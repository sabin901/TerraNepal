"""Shared helpers for the Nepal Disaster Lab modules.

Import from here instead of duplicating across data.py, cases.py, exposure.py etc.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import math

UTC = dt.timezone.utc


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def now() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return dt.datetime.now(UTC).isoformat(timespec='seconds')


def timestamp(value) -> float | None:
    """Convert an ISO-8601 string to a UTC POSIX timestamp, or None on failure."""
    try:
        t = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return t.timestamp() if t.tzinfo is not None else None
    except (ValueError, TypeError):
        return None


def stamp(value: str) -> str:
    """Validate and normalise a timezone-aware ISO-8601 timestamp to UTC.

    Raises ValueError for naive timestamps or unparseable strings.
    """
    if not isinstance(value, str):
        raise ValueError('Expected timezone-aware timestamp')
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('Invalid timestamp') from exc
    if parsed.tzinfo is None:
        raise ValueError('Timestamp requires timezone')
    return parsed.astimezone(UTC).isoformat()


def epoch(value: str) -> float:
    """Return POSIX timestamp for a timezone-aware ISO-8601 string."""
    return dt.datetime.fromisoformat(stamp(value)).timestamp()


def iso(t: float) -> str:
    """Return UTC ISO-8601 for a POSIX timestamp."""
    return dt.datetime.fromtimestamp(t, UTC).isoformat(timespec='seconds')


# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------

def number(value) -> bool:
    """True iff value is a finite non-boolean number."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def finite(value) -> bool:
    """Like number() but suppresses OverflowError for exotic numeric subclasses."""
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


# ---------------------------------------------------------------------------
# JSON / hashing helpers
# ---------------------------------------------------------------------------

def canonical(value) -> str:
    """Deterministic compact JSON serialisation (sorted keys, no NaN)."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def digest(value) -> str:
    """SHA-256 hex digest of the canonical JSON representation."""
    return hashlib.sha256(canonical(value).encode()).hexdigest()


# sha is an alias matching the name used in cases.py
sha = digest
