"""Event and health notifications for the Nepal Disaster Lab.

Sends alerts when jobs fail, sources go offline, or station counts drop.
Configure channels via environment variables — no credentials in source code.

Supported channels (all optional):
  NEPAL_NOTIFY_WEBHOOK   — HTTPS URL (Slack/Discord/generic webhook)
  NEPAL_NOTIFY_EMAIL     — SMTP: smtp://user:pass@host:port/to@recipient
  NEPAL_NOTIFY_LOG       — Path to append structured notification log (default: state/notifications.sqlite)
"""
from __future__ import annotations
import contextlib
import datetime as dt
import json
import os
import smtplib
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

UTC = dt.timezone.utc
SCHEMA = '''
CREATE TABLE IF NOT EXISTS notifications(
  id INTEGER PRIMARY KEY,
  event_type TEXT NOT NULL,
  message TEXT NOT NULL,
  channels TEXT NOT NULL,
  sent_at TEXT NOT NULL,
  status TEXT NOT NULL,
  detail TEXT
);
'''
_lock = threading.Lock()


def _now() -> str:
    return dt.datetime.now(UTC).isoformat(timespec='seconds')


def _db_path(state: Path | None = None) -> Path:
    if state is None:
        from operations import state_root  # lazy import to avoid circular
        state = state_root()
    return Path(state) / 'notifications.sqlite'


def _ensure_schema(db_path: Path) -> None:
    with contextlib.closing(sqlite3.connect(db_path, timeout=10)) as db, db:
        db.executescript(SCHEMA)


def _log(db_path: Path, event_type: str, message: str, channels: list[str],
         status: str, detail: str | None = None) -> None:
    _ensure_schema(db_path)
    with contextlib.closing(sqlite3.connect(db_path, timeout=10)) as db, db:
        db.execute(
            'INSERT INTO notifications(event_type,message,channels,sent_at,status,detail) VALUES(?,?,?,?,?,?)',
            (event_type, message, json.dumps(channels), _now(), status, detail)
        )


def _send_webhook(url: str, event_type: str, message: str) -> None:
    """POST a JSON payload to the webhook URL."""
    payload = json.dumps({'event': event_type, 'message': message,
                          'sent_at': _now(), 'source': 'TerraRaksha'}).encode()
    req = urllib.request.Request(url, data=payload,
                                 headers={'Content-Type': 'application/json',
                                          'User-Agent': 'TerraRaksha/1.0'},
                                 method='POST')
    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status >= 400:
            raise RuntimeError(f'Webhook returned {resp.status}')


def _send_email(dsn: str, event_type: str, message: str) -> None:
    """Send via SMTP using a DSN: smtp://user:pass@host:port/to@recipient"""
    parsed = urllib.parse.urlparse(dsn)
    host = parsed.hostname or 'localhost'
    port = parsed.port or 587
    user = urllib.parse.unquote(parsed.username or '')
    password = urllib.parse.unquote(parsed.password or '')
    to_addr = urllib.parse.unquote(parsed.path.lstrip('/'))
    if not to_addr:
        raise ValueError('Email DSN must include recipient address in path')
    subject = f'[TerraRaksha] {event_type}'
    body = f'Subject: {subject}\r\nFrom: {user}\r\nTo: {to_addr}\r\n\r\n{message}\r\nSent: {_now()}\r\n'
    with smtplib.SMTP(host, port, timeout=15) as smtp:
        smtp.starttls()
        if user:
            smtp.login(user, password)
        smtp.sendmail(user or 'noreply@terraraksha', [to_addr], body.encode())


def notify(event_type: str, message: str, channels: list[str] | None = None,
           state: Path | None = None) -> dict:
    """Send a notification to all configured channels.

    Args:
        event_type: Short machine-readable label (e.g. 'job_failure').
        message: Human-readable description.
        channels: Optional override list. Defaults to env-configured channels.
        state: Optional state directory for the notification log.

    Returns:
        dict with 'sent', 'failed', and 'skipped' counts.
    """
    if channels is None:
        channels = []
        if os.environ.get('NEPAL_NOTIFY_WEBHOOK'):
            channels.append('webhook')
        if os.environ.get('NEPAL_NOTIFY_EMAIL'):
            channels.append('email')
        channels.append('log')  # Always log locally.

    db_path = _db_path(state)
    results = {'sent': 0, 'failed': 0, 'skipped': 0}
    errors = []

    with _lock:
        for channel in channels:
            try:
                if channel == 'webhook':
                    url = os.environ.get('NEPAL_NOTIFY_WEBHOOK', '')
                    if not url:
                        results['skipped'] += 1
                        continue
                    _send_webhook(url, event_type, message)
                    results['sent'] += 1
                elif channel == 'email':
                    dsn = os.environ.get('NEPAL_NOTIFY_EMAIL', '')
                    if not dsn:
                        results['skipped'] += 1
                        continue
                    _send_email(dsn, event_type, message)
                    results['sent'] += 1
                elif channel == 'log':
                    _log(db_path, event_type, message, channels, 'ok')
                    results['sent'] += 1
                else:
                    results['skipped'] += 1
            except Exception as exc:
                errors.append(f'{channel}: {exc}')
                results['failed'] += 1
                try:
                    _log(db_path, event_type, message, [channel], 'error', str(exc))
                except Exception:
                    pass

    if errors:
        results['errors'] = errors
    return results


def recent(state: Path | None = None, limit: int = 50) -> list[dict]:
    """Return the most recent notification records."""
    db_path = _db_path(state)
    if not db_path.exists():
        return []
    _ensure_schema(db_path)
    with contextlib.closing(sqlite3.connect(db_path, timeout=10)) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            'SELECT * FROM notifications ORDER BY id DESC LIMIT ?', (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
