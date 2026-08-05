"""Split raw bibliography text into entries and parse each into a Reference.

Currently handles NeurIPS-style numbered ("[n] ...") bibliographies, the
convention citebot.extract.pdf hands off here after isolating the References
section of a paper. Multi-convention support (author-year, etc., picked via
the shared style detector in citebot.parse.style) was prototyped and is
commented out below for now. Revisit later.

Splitting each entry into title/authors/year is delegated to anystyle-cli (a
CRF-based reference parser) rather than hand-written regex: citation
formatting is inconsistent enough (missing delimiters between title and
venue, periods inside author initials, etc.) that a period/capitalization
heuristic mis-splits real entries. See notes.md.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from citebot.models import ExtractionSource, Identifiers, Reference
from citebot.parse import normalize

ENTRY_MARKER = re.compile(r"\[(\d+)\]")

_DATE_YEAR = re.compile(r"\d{4}")


class AnystyleNotFoundError(RuntimeError):
    """Raised when the anystyle-cli binary can't be located."""


def _anystyle_bin() -> str:
    """Locate the anystyle-cli executable.

    `gem install anystyle-cli` on macOS system Ruby needs --user-install,
    which lands in Gem.user_dir/bin - a path that's often not on PATH. Fall
    back to asking Ruby for that directory before giving up.
    """
    found = shutil.which("anystyle")
    if found:
        return found

    try:
        user_dir = subprocess.run(
            ["ruby", "-rrubygems", "-e", "print Gem.user_dir"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        candidate = Path(user_dir) / "bin" / "anystyle"
        if candidate.exists():
            return str(candidate)
    except (OSError, subprocess.CalledProcessError):
        pass

    raise AnystyleNotFoundError(
        "anystyle-cli not found. Install it with `gem install anystyle-cli` "
        "(see README for setup)."
    )


def _run_anystyle(raw_entries: list[str]) -> list[dict]:
    """Parse raw entry strings into anystyle's structured records, in order."""
    if not raw_entries:
        return []

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("\n".join(raw_entries))
        tmp_path = f.name

    try:
        result = subprocess.run(
            [_anystyle_bin(), "--format", "json", "parse", tmp_path],
            capture_output=True, text=True, check=True,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return json.loads(result.stdout)


def _authors_from_record(record: dict) -> list[str]:
    names = []
    for author in record.get("author", []):
        if "others" in author:
            continue
        name = " ".join(p for p in (author.get("given", ""), author.get("family", "")) if p)
        if name:
            names.append(name)
    return names


def _title_from_record(record: dict) -> Optional[str]:
    titles = record.get("title")
    if not titles:
        return None
    return normalize.clean_title(" ".join(titles))


def _year_from_record(record: dict) -> Optional[int]:
    for date in record.get("date", []):
        match = _DATE_YEAR.search(date)
        if match:
            return int(match.group())
    return None


def split_entries(section: str) -> list[tuple[str, str]]:
    """Split the bibliography into (number, entry text) pairs.

    Each entry runs from its own "[n]" marker up to the next one, and the
    last entry runs to the end of the section.
    """
    markers = list(ENTRY_MARKER.finditer(section))
    entries = []

    for i, marker in enumerate(markers):
        number = marker.group(1)

        # The entry body sits between this marker and the next one.
        start = marker.end()
        if i + 1 < len(markers):
            end = markers[i + 1].start()
        else:
            end = len(section)

        # split() + join() collapses the line breaks the PDF put mid-entry.
        body = " ".join(section[start:end].split())
        if body:
            entries.append((number, body))

    return entries


def parse_entry(number: str, raw: str, record: dict) -> Reference:
    return Reference(
        ref_id=number,
        raw_string=raw,
        title=_title_from_record(record),
        authors=_authors_from_record(record),
        year=_year_from_record(record) or normalize.extract_year(raw),
        identifiers=Identifiers(
            doi=normalize.extract_doi(raw),
            arxiv_id=normalize.extract_arxiv_id(raw),
            url=normalize.extract_url(raw),
        ),
        source=ExtractionSource.PDF,
    )


def parse(section: str) -> list[Reference]:
    """Split a bibliography section and parse every entry via anystyle-cli."""
    entries = split_entries(section)
    records = _run_anystyle([raw for _, raw in entries])
    return [
        parse_entry(number, raw, record)
        for (number, raw), record in zip(entries, records)
    ]


# --------------------------------------------------------------------------- #
# Multi-convention support (author-year splitting/parsing + shared style
# detection) - commented out for now, bare-bones NeurIPS-only support above.
# Revisit later.
# --------------------------------------------------------------------------- #
#
# def _split_author_year_entries(section: str) -> list[str]:
#     """Split an author-year bibliography into raw entry strings.
#
#     Entry boundaries are found with AUTHOR_YEAR_BOUNDARY rather than a
#     single unambiguous marker (author-year bibliographies don't have one),
#     so this is best-effort: it works well on cleanly extracted text and
#     degrades gracefully (fewer, longer entries) on messier PDFs.
#     """
#     norm = " ".join(section.split())
#
#     bounds = [m.end() for m in AUTHOR_YEAR_BOUNDARY.finditer(norm)]
#     if not bounds or bounds[0] != 0:
#         bounds = [0] + bounds
#     bounds.append(len(norm))
#
#     chunks = [
#         raw for start, end in zip(bounds, bounds[1:])
#         if (raw := norm[start:end].strip(" ."))
#     ]
#
#     # A real entry boundary is followed shortly by a "(YYYY)" year, but
#     # venue/publisher text that happens to start with a capitalized word +
#     # comma (e.g. "Nature, 521(7553), 436-444.") can also match the
#     # boundary pattern. Merge any chunk without a year into the entry
#     # before it rather than treating it as its own reference.
#     entries: list[str] = []
#     for chunk in chunks:
#         if entries and not YEAR_PAREN.search(chunk):
#             entries[-1] = f"{entries[-1]} {chunk}"
#         elif len(chunk) > 5:
#             entries.append(chunk)
#     return entries
#
#
# def _parse_author_year_entry(index: str, raw: str) -> Reference:
#     year_match = YEAR_PAREN.search(raw)
#     if year_match:
#         author_block = raw[:year_match.start()]
#         rest = raw[year_match.end():].strip(" .,")
#     else:
#         author_block = raw
#         rest = ""
#
#     title = None
#     if rest:
#         sentences = SENTENCE_BREAK.split(rest)
#         title = normalize.clean_title(sentences[0])
#
#     return Reference(
#         ref_id=index,
#         raw_string=raw,
#         title=title,
#         authors=normalize.parse_authors(author_block),
#         year=normalize.extract_year(raw),
#         identifiers=Identifiers(
#             doi=normalize.extract_doi(raw),
#             arxiv_id=normalize.extract_arxiv_id(raw),
#             url=normalize.extract_url(raw),
#         ),
#         source=ExtractionSource.PDF,
#     )
#
#
# def _detect_style(section: str) -> style.CitationStyle:
#     """Classify the bibliography's citation convention before splitting it.
#
#     Feeds candidate entry-leading snippets for both conventions through
#     the shared classifier (citebot/parse/style.py) and majority-votes, since
#     a document can contain a handful of spurious matches for the "wrong"
#     convention (e.g. a URL fragment that looks like a bracketed number).
#     """
#     numbered_markers = [f"[{m.group(1)}]" for m in ENTRY_MARKER.finditer(section)]
#
#     norm = " ".join(section.split())
#     author_year_snippets = [
#         norm[m.end():m.end() + 80] for m in AUTHOR_YEAR_BOUNDARY.finditer(norm)
#     ]
#
#     return style.dominant_style(numbered_markers + author_year_snippets)
#
#
# def parse_verbose(section: str) -> tuple[style.CitationStyle, list[Reference]]:
#     """Like parse(), but also returns the detected citation style."""
#     detected = _detect_style(section)
#
#     if detected == style.CitationStyle.AUTHOR_YEAR:
#         references = [
#             _parse_author_year_entry(str(i), raw)
#             for i, raw in enumerate(_split_author_year_entries(section), start=1)
#         ]
#     else:
#         references = [parse_entry(number, raw) for number, raw in split_entries(section)]
#
#     return detected, references
