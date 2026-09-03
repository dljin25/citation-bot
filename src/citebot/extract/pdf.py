"""Extract raw bibliography text from a NeurIPS paper PDF.

NeurIPS papers are single-column with a numbered, natbib-style bibliography,
so plain text extraction (no layout analysis needed) is enough to isolate
the References section, which is then handed off to citebot.parse.bibliography
for splitting into entries and parsing.

The pipeline is three steps:
    PDF -> full text -> just the bibliography -> one Reference per entry
"""

from __future__ import annotations

import re # regex
from pathlib import Path

from pypdf import PdfReader

from citebot.models import Reference
from citebot.parse import bibliography

# regex patterns

REFERENCES_HEADING = re.compile(r"^\s*(?:\d+\.?\s+)?(references|bibliography)\s*$", re.IGNORECASE | re.MULTILINE)

# The paper's own top-level banner for post-bibliography content: closed,
# stable vocabulary (NeurIPS mandates "NeurIPS Paper Checklist" verbatim;
# "Appendix"/"Supplementary Material" are the conventional banners before it).
NEXT_SECTION_KEYWORD = re.compile(r"appendix|checklist|supplementary material", re.IGNORECASE)

# Papers that skip the banner and open straight on a lettered appendix
# section (LaTeX's \appendix restarts numbering as A, B, C, ...) - matches
# e.g. "A Ethics Statement", "B Broader Impact and Limitations". Unlike
# NEXT_SECTION_KEYWORD this doesn't need to know the section's name.
LETTERED_SECTION_HEADING = re.compile(r"^[A-Z]\s+[A-Z][a-z]+(?:\s+[A-Za-z]+){0,6}\s*$", re.MULTILINE)

PAGE_NUMBER_LINE = re.compile(r"^\s*\d{1,4}\s*$", re.MULTILINE)


def _references_section(text: str) -> str:
    """Return just the bibliography.

    That is the text between the "References" heading and whichever section
    comes after it. Returns "" if the paper has no References heading.
    """
    heading = REFERENCES_HEADING.search(text)
    if not heading:
        return ""

    section = text[heading.end():]

    for page_break in PAGE_NUMBER_LINE.finditer(section):
        window = section[page_break.end():page_break.end() + 120]
        # NOTE: keyword match does not need to be the first word, so
        # "NeurIPS Paper Checklist" and "In this Supplementary Material" are
        # both valid.
        if NEXT_SECTION_KEYWORD.search(window) or LETTERED_SECTION_HEADING.search(window):
            return section[:page_break.start()]

    return section


def extract(pdf_path: str | Path) -> list[Reference]:
    """Read a paper PDF and return every reference in its bibliography."""
    reader = PdfReader(str(pdf_path))

    pages = []
    for page in reader.pages:
        # extract_text() returns None on pages with no text layer.
        pages.append(page.extract_text() or "")
    text = "\n".join(pages)

    section = _references_section(text)
    return bibliography.parse(section)
