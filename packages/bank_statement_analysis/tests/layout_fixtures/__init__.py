"""Synthetic document-kind fixtures for the `layout/` classifier (Phase 2.2
cell C). See `kinds.py` for the generators and `builders.py` for the page
primitives. Nothing in this package reads a real document."""
from tests.layout_fixtures.kinds import FIXTURES, Expect, LayoutFixture, build, names

__all__ = ["FIXTURES", "Expect", "LayoutFixture", "build", "names"]
