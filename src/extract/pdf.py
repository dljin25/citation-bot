"""Extract references from a NeurIPS paper PDF.

NeurIPS papers are single-column with a numbered, natbib-style bibliography,
so plain text extraction (no layout analysis needed) plus a "[n] ..." split
is enough to isolate entries.

The pipeline is three steps:
    PDF -> full text -> just the bibliography -> one Reference per entry

Multi-convention support (author-year, etc., picked via a shared style
detector) was prototyped and is commented out below for now, bare-bones
NeurIPS-numbered support only. Revisit later.
"""

from __future__ import annotations

import re # regex
from pathlib import Path

from pypdf import PdfReader

from src.extract import normalize
# from src.extract import style  # only needed by the commented-out style-detection code below
from src.models import ExtractionSource, Identifiers, Reference

# regex patterns

REFERENCES_HEADING = re.compile(r"^\s*references\s*$", re.IGNORECASE | re.MULTILINE)

NEXT_SECTION_HEADING = re.compile(r"^\s*(appendix|checklist|supplementary material)\b", re.IGNORECASE | re.MULTILINE)

ENTRY_MARKER = re.compile(r"\[(\d+)\]")

SENTENCE_BREAK = re.compile(r"\.\s+(?=[A-Z])")

# # An author-year entry starts at document start, or right after a sentence
# # ending ("... 45-67. ") that is immediately followed by a capitalized
# # surname and comma (e.g. "Smith, J. ..."). Mid-entry author lists don't
# # trigger this because co-authors are joined by "," or " and ", not ". ".
# AUTHOR_YEAR_BOUNDARY = re.compile(r"(?:^|\.\s+)(?=[A-Z][A-Za-z\-']+,\s)")
#
# YEAR_PAREN = re.compile(r"\(?(19[5-9]\d|20[0-4]\d)[a-z]?\)?")

def _references_section(text: str) -> str:
    """Return just the bibliography.

    That is the text between the "References" heading and whichever section
    comes after it. Returns "" if the paper has no References heading.
    """
    heading = REFERENCES_HEADING.search(text)
    if not heading:
        return ""

    section = text[heading.end():]

    # Stop at the next heading. If there isn't one, the bibliography runs
    # to the end of the document.
    next_heading = NEXT_SECTION_HEADING.search(section)
    if not next_heading:
        return section
    return section[:next_heading.start()]


def _split_entries(section: str) -> list[tuple[str, str]]:
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


def _parse_entry(number: str, raw: str) -> Reference:

    sentences = SENTENCE_BREAK.split(raw)

    authors = normalize.parse_authors(sentences[0])
    if len(sentences) > 1:
        title = normalize.clean_title(sentences[1])
    else:
        title = None

    return Reference(
        ref_id=number,
        raw_string=raw,
        title=title,
        authors=authors,
        year=normalize.extract_year(raw),
        identifiers=Identifiers(
            doi=normalize.extract_doi(raw),
            arxiv_id=normalize.extract_arxiv_id(raw),
            url=normalize.extract_url(raw),
        ),
        source=ExtractionSource.PDF,
    )


# --------------------------------------------------------------------------- #
# Multi-convention support (author-year splitting/parsing + shared style
# detection) - commented out for now, bare-bones NeurIPS-only support below.
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
#     the shared classifier (src/extract/style.py) and majority-votes, since
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
# def extract_verbose(pdf_path: str | Path) -> tuple[style.CitationStyle, list[Reference]]:
#     """Like extract(), but also returns the detected citation style."""
#     reader = PdfReader(str(pdf_path))
#
#     pages = []
#     for page in reader.pages:
#         # extract_text() returns None on pages with no text layer.
#         pages.append(page.extract_text() or "")
#     text = "\n".join(pages)
#
#     section = _references_section(text)
#     detected = _detect_style(section)
#
#     if detected == style.CitationStyle.AUTHOR_YEAR:
#         references = [
#             _parse_author_year_entry(str(i), raw)
#             for i, raw in enumerate(_split_author_year_entries(section), start=1)
#         ]
#     else:
#         references = [_parse_entry(number, raw) for number, raw in _split_entries(section)]
#
#     return detected, references


def extract(pdf_path: str | Path) -> list[Reference]:
    """Read a paper PDF and return every reference in its bibliography."""
    reader = PdfReader(str(pdf_path))

    pages = []
    for page in reader.pages:
        # extract_text() returns None on pages with no text layer.
        pages.append(page.extract_text() or "")
    text = "\n".join(pages)

    section = _references_section(text)

    references = []
    for number, raw in _split_entries(section):
        references.append(_parse_entry(number, raw))
    return references
