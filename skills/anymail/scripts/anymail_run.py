"""Run AnyMail reliably from the repo.

Usage:
  python skills/anymail/scripts/anymail_run.py -- <anymail args...>

Examples:
  python skills/anymail/scripts/anymail_run.py -- doctor
  python skills/anymail/scripts/anymail_run.py -- inbox personal --unread --limit 20 --json

Behavior:
- Prefers the repo venv interpreter: <repo>/.venv/Scripts/python.exe
- Falls back to `python` on PATH.
- Executes `python -m anymail <args>` with cwd set to repo root.

Exit code matches the underlying command.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def find_repo_root() -> Path:
    # This file: <repo>/skills/anymail/scripts/anymail_run.py
    here = Path(__file__).resolve()
    return here.parents[3]


def choose_python(repo_root: Path) -> str:
    venv_py = repo_root / ".venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        return str(venv_py)
    return "python"


def main(argv: list[str]) -> int:
    if "--" in argv:
        idx = argv.index("--")
        args = argv[idx + 1 :]
    else:
        # allow calling without explicit --
        args = argv[1:]

    repo_root = find_repo_root()
    py = choose_python(repo_root)

    # AnyMail's CLI entrypoint lives in anymail/cli.py (module: anymail.cli).
    cmd = [py, "-m", "anymail.cli", *args]

    # Ensure predictable encoding on Windows terminals.
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")

    p = subprocess.run(cmd, cwd=str(repo_root), env=env)
    return int(p.returncode)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
