"""Tests for citebot.classify — pure function, no network required.

The `resolve` fan-out in citebot.crossref hits real APIs and isn't covered
here; these tests exercise the verdict thresholds against synthetic
Resolutions instead.
"""

from citebot.classify import ConflictReason, Verdict, classify
from citebot.crossref.base import Candidate, CrossrefSource, Resolution

ALL_SOURCES = [CrossrefSource.OPENALEX]


def _resolution(
    *,
    match_score: float | None,
    sources_ok: list[CrossrefSource],
    title_score: float = 0.0,
    author_score: float | None = None,
) -> Resolution:
    best = (
        Candidate(
            source=CrossrefSource.OPENALEX,
            match_score=match_score,
            title_score=title_score,
            author_score=author_score,
        )
        if match_score is not None
        else None
    )
    return Resolution(ref_id="r1", candidates=[best] if best else [], best=best, sources_ok=sources_ok)


def test_high_score_is_verified():
    res = _resolution(match_score=0.9, sources_ok=[CrossrefSource.OPENALEX])
    assert classify(res).verdict == Verdict.VERIFIED


def test_low_score_with_full_coverage_is_conflict():
    res = _resolution(match_score=0.05, sources_ok=ALL_SOURCES)
    result = classify(res)
    assert result.verdict == Verdict.CONFLICT
    assert result.reason == ConflictReason.NO_CANDIDATE


def test_low_score_with_source_down_is_ambiguous():
    # OpenAlex itself errored out — no evidence at all, not enough to accuse.
    res = _resolution(match_score=0.05, sources_ok=[])
    assert classify(res).verdict == Verdict.AMBIGUOUS


def test_no_candidates_with_source_down_is_ambiguous():
    res = _resolution(match_score=None, sources_ok=[])
    assert classify(res).verdict == Verdict.AMBIGUOUS


def test_no_candidates_with_full_coverage_is_conflict():
    res = _resolution(match_score=None, sources_ok=ALL_SOURCES)
    result = classify(res)
    assert result.verdict == Verdict.CONFLICT
    assert result.reason == ConflictReason.NO_CANDIDATE


def test_middling_score_is_ambiguous():
    res = _resolution(match_score=0.4, sources_ok=ALL_SOURCES, title_score=0.4)
    assert classify(res).verdict == Verdict.AMBIGUOUS


def test_title_match_with_no_author_overlap_is_conflict():
    # Title clearly identifies a real paper, but its authors don't back up
    # the claim — a specific, high-confidence mismatch, not just a middling
    # score.
    res = _resolution(match_score=0.54, sources_ok=ALL_SOURCES, title_score=0.9, author_score=0.0)
    result = classify(res)
    assert result.verdict == Verdict.CONFLICT
    assert result.reason == ConflictReason.AUTHOR_MISMATCH


def test_title_match_with_no_ref_authors_is_ambiguous():
    # Same strong title match, but author_score is None because our own
    # extraction never got a ref author list to compare — that's a gap in
    # our evidence, not proof the citation is wrong.
    res = _resolution(match_score=0.54, sources_ok=ALL_SOURCES, title_score=0.9, author_score=None)
    assert classify(res).verdict == Verdict.AMBIGUOUS
