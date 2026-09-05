"""Turn a crossref Resolution into a trust verdict for a reference.

Deliberately biased toward a low false-positive rate: CONFLICT is an
accusation (this citation may not check out) and requires strong, complete
evidence, whereas VERIFIED only needs a confident match. Anything in
between, or any case where a source couldn't be reached, falls back to
AMBIGUOUS rather than risk wrongly flagging a legitimate citation.
"""

from __future__ import annotations

from enum import Enum
from typing import NamedTuple, Optional

from citebot.crossref.base import CrossrefSource, Resolution

VERIFIED_THRESHOLD = 0.7
NO_MATCH_THRESHOLD = 0.15
CONFLICT_TITLE_THRESHOLD = 0.7
CONFLICT_AUTHOR_THRESHOLD = 0.1

# Only OpenAlex is active while DBLP/Semantic Scholar are disabled — see CLAUDE.md.
_ALL_SOURCES = {CrossrefSource.OPENALEX}


class Verdict(str, Enum):
    VERIFIED = "verified"
    AMBIGUOUS = "ambiguous"
    CONFLICT = "conflict"


class ConflictReason(str, Enum):
    """Why a CONFLICT verdict was reached — CLI uses this to explain itself."""

    NO_CANDIDATE = "no_candidate"
    AUTHOR_MISMATCH = "author_mismatch"


class Classification(NamedTuple):
    verdict: Verdict
    reason: Optional[ConflictReason] = None


def classify(resolution: Resolution) -> Classification:
    best = resolution.best
    searched_everywhere = set(resolution.sources_ok) == _ALL_SOURCES

    if best is None:
        if searched_everywhere:
            return Classification(Verdict.CONFLICT, ConflictReason.NO_CANDIDATE)
        return Classification(Verdict.AMBIGUOUS)

    if best.match_score >= VERIFIED_THRESHOLD:
        return Classification(Verdict.VERIFIED)

    # A well-matched title with authors that don't back it up is stronger,
    # more specific evidence than a merely middling blended score — it says
    # "we found the paper this is citing, and it disagrees with the claim",
    # not just "nothing scored high enough". author_score is None (rather
    # than 0.0) when ref.authors was never extracted, so a missing author
    # list can't be mistaken for a real mismatch.
    if (
        best.title_score >= CONFLICT_TITLE_THRESHOLD
        and best.author_score is not None
        and best.author_score <= CONFLICT_AUTHOR_THRESHOLD
    ):
        return Classification(Verdict.CONFLICT, ConflictReason.AUTHOR_MISMATCH)

    if best.title_score < NO_MATCH_THRESHOLD and searched_everywhere:
        return Classification(Verdict.CONFLICT, ConflictReason.NO_CANDIDATE)

    return Classification(Verdict.AMBIGUOUS)
