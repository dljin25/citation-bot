"""Parse .bbl bibliography text into Reference objects.

Two .bbl dialects are handled: classic natbib/plain (\\bibitem + \\newblock)
and biblatex (\\entry + \\field). Callers (e.g. citebot.extract.arxiv) are
responsible for locating and fetching the raw .bbl text; this module only
turns that text into structured references.
"""

from __future__ import annotations

import re
from typing import Optional

from citebot.models import ExtractionSource, Identifiers, Reference
from citebot.parse import normalize as N

# --------------------------------------------------------------------------- #
# Parsers
# --------------------------------------------------------------------------- #
def _ident_from(raw: str) -> Identifiers:
    return Identifiers(
        doi=N.extract_doi(raw),
        arxiv_id=N.extract_arxiv_id(raw),
        url=N.extract_url(raw),
    )


def parse_bibitems(text: str) -> list[Reference]:
    """Classic natbib/plain .bbl: \\bibitem[label]{key} blocks split by \\newblock."""
    refs: list[Reference] = []

    # split into bibitem blocks
    chunks = re.split(r"\\bibitem", text)

    idx = 0
    for chunk in chunks[1:]: # ignore chunks[0] preamble
        m = re.match(r"\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}", chunk)
        key = m.group(1) if m else f"ref{idx + 1}"
        body = chunk[m.end():] if m else chunk
        raw = N.strip_latex(body)
        if not raw:
            continue
        idx += 1

        blocks = [b.strip() for b in re.split(r"\\newblock", body) if b.strip()]
        title = author = None
        if len(blocks) >= 2:
            author = blocks[0]
            title = N.clean_title(blocks[1])
            authors = N.parse_authors(author)
        else:
            authors = N.parse_authors(blocks[0]) if blocks else []

        refs.append(Reference(
            ref_id=key,
            raw_string=raw,
            title=title,
            authors=authors,
            year=N.extract_year(raw),
            identifiers=_ident_from(body),
            source=ExtractionSource.BBL,
        ))
    return refs


def parse_biblatex_bbl(text: str) -> list[Reference]:
    """biblatex .bbl: \\entry{key}{type}{} with \\field / \\name blocks."""
    refs: list[Reference] = []
    entries = re.split(r"\\entry\{", text)
    for idx, ent in enumerate(entries[1:]):
        key = ent[: ent.index("}")] if "}" in ent else f"ref{idx + 1}"
        body = ent.split("\\endentry")[0]

        def field(name: str) -> Optional[str]:
            m = re.search(r"\\field\{" + re.escape(name) + r"\}\{(.*?)\}", body, re.DOTALL)
            return N.strip_latex(m.group(1)) if m else None

        title = N.clean_title(field("title") or "")
        venue = field("journaltitle") or field("booktitle") or field("eventtitle")
        year = field("year")
        if not year:
            date = field("date") or ""
            ym = re.search(r"\b(19|20)\d{2}\b", date)
            year = ym.group(0) if ym else None

        # authors: prefer key=value (family={...}, given={...}); fall back to positional
        authors: list[str] = []
        name_block = re.search(r"\\name\{author\}.*?\{%(.*?)\}\s*$", body, re.DOTALL)
        search_region = name_block.group(1) if name_block else body
        for fam, giv in re.findall(r"family=\{([^}]*)\}.*?given=\{([^}]*)\}", search_region, re.DOTALL):
            authors.append(N.strip_latex(f"{giv} {fam}".strip()))
        if not authors:
            for grp in re.findall(r"\{\{[^}]*\}\{([^}]*)\}\{([^}]*)\}", search_region):
                fam, giv = grp
                authors.append(N.strip_latex(f"{giv} {fam}".strip()))

        eprint = field("eprint")
        raw_parts = [", ".join(authors), title or "", venue or "", year or ""]
        raw = N.strip_latex(" ".join(p for p in raw_parts if p))
        idents = Identifiers(
            doi=field("doi") or N.extract_doi(body),
            arxiv_id=eprint if (eprint and re.match(r"\d{4}\.\d{4,5}", eprint)) else N.extract_arxiv_id(body),
            url=field("url") or N.extract_url(body),
        )
        refs.append(Reference(
            ref_id=key,
            raw_string=raw or (title or key),
            title=title,
            authors=[a for a in authors if a],
            year=int(year) if year and year.isdigit() else None,
            venue=venue,
            identifiers=idents,
            source=ExtractionSource.BBL,
        ))
    return refs


# --------------------------------------------------------------------------- #
# Style detection - commented out for now, bare-bones dialect-only support
# (parse_bibitems / parse_biblatex_bbl already handle both regardless of
# citation style). Revisit later.
# --------------------------------------------------------------------------- #
# _BIBITEM_LABEL_RE = re.compile(r"\\bibitem\s*(?:\[([^\]]*)\])?\s*\{")
#
#
# def detect_style(text: str) -> style.CitationStyle:
#     """Classify the bibliography's citation convention, via the same
#     shared classifier the PDF extractor uses (citebot/parse/style.py).
#
#     Only the natbib/plain dialect carries a usable signal: its optional
#     \\bibitem[label]{key} argument holds "[Author, Year]" for author-year
#     styles and is omitted entirely for numbered styles (natbib only
#     populates it when rendering needs the author-year text). biblatex
#     .bbl entries are already fully structured fields regardless of the
#     citation style used to render them, so there's no ambiguity to
#     resolve and detection is skipped.
#     """
#     if not text.strip() or "\\entry{" in text:
#         return style.CitationStyle.UNKNOWN
#
#     labels = [m.group(1) or "" for m in _BIBITEM_LABEL_RE.finditer(text)]
#     if not labels:
#         return style.CitationStyle.UNKNOWN
#
#     # An empty label is itself a numbered-style signal (see docstring), so
#     # stand it in for a marker rather than letting it fall through as
#     # unclassifiable text.
#     samples = [label if label else "[1]" for label in labels]
#     return style.dominant_style(samples)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def parse(text: str) -> list[Reference]:
    """Dispatch raw .bbl text to the matching dialect parser."""
    if not text.strip():
        return []
    if "\\entry{" in text:  # biblatex dialect
        return parse_biblatex_bbl(text)
    return parse_bibitems(text)
