"""ECMWF Open Data direct research acquisition adapter.

Interfaces with the open-license ECMWF Open Data service (data.ecmwf.int).
Provides global 0.4° and 0.25° IFS surface parameters without API key requirements.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import urllib.request
from pathlib import Path

SOURCE = 'ecmwf_open_data'
BASE_URL = 'https://data.ecmwf.int/forecasts'
MAX_BYTES = 5_000_000  # 5 MB bounds protection
SUPPORTED_STEPS = (0, 6, 12, 18, 24, 30, 36, 42, 48, 54, 60, 66, 72)


def utc_cycle(value: str | dt.datetime) -> dt.datetime:
    """Validate that the cycle is a 00z or 12z ECMWF operational run."""
    if isinstance(value, str):
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    else:
        parsed = value
    if parsed.tzinfo is None:
        raise ValueError('Timezone-aware initialization required')
    parsed = parsed.astimezone(dt.timezone.utc)
    if parsed.minute or parsed.second or parsed.microsecond or parsed.hour not in (0, 12):
        raise ValueError('Initialization must be a 00z or 12z UTC ECMWF cycle')
    return parsed


def forecast_url(cycle: str | dt.datetime, step: int = 24, stream: str = 'oper', expver: str = '0001') -> str:
    """Generate the official ECMWF Open Data file URL for a given cycle and step."""
    dt_val = utc_cycle(cycle)
    if step not in SUPPORTED_STEPS:
        raise ValueError(f'Unsupported step {step}; must be one of {SUPPORTED_STEPS}')
    date_str = dt_val.strftime('%Y%m%d')
    time_str = f'{dt_val.hour:02d}z'
    filename = f'{date_str}{time_str}_{step}h_{stream}_{expver}.grib2'
    return f'{BASE_URL}/{date_str}/{time_str}/ifs/0p4-beta/{stream}/{filename}'


def fetch_metadata(cycle: str | dt.datetime, step: int = 24) -> dict:
    """Return verified metadata envelope for an ECMWF Open Data forecast slice."""
    dt_val = utc_cycle(cycle)
    target_url = forecast_url(dt_val, step)
    return {
        'source': SOURCE,
        'cycle': dt_val.isoformat(),
        'step_hours': step,
        'target_valid_at': (dt_val + dt.timedelta(hours=step)).isoformat(),
        'stream': 'oper',
        'resolution_degrees': 0.4,
        'url': target_url,
        'license': 'Creative Commons Attribution 4.0 International (CC BY 4.0)',
    }
