"""Shared resolver interface and matching helpers for crossref backends.

Defines the Candidate/Resolution data model that openalex.py, dblp.py, and
semantic_scholar.py each return into, plus the scoring helpers used to judge
how well a candidate matches the reference we searched for.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from enum import Enum
from typing import Optional, Protocol

from pydantic import BaseModel, Field

from citebot.models import Identifiers, Reference


class CrossrefSource(str, Enum):
    DBLP = "dblp"
    OPENALEX = "openalex"
    SEMANTIC_SCHOLAR = "semantic_scholar"


class Candidate(BaseModel):
    """One paper a backend found that might match a Reference."""

    source: CrossrefSource
    title: Optional[str] = None
    authors: list[str] = Field(default_factory=list)
    year: Optional[int] = None
    identifiers: Identifiers = Field(default_factory=Identifiers)
    venue: Optional[str] = None
    url: Optional[str] = None
    match_score: float = 0.0


class Resolution(BaseModel):
    """The outcome of resolving one Reference against all crossref sources."""

    ref_id: str
    candidates: list[Candidate] = Field(default_factory=list)
    best: Optional[Candidate] = None
    # Sources that responded successfully, whether or not they found a candidate.
    # Lets citebot.classify tell "searched everywhere, found nothing" apart from
    # "couldn't reach some sources" — the latter isn't enough evidence to flag a
    # reference as not found.
    sources_ok: list[CrossrefSource] = Field(default_factory=list)


class Resolver(Protocol):
    def resolve(self, ref: Reference) -> list[Candidate]:
        """Return candidate matches for ref (unscored; caller scores them)."""
        ...


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #

def score(ref: Reference, candidate: Candidate) -> float:
    """How confident we are that candidate is the same paper as ref, 0..1.

    An exact DOI or arXiv id match is treated as certain. Otherwise blend
    title similarity (most reliable signal), author overlap, and year
    closeness.
    """
    ids = ref.identifiers
    if ids.doi and ids.doi == candidate.identifiers.doi:
        return 1.0
    if ids.arxiv_id and ids.arxiv_id == candidate.identifiers.arxiv_id:
        return 1.0

    title_score = title_similarity(ref.title, candidate.title)
    author_score = author_overlap(ref.authors, candidate.authors)
    year_score = 1.0 if year_match(ref.year, candidate.year) else 0.0

    return 0.6 * title_score + 0.25 * author_score + 0.15 * year_score


def title_similarity(a: Optional[str], b: Optional[str]) -> float:
    """0..1 similarity between two titles, case/whitespace-insensitive."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, _normalize_title(a), _normalize_title(b)).ratio()


def author_overlap(a: list[str], b: list[str]) -> float:
    """Fraction of surnames shared between two author lists, 0..1."""
    surnames_a = {_surname(name) for name in a}
    surnames_b = {_surname(name) for name in b}
    if not surnames_a or not surnames_b:
        return 0.0
    return len(surnames_a & surnames_b) / len(surnames_a | surnames_b)


def year_match(a: Optional[int], b: Optional[int], tolerance: int = 1) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= tolerance


def _normalize_title(title: str) -> str:
    return " ".join(title.lower().split())


def _surname(name: str) -> str:
    """Best-effort surname from a display name, for coarse author matching."""
    parts = name.strip().split()
    return parts[-1].lower() if parts else ""
