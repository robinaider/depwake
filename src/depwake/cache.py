"""Tiny file cache for registry lookups. Stdlib only.

Same TTL for version + advisory data: staleness here costs a delayed
upgrade notice, never a wrong one (versions only move forward; advisories
only accumulate — both refresh within the hour).
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

TTL = 3600


def cache_dir() -> Path:
    import os
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    d = Path(base) / "depwake"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(key: str) -> Path:
    return cache_dir() / (hashlib.sha256(key.encode()).hexdigest() + ".json")


def get(key: str, ttl: float = TTL) -> object | None:
    try:
        p = _path(key)
        if not p.exists() or time.time() - p.stat().st_mtime > ttl:
            return None
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def put(key: str, value: object) -> None:
    try:
        _path(key).write_text(json.dumps(value), encoding="utf-8")
    except OSError:
        pass  # cache is best-effort; a full disk must never break a plan
