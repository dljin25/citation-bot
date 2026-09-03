"""Turn a crossref Resolution into a trust verdict for a reference.

Deliberately biased toward a low false-positive rate: NOT_FOUND is an
accusation (this citation may not exist) and requires strong, complete
evidence, whereas VERIFIED only needs a confident match. Anything in
between, or any case where a source couldn't be reached, falls back to
AMBIGUOUS rather than risk wrongly flagging a legitimate citation.
"""

from __future__ import annotations

from enum import Enum

from citebot.crossref.base import CrossrefSource, Resolution

VERIFIED_THRESHOLD = 0.7
NOT_FOUND_THRESHOLD = 0.15

# Only OpenAlex is active while DBLP/Semantic Scholar are disabled — see CLAUDE.md.
_ALL_SOURCES = {CrossrefSource.OPENALEX}


class Verdict(str, Enum):
    VERIFIED = "verified"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"


def classify(resolution: Resolution) -> Verdict:
    best_score = resolution.best.match_score if resolution.best else 0.0

    if best_score >= VERIFIED_THRESHOLD:
        return Verdict.VERIFIED

    searched_everywhere = set(resolution.sources_ok) == _ALL_SOURCES
    if best_score < NOT_FOUND_THRESHOLD and searched_everywhere:
        return Verdict.NOT_FOUND

    return Verdict.AMBIGUOUS
