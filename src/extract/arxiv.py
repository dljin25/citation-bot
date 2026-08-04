"""Extract references from an arXiv paper's compiled .bbl.

Strategy:
  1. Download the e-print source tarball.
  2. Locate the compiled ``.bbl`` file(s). If none exist (some sources embed
     the bibliography directly in a ``.tex`` file instead of a compiled
     ``.bbl``), fall back to any ``\\begin{thebibliography}`` block found in
     the ``.tex`` sources.
  3. Parse it. Two .bbl dialects are handled: classic natbib/plain
     (``\\bibitem`` + ``\\newblock``) and biblatex (``\\entry`` + ``\\field``).

"""

from __future__ import annotations

import io
import re
import tarfile
from typing import Optional

import httpx

from src.extract import normalize as N
# from src.extract import style  # only needed by the commented-out style-detection code below
from src.models import ExtractionSource, Identifiers, Reference

ARXIV_EPRINT = "https://arxiv.org/e-print/{id}"
_USER_AGENT = "citebot/0.1 (research-integrity tool; mailto:davidjin684@gmail.com)"

# --------------------------------------------------------------------------- #
# Download from ARXIV_EPRINT
# --------------------------------------------------------------------------- #

def fetch_source_files(arxiv_id: str, *, timeout: float = 60.0) -> dict[str, str]:
    """Return {filename: text} for all text-ish files in the e-print source."""
    url = ARXIV_EPRINT.format(id=arxiv_id)
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout,
                          headers={"User-Agent": _USER_AGENT}) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.content

    # failure modes
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise ValueError(
                f"No arXiv paper found for id '{arxiv_id}' (404)."
            ) from e
        raise ValueError(
            f"arXiv returned {e.response.status_code} fetching '{arxiv_id}'."
        ) from e
    except httpx.RequestError as e:
        raise ValueError(f"Could not reach arXiv to fetch '{arxiv_id}': {e}") from e
    
    return _unpack(data)


_TEX_BIBLIOGRAPHY_RE = re.compile(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", re.DOTALL)


def _unpack(data: bytes) -> dict[str, str]: # Ex. data = b'\x1f\x8b\x08...'
    bbl_files: dict[str, str] = {}
    tex_files: dict[str, str] = {}

    # tar.gz
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                name = member.name.lower()
                if not (name.endswith(".bbl") or name.endswith(".tex")):
                    continue
                f = tar.extractfile(member)
                if f is None:
                    continue
                text = _decode(f.read())
                if name.endswith(".bbl"):
                    bbl_files[member.name] = text
                else:
                    tex_files[member.name] = text
    except tarfile.TarError:
        pass

    if bbl_files:
        return bbl_files

    # No compiled .bbl shipped with the source — some papers embed the
    # bibliography directly in a .tex file instead.
    inline: dict[str, str] = {}
    for name, text in tex_files.items():
        m = _TEX_BIBLIOGRAPHY_RE.search(text)
        if m:
            inline[name] = m.group(0)
    return inline


def _decode(b: bytes) -> str:
    for enc in ("utf-8", "latin-1"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", errors="replace")


# --------------------------------------------------------------------------- #
# Locate bibliography content
# --------------------------------------------------------------------------- #
def _select_bibliography(files: dict[str, str]) -> str:
    """Return the concatenated text of all .bbl files, or '' if none."""
    return "\n".join(files.values())


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
    for chunk in chunks[1:]:
        # strip the [label] and {key}
        m = re.match(r"\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}", chunk)
        key = m.group(1) if m else f"ref{idx + 1}"
        body = chunk[m.end():] if m else chunk
        body = body.split("\\bibitem")[0]
        raw = N.strip_latex(body)
        if not raw:
            continue
        idx += 1

        blocks = [b.strip() for b in re.split(r"\\newblock", body) if b.strip()]
        title = author = venue = None
        if len(blocks) >= 2:
            author = blocks[0]
            title = N.clean_title(blocks[1])
            if len(blocks) >= 3:
                venue = N.strip_latex(blocks[2]) or None
            authors = N.parse_authors(author)
        else:
            authors = N.parse_authors(blocks[0]) if blocks else []
        confidence = 0.9 if (title and authors) else 0.4

        refs.append(Reference(
            ref_id=key,
            raw_string=raw,
            title=title,
            authors=authors,
            year=N.extract_year(raw),
            venue=venue,
            identifiers=_ident_from(body),
            source=ExtractionSource.BBL,
            extraction_confidence=confidence,
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
        confidence = 0.95 if (title and authors) else 0.5
        refs.append(Reference(
            ref_id=key,
            raw_string=raw or (title or key),
            title=title,
            authors=[a for a in authors if a],
            year=int(year) if year and year.isdigit() else None,
            venue=venue,
            identifiers=idents,
            source=ExtractionSource.BBL,
            extraction_confidence=confidence,
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
# def detect_style(files: dict[str, str]) -> style.CitationStyle:
#     """Classify the bibliography's citation convention, via the same
#     shared classifier the PDF extractor uses (src/extract/style.py).
#
#     Only the natbib/plain dialect carries a usable signal: its optional
#     \\bibitem[label]{key} argument holds "[Author, Year]" for author-year
#     styles and is omitted entirely for numbered styles (natbib only
#     populates it when rendering needs the author-year text). biblatex
#     .bbl entries are already fully structured fields regardless of the
#     citation style used to render them, so there's no ambiguity to
#     resolve and detection is skipped.
#     """
#     text = _select_bibliography(files)
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
def extract_from_files(files: dict[str, str]) -> list[Reference]:
    text = _select_bibliography(files)
    if not text.strip():
        return []
    if "\\entry{" in text:  # biblatex dialect
        return parse_biblatex_bbl(text)
    return parse_bibitems(text)


# def extract_verbose(arxiv_id: str) -> tuple[style.CitationStyle, list[Reference]]:
#     """Like extract(), but also returns the detected citation style."""
#     files = fetch_source_files(arxiv_id)
#     return detect_style(files), extract_from_files(files)


def extract(arxiv_id: str) -> list[Reference]:
    """Public extractor: arXiv id -> normalized references."""
    files = fetch_source_files(arxiv_id)
    return extract_from_files(files)
