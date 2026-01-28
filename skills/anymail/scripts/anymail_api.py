"""Programmatic helper for driving AnyMail CLI.

This is *not* a Clawdbot tool by itself; it is a reusable library you can call from
other scripts/tests. It provides:
- a stable way to run AnyMail from the repo venv
- helpers to enforce JSON output and parse it

Keep this deterministic and side-effect explicit.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence


@dataclass
class RunResult:
    ok: bool
    code: int
    stdout: str
    stderr: str
    json: Optional[Any] = None


def find_repo_root(start: Optional[Path] = None) -> Path:
    start = (start or Path(__file__)).resolve()
    # <repo>/skills/anymail/scripts/anymail_api.py
    return start.parents[3]


def choose_python(repo_root: Path) -> str:
    venv_py = repo_root / ".venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        return str(venv_py)
    return "python"


def run_anymail(args: Sequence[str], *, repo_root: Optional[Path] = None, timeout_s: int = 120) -> RunResult:
    repo_root = repo_root or find_repo_root()
    py = choose_python(repo_root)

    cmd = [py, "-m", "anymail.cli", *args]
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")

    p = subprocess.run(
        cmd,
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )

    res = RunResult(ok=p.returncode == 0, code=p.returncode, stdout=p.stdout or "", stderr=p.stderr or "")

    # best-effort JSON parse if it looks like JSON
    out = (p.stdout or "").strip()
    if out.startswith("{") or out.startswith("["):
        try:
            res.json = json.loads(out)
        except Exception:
            pass

    return res


def ensure_flag(args: list[str], flag: str) -> list[str]:
    if flag not in args:
        return [*args, flag]
    return args


def run_json(args: Sequence[str], **kw: Any) -> RunResult:
    # Prefer --json where supported; safe to append if already present.
    a = list(args)
    if "--json" not in a and "--format" not in a:
        a.append("--json")
    return run_anymail(a, **kw)
