"""Citation-style detection shared by the arXiv and PDF extractors.

Commented out for now - both extractors currently give bare-bones support
for NeurIPS-style (numbered) papers only. Revisit later.
"""

# from __future__ import annotations
#
# import re
# from collections import Counter
# from enum import Enum
#
#
# class CitationStyle(str, Enum):
#     NUMBERED = "numbered"
#     AUTHOR_YEAR = "author_year"
#     UNKNOWN = "unknown"
#
#
# _NUMBERED_MARKER = re.compile(r"^\s*[\[(]?\d{1,3}[\])]?\.?\s*$")
#
# # Author-year entries lead with a capitalized surname (optionally an
# # initial-studded author list) and hit a four-digit year, often
# # parenthesized, within a short window.
# _AUTHOR_YEAR_LEAD = re.compile(
#     r"^\s*[A-Z][A-Za-z\-']+(?:,\s*[A-Z]\.[A-Za-z]*\.?)*"
#     r"(?:,|\s+and\s+|\s*&\s*|\s+et al\.?)?.{0,80}?\(?(19[5-9]\d|20[0-4]\d)[a-z]?\)?",
#     re.DOTALL,
# )
#
#
# def classify(snippet: str) -> CitationStyle:
#     """Classify a single entry's leading text as numbered or author-year.
#
#     ``snippet`` is either just the entry's lead-in marker (e.g. "[1]", a
#     .bbl ``\\bibitem`` optional label like "Smith, 2020") or the start of
#     the entry's raw text when no separate marker exists.
#     """
#     snippet = snippet.strip()
#     if not snippet:
#         return CitationStyle.UNKNOWN
#     if _NUMBERED_MARKER.match(snippet):
#         return CitationStyle.NUMBERED
#     if _AUTHOR_YEAR_LEAD.match(snippet):
#         return CitationStyle.AUTHOR_YEAR
#     return CitationStyle.UNKNOWN
#
#
# def dominant_style(snippets: list[str]) -> CitationStyle:
#     """Majority-vote style across several entries so one odd entry can't flip it."""
#     counts = Counter(classify(s) for s in snippets)
#     counts.pop(CitationStyle.UNKNOWN, None)
#     if not counts:
#         return CitationStyle.UNKNOWN
#     return counts.most_common(1)[0][0]
