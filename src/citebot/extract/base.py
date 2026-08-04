"""Extractor protocol so PDF/arXiv/LaTeX backends are interchangeable."""

from __future__ import annotations

from typing import Protocol

from citebot.models import Reference


class Extractor(Protocol):
    def extract(self, source: str) -> list[Reference]:
        """Return normalized references for the given source (id or path)."""
        ...
