"""Core data model for extraction."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ExtractionSource(str, Enum):
    BBL = "bbl"
    PDF = "pdf"


class Identifiers(BaseModel):
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    url: Optional[str] = None


class Reference(BaseModel):
    """One extracted reference, normalized."""

    ref_id: str  # stable within a paper, e.g. the bib key or an index
    raw_string: str
    title: Optional[str] = None
    authors: list[str] = Field(default_factory=list)  # given-leading display names
    year: Optional[int] = None
    venue: Optional[str] = None  # journal, book, or conference/proceedings
    identifiers: Identifiers = Field(default_factory=Identifiers)
    source: ExtractionSource = ExtractionSource.BBL
