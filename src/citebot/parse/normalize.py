"""Field normalization shared across extractors.

These helpers turn messy LaTeX/PDF-derived strings into clean, comparable field
values. They are deliberately conservative: when a field cannot be parsed with
confidence we return None rather than guessing, so downstream resolution sees an
honest "unknown" instead of a fabricated value.
"""

from __future__ import annotations

import re
from typing import Optional

# --------------------------------------------------------------------------- #
# LaTeX cleanup
# --------------------------------------------------------------------------- #
# Accent commands like \'e \"{o} \~n \c{c} \v{s} -> keep the base letter.
_ACCENT_RE = re.compile(r"\\[`'\"^~=.uvHtcdbr]\s*\{?([a-zA-Z])\}?")
# Generic command with one braced arg we want to keep the content of.
_KEEP_ARG_CMDS = re.compile(r"\\(?:emph|textbf|textit|textsc|text|mbox|href\{[^}]*\})\s*\{([^{}]*)\}")
# Commands to drop entirely (with optional arg).
_DROP_CMDS = re.compile(r"\\(?:newblock|bibinfo|natexlab|urlprefix|doi|url|penalty|protect|relax|bgroup|egroup|noopsort)\b")
_INLINE_MATH = re.compile(r"\$[^$]*\$")
_BRACES = re.compile(r"[{}]")
_MULTISPACE = re.compile(r"\s+")


def strip_latex(s: str) -> str:
    """Remove LaTeX markup, keeping human-readable text."""
    if not s:
        return ""
    s = s.replace("\\&", "&").replace("\\%", "%").replace("\\_", "_")
    s = _INLINE_MATH.sub(" ", s)
    # apply keep-arg replacement repeatedly for nesting
    prev = None
    while prev != s:
        prev = s
        s = _KEEP_ARG_CMDS.sub(r"\1", s)
    s = _ACCENT_RE.sub(r"\1", s)
    s = _DROP_CMDS.sub(" ", s)
    # any remaining \command (no/other args) -> drop the command token
    s = re.sub(r"\\[a-zA-Z]+", " ", s)
    s = s.replace("~", " ").replace("--", "-").replace("\\", " ")
    s = _BRACES.sub("", s)
    s = _MULTISPACE.sub(" ", s).strip(" .,;")
    return s.strip()


# --------------------------------------------------------------------------- #
# Identifier extraction
# --------------------------------------------------------------------------- #
_ARXIV_RE = re.compile(
    r"arxiv[:\s]*((?:\d{4}\.\d{4,5})(?:v\d+)?|(?:[a-z\-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?)",
    re.IGNORECASE,
)
_ARXIV_BARE_RE = re.compile(r"\b(\d{4}\.\d{4,5})(v\d+)?\b")
_DOI_RE = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)\b")
_URL_RE = re.compile(r"https?://[^\s,}{)\]]+", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")
# A bibitem with no separate venue \newblock (e.g. a plain preprint/tech
# report entry) leaves the year glued onto the title's own block, since
# there's nothing else to hold it — matches only a trailing ", <year>",
# never a year appearing elsewhere in a legitimate title.
_TRAILING_YEAR_RE = re.compile(r",\s*(19[5-9]\d|20[0-4]\d)\.?\s*$")


def extract_arxiv_id(s: str) -> Optional[str]:
    m = _ARXIV_RE.search(s)
    if m:
        return m.group(1)
    # bare new-style id only if the word 'arxiv' appears nearby or it's isolated
    if "arxiv" in s.lower():
        m = _ARXIV_BARE_RE.search(s)
        if m:
            return m.group(1)
    return None


def extract_doi(s: str) -> Optional[str]:
    m = _DOI_RE.search(s)
    return m.group(1).rstrip(".") if m else None


def extract_url(s: str) -> Optional[str]:
    m = _URL_RE.search(s)
    return m.group(0).rstrip(".,") if m else None


def extract_year(s: str) -> Optional[int]:
    matches = _YEAR_RE.findall(s)
    if not matches:
        return None
    # prefer the last 4-digit year in the string (usually the publication year)
    return int(matches[-1])


# --------------------------------------------------------------------------- #
# Authors
# --------------------------------------------------------------------------- #
_ETAL_RE = re.compile(r"\bet\s*al\.?", re.IGNORECASE)


def parse_authors(block: str) -> list[str]:
    """Parse an author block into a list of display names.

    Handles 'A, B, and C', 'A and B', and 'Last, First' segments. Drops 'et al.'.
    Conservative: if a segment looks empty or junk it is skipped.
    """
    if not block:
        return []
    block = strip_latex(block)
    block = _ETAL_RE.sub("", block)
    # normalize separators: '&' and ' and ' -> comma
    block = re.sub(r"\s*&\s*", ", ", block)
    block = re.sub(r"\s+and\s+", ", ", block, flags=re.IGNORECASE)
    parts = [p.strip(" .,") for p in block.split(",")]

    authors: list[str] = []
    i = 0
    # rejoin "Last, First" pairs heuristically: if a part has no space and the
    # next part is short initials/given names, treat them as one author.
    while i < len(parts):
        p = parts[i]
        if not p:
            i += 1
            continue
        nxt = parts[i + 1] if i + 1 < len(parts) else ""
        if (
            " " not in p
            and nxt
            and len(nxt.split()) <= 3
            and re.match(r"^[A-Z][\w.\- ]*$", nxt)
            and not re.search(r"\d", nxt)
        ):
            authors.append(f"{nxt} {p}".strip())
            i += 2
        else:
            authors.append(p)
            i += 1
    return [a for a in authors if a and len(a) > 1]


def surname(name: str) -> str:
    """Best-effort surname extraction for last-name-set overlap."""
    name = name.strip()
    if "," in name:
        return name.split(",")[0].strip().lower()
    toks = name.split()
    return toks[-1].lower() if toks else ""


# --------------------------------------------------------------------------- #
# Title
# --------------------------------------------------------------------------- #
def clean_title(s: str) -> Optional[str]:
    t = strip_latex(s).strip(" .")
    t = _TRAILING_YEAR_RE.sub("", t).strip(" .,")
    if not t or len(t) < 3:
        return None
    return t
