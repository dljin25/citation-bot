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
    # Sub-scores behind match_score, exposed so citebot.classify can reason about
    # them individually (e.g. title matches but authors don't). author_score is
    # None rather than 0.0 when either author list is empty — "no data to compare"
    # is a different state from "compared and found no overlap".
    title_score: float = 0.0
    author_score: Optional[float] = None
    year_score: float = 0.0


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

def score(ref: Reference, candidate: Candidate) -> None:
    """Score how confident we are that candidate is the same paper as ref, 0..1.

    Writes the breakdown (title_score, author_score, year_score, match_score)
    onto candidate. An exact DOI/arXiv id match means candidate is genuinely
    the work at that identifier, not that its metadata is honest — title,
    authors, and year are compared the same way regardless of how the
    candidate was found, so a right-id-wrong-paper case still scores low.
    """
    candidate.title_score = title_similarity(ref.title, candidate.title)
    candidate.author_score = author_overlap(ref.authors, candidate.authors)
    candidate.year_score = 1.0 if year_match(ref.year, candidate.year) else 0.0

    author_component = candidate.author_score if candidate.author_score is not None else 0.0
    candidate.match_score = (
        0.6 * candidate.title_score + 0.25 * author_component + 0.15 * candidate.year_score
    )


def title_similarity(a: Optional[str], b: Optional[str]) -> float:
    """0..1 similarity between two titles, case/whitespace-insensitive."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, _normalize_title(a), _normalize_title(b)).ratio()


def author_overlap(a: list[str], b: list[str]) -> Optional[float]:
    """Fraction of surnames shared between two author lists, 0..1, or None if
    either list is empty (nothing to compare, not "no overlap")."""
    surnames_a = {_surname(name) for name in a}
    surnames_b = {_surname(name) for name in b}
    if not surnames_a or not surnames_b:
        return None
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
