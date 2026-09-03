"""Tests for citebot.classify — pure function, no network required.

The `resolve` fan-out in citebot.crossref hits real APIs and isn't covered
here; these tests exercise the verdict thresholds against synthetic
Resolutions instead.
"""

from citebot.classify import Verdict, classify
from citebot.crossref.base import Candidate, CrossrefSource, Resolution

ALL_SOURCES = [CrossrefSource.OPENALEX]


def _resolution(*, match_score: float | None, sources_ok: list[CrossrefSource]) -> Resolution:
    best = Candidate(source=CrossrefSource.OPENALEX, match_score=match_score) if match_score is not None else None
    return Resolution(ref_id="r1", candidates=[best] if best else [], best=best, sources_ok=sources_ok)


def test_high_score_is_verified():
    res = _resolution(match_score=0.9, sources_ok=[CrossrefSource.OPENALEX])
    assert classify(res) == Verdict.VERIFIED


def test_low_score_with_full_coverage_is_not_found():
    res = _resolution(match_score=0.05, sources_ok=ALL_SOURCES)
    assert classify(res) == Verdict.NOT_FOUND


def test_low_score_with_source_down_is_ambiguous():
    # OpenAlex itself errored out — no evidence at all, not enough to accuse.
    res = _resolution(match_score=0.05, sources_ok=[])
    assert classify(res) == Verdict.AMBIGUOUS


def test_no_candidates_with_source_down_is_ambiguous():
    res = _resolution(match_score=None, sources_ok=[])
    assert classify(res) == Verdict.AMBIGUOUS


def test_no_candidates_with_full_coverage_is_not_found():
    res = _resolution(match_score=None, sources_ok=ALL_SOURCES)
    assert classify(res) == Verdict.NOT_FOUND


def test_middling_score_is_ambiguous():
    res = _resolution(match_score=0.4, sources_ok=ALL_SOURCES)
    assert classify(res) == Verdict.AMBIGUOUS
