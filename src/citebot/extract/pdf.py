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

REFERENCES_HEADING = re.compile(r"^\s*references\s*$", re.IGNORECASE | re.MULTILINE)

NEXT_SECTION_HEADING = re.compile(r"^\s*(appendix|checklist|supplementary material)\b", re.IGNORECASE | re.MULTILINE)


def _references_section(text: str) -> str:
    """Return just the bibliography.

    That is the text between the "References" heading and whichever section
    comes after it. Returns "" if the paper has no References heading.
    """
    heading = REFERENCES_HEADING.search(text)
    if not heading:
        return ""

    section = text[heading.end():]

    # Stop at the next heading. If there isn't one, the bibliography runs
    # to the end of the document.
    next_heading = NEXT_SECTION_HEADING.search(section)
    if not next_heading:
        return section
    return section[:next_heading.start()]


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
