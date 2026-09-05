"""Tests for citebot.crossref.base's scoring helpers — pure functions, no network."""

from citebot.crossref.base import Candidate, CrossrefSource, author_overlap, score
from citebot.models import Identifiers, Reference


def _ref(**kwargs) -> Reference:
    return Reference(ref_id="r1", raw_string="", **kwargs)


def _candidate(**kwargs) -> Candidate:
    return Candidate(source=CrossrefSource.OPENALEX, **kwargs)


def test_author_overlap_none_when_either_list_empty():
    assert author_overlap([], ["Alice Smith"]) is None
    assert author_overlap(["Alice Smith"], []) is None


def test_author_overlap_fraction_of_shared_surnames():
    assert author_overlap(["Alice Smith", "Bob Jones"], ["Bob Jones"]) == 0.5


def test_id_match_with_agreeing_content_scores_high():
    ref = _ref(title="Attention Is All You Need", authors=["Ashish Vaswani"], year=2017,
               identifiers=Identifiers(arxiv_id="1706.03762"))
    candidate = _candidate(title="Attention Is All You Need", authors=["Ashish Vaswani"], year=2017,
                            identifiers=Identifiers(doi="10.48550/arxiv.1706.03762"))
    score(ref, candidate)
    assert candidate.match_score >= 0.9


def test_id_match_with_conflicting_content_does_not_score_as_verified():
    # A DOI/arXiv id lookup only proves the candidate exists at that id, not
    # that it's the paper the reference claims — a wrong/fabricated id
    # pointing at a real but unrelated paper must not score as a match.
    ref = _ref(title="Attention Is All You Need", authors=["Ashish Vaswani"], year=2017,
               identifiers=Identifiers(arxiv_id="1706.03762"))
    candidate = _candidate(title="A Survey of Deep Learning in Agriculture", authors=["John Doe"], year=2019,
                            identifiers=Identifiers(doi="10.48550/arxiv.1706.03762"))
    score(ref, candidate)
    assert candidate.match_score < 0.7
    assert candidate.author_score == 0.0
