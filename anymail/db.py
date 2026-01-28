"""SQLite database for CLI invocation logging (agent monitoring)."""

import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from .config import get_config_dir, ensure_config_dir

# Sensitive option names: their values are redacted in stored argv
_SENSITIVE_OPTIONS = frozenset({"--body", "-b", "--attach", "--password", "-p"})
# -p is profile, not password; password is from getpass. So only --body and --attach content redact.
# Actually -p is profile. So sensitive: --body, --attach (we can store filenames or redact; redact to be safe).


def get_db_path() -> Path:
    """Path to the SQLite log database."""
    return get_config_dir() / "anymail.db"


def _get_connection() -> sqlite3.Connection:
    ensure_config_dir()
    path = get_db_path()
    conn = sqlite3.connect(str(path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the log table if it does not exist."""
    with _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cli_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                command TEXT NOT NULL,
                args_json TEXT,
                profile TEXT,
                outcome TEXT NOT NULL,
                error_message TEXT,
                duration_ms INTEGER
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cli_logs_ts ON cli_logs(ts)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cli_logs_command ON cli_logs(command)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cli_logs_outcome ON cli_logs(outcome)"
        )


def sanitize_argv(argv: List[str]) -> List[str]:
    """Redact sensitive values in argv (e.g. --body content, attachment paths)."""
    out: List[str] = []
    i = 0
    sensitive_flags = frozenset({"--body", "--attach"})
    while i < len(argv):
        arg = argv[i]
        out.append(arg)
        if arg in sensitive_flags and i + 1 < len(argv):
            out.append("[REDACTED]")
            i += 1
        i += 1
    return out


def insert_log(
    command: str,
    args_json: Optional[str] = None,
    profile: Optional[str] = None,
    outcome: str = "success",
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> int:
    """Insert a log entry. Returns row id."""
    init_db()
    ts = datetime.utcnow().isoformat() + "Z"
    with _get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO cli_logs (ts, command, args_json, profile, outcome, error_message, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (ts, command, args_json, profile, outcome, error_message, duration_ms),
        )
        conn.commit()
        return cur.lastrowid or 0


def query_logs(
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    command: Optional[str] = None,
    outcome: Optional[str] = None,
    profile: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Query log entries. Returns list of dicts with keys id, ts, command, args_json, profile, outcome, error_message, duration_ms."""
    init_db()
    conditions: List[str] = []
    params: List[Any] = []
    if since is not None:
        conditions.append("ts >= ?")
        params.append(since.strftime("%Y-%m-%dT%H:%M:%S"))
    if until is not None:
        conditions.append("ts <= ?")
        params.append(until.strftime("%Y-%m-%dT%H:%M:%S"))
    if command is not None:
        conditions.append("command = ?")
        params.append(command)
    if outcome is not None:
        conditions.append("outcome = ?")
        params.append(outcome)
    if profile is not None:
        conditions.append("profile = ?")
        params.append(profile)
    where = " AND ".join(conditions) if conditions else "1=1"
    params.extend([limit, offset])
    with _get_connection() as conn:
        cur = conn.execute(
            f"""
            SELECT id, ts, command, args_json, profile, outcome, error_message, duration_ms
            FROM cli_logs
            WHERE {where}
            ORDER BY ts DESC
            LIMIT ? OFFSET ?
            """,
            params,
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


@contextmanager
def log_invocation(
    argv: List[str],
    invoked_command_path: str,
    profile_used: Optional[str] = None,
) -> Iterator[None]:
    """Context manager that logs CLI invocation on exit (success or failure)."""
    start = time.perf_counter()
    args_sanitized = sanitize_argv(argv)
    args_json = json.dumps(args_sanitized, ensure_ascii=False)
    try:
        yield
        outcome = "success"
        error_message = None
    except Exception as e:
        outcome = "error"
        error_message = str(e)
        raise
    finally:
        duration_ms = int((time.perf_counter() - start) * 1000)
        try:
            insert_log(
                command=invoked_command_path,
                args_json=args_json,
                profile=profile_used,
                outcome=outcome,
                error_message=error_message,
                duration_ms=duration_ms,
            )
        except Exception:
            pass  # Do not fail the CLI if logging fails
