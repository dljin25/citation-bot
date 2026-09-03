"""Tests for citebot.extract.pdf's References-section boundary detection.

Exercises _references_section() directly against real NeurIPS PDFs in
tests/fixtures/ rather than the full extract() pipeline, so these don't
depend on anystyle-cli being installed. Each fixture stresses a different
trailing-section case: References followed by a Checklist, by nothing
(plain text/end of doc), by an Appendix, or by a lettered appendix section
("A Ethics Statement") with no generic Appendix banner first. The fifth
fixture (messy_entries) has a clean boundary already; it exists to stress
anystyle-cli's entry parsing rather than this boundary logic, so it's only
checked here for correct sectioning.

test_lettered_heading_generalizes_beyond_ethics_statement uses a synthetic
string (no fixture needed) to confirm LETTERED_SECTION_HEADING catches a
*different* section name than the one it was written against - the whole
point of matching structure instead of a growing keyword list.
"""

import re
from pathlib import Path

from pypdf import PdfReader

from citebot.extract.pdf import _references_section

FIXTURES = Path(__file__).parent / "fixtures"

ENTRY_MARKER = re.compile(r"\[(\d+)\]")


def _section_for(pdf_name: str) -> str:
    reader = PdfReader(str(FIXTURES / pdf_name))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return _references_section(text)


def test_checklist_after_references_is_excluded():
    section = _section_for("test1_checklist.pdf")
    markers = [int(m.group(1)) for m in ENTRY_MARKER.finditer(section)]
    assert markers == list(range(1, 28))
    assert "checklist" not in section.lower()


def test_plain_text_after_references_is_excluded():
    section = _section_for("test2_text.pdf")
    markers = [int(m.group(1)) for m in ENTRY_MARKER.finditer(section)]
    assert markers == list(range(1, 27))


def test_appendix_after_references_is_excluded():
    section = _section_for("test3_appendix.pdf")
    markers = [int(m.group(1)) for m in ENTRY_MARKER.finditer(section)]
    assert markers == list(range(1, 77))
    assert "appendix" not in section.lower()


def test_ethics_statement_after_references_is_excluded():
    section = _section_for("test4_ethics_statement.pdf")
    markers = [int(m.group(1)) for m in ENTRY_MARKER.finditer(section)]
    assert markers == list(range(1, 130))
    assert "ethics statement" not in section.lower()


def test_messy_entries_boundary_is_clean():
    section = _section_for("test5_messy_entries.pdf")
    markers = [int(m.group(1)) for m in ENTRY_MARKER.finditer(section)]
    assert markers == list(range(1, 138))


def test_bibliography_heading_with_section_number_is_found():
    text = (
        "7. Bibliography\n"
        "[1] Jane Doe. A paper about things. In Proceedings of Something, 2020.\n"
    )
    section = _references_section(text)
    markers = [int(m.group(1)) for m in ENTRY_MARKER.finditer(section)]
    assert markers == [1]


def test_lettered_heading_generalizes_beyond_ethics_statement():
    text = (
        "References\n"
        "[1] Jane Doe. A paper about things. In Proceedings of Something, 2020.\n"
        "[2] John Smith. Another paper. In Proceedings of Something Else, 2021.\n"
        "9\n"
        "B Broader Impact Statement\n"
        "This work may affect society in the following ways...\n"
    )
    section = _references_section(text)
    markers = [int(m.group(1)) for m in ENTRY_MARKER.finditer(section)]
    assert markers == [1, 2]
    assert "broader impact" not in section.lower()
