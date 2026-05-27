"""Shared builder utilities for the integration fixtures.

Each fixture module defines:
    NAME: str                    # filesystem-safe, used as the fixture id
    def build() -> Project       # construct the in-memory Project

Keep individual fixtures small and exercise ONE concept each.
"""

from __future__ import annotations

from datetime import UTC, datetime

# Canonical session start used across all fixtures so the scheduler's
# date math is reproducible: Monday 2026-06-01 13:00 UTC.
START = datetime(2026, 6, 1, 13, 0, tzinfo=UTC)


def utc(year: int, month: int, day: int, hour: int = 13, minute: int = 0) -> datetime:
    """Build a tz-aware UTC datetime — required by `_iso()`."""
    return datetime(year, month, day, hour, minute, tzinfo=UTC)
