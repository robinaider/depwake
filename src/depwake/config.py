"""Project config: depwake.toml > package.json \"depwake\" key > pyproject [tool.depwake].

Keys:
  ignore  = ["pkg", ...]   deps to exclude from every plan (with a note)
  fail_on = "major"        default gate when --fail-on isn't passed

Explicit CLI flags always win over config. Unknown keys are ignored, not
errors — configs must never break a plan.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any


def load(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    cfg: dict[str, Any] = {}
    toml = root / "depwake.toml"
    if toml.exists():
        try:
            cfg.update(tomllib.loads(toml.read_bytes().decode("utf-8", errors="replace")))
        except (ValueError, OSError):
            pass
        return _clean(cfg)
    pkg = root / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            if isinstance(data.get("depwake"), dict):
                cfg.update(data["depwake"])
                return _clean(cfg)
        except (ValueError, OSError):
            pass
    proj = root / "pyproject.toml"
    if proj.exists():
        try:
            data = tomllib.loads(proj.read_bytes().decode("utf-8", errors="replace"))
            tool = (data.get("tool") or {}).get("depwake")
            if isinstance(tool, dict):
                cfg.update(tool)
        except (ValueError, OSError):
            pass
    return _clean(cfg)


def _clean(cfg: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    ignore = cfg.get("ignore", [])
    if isinstance(ignore, list):
        out["ignore"] = sorted({str(x).lower() for x in ignore if str(x).strip()})
    fail_on = cfg.get("fail_on")
    if fail_on in ("major", "minor", "patch", "never"):
        out["fail_on"] = fail_on
    return out
