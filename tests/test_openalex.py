"""Tests for citebot.crossref.openalex's query construction — offline, no network.

OpenAlex's filter= syntax breaks on unescaped commas (filter separator) and
on ?/* (wildcard operators, invalid on the stemmed title.search field);
these lock in that _search_by_title strips them before building the query.
"""

from citebot.crossref.openalex import _FILTER_BREAKING_CHARS


def test_strips_comma_and_wildcard_chars():
    assert _FILTER_BREAKING_CHARS.sub(" ", "Learning accurate, compact, and interpretable tree annotation") == (
        "Learning accurate  compact  and interpretable tree annotation"
    )
    assert _FILTER_BREAKING_CHARS.sub(" ", "Can active memory replace attention?") == (
        "Can active memory replace attention "
    )


def test_leaves_ordinary_titles_untouched():
    title = "Attention is all you need: a survey"
    assert _FILTER_BREAKING_CHARS.sub(" ", title) == title
