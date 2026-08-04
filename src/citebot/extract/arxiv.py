"""Fetch an arXiv paper's compiled .bbl (or inline bibliography) source.

Strategy:
  1. Download the e-print source tarball.
  2. Locate the compiled ``.bbl`` file(s). If none exist (some sources embed
     the bibliography directly in a ``.tex`` file instead of a compiled
     ``.bbl``), fall back to any ``\\begin{thebibliography}`` block found in
     the ``.tex`` sources.
  3. Hand the raw bibliography text off to citebot.parse.bibtex for parsing.
"""

from __future__ import annotations

import io
import re
import tarfile

import httpx

from citebot.models import Reference
from citebot.parse import bibtex

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
# Entry point
# --------------------------------------------------------------------------- #
def extract_from_files(files: dict[str, str]) -> list[Reference]:
    return bibtex.parse(_select_bibliography(files))


def extract(arxiv_id: str) -> list[Reference]:
    """Public extractor: arXiv id -> normalized references."""
    files = fetch_source_files(arxiv_id)
    return extract_from_files(files)
