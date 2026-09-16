"""Safe auto-bumps: patch (default) and optionally minor. Never major.

Rules, in order:
1. Only items whose risk is included AND whose current version is exact
   (lockfile or == pin). Range floors are assumptions — listed, not touched.
2. package.json: keep the range prefix, replace the version triple
   (^4.17.0 -> ^4.17.21). requirements/pyproject: only == pins.
3. Numbered .bak backups, never clobbered. --dry-run changes nothing.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .plan import Plan

TRIPLE = re.compile(r"\d+\.\d+\.\d+[^,\s|]*")


@dataclass
class ApplyResult:
    changed: list[str] = field(default_factory=list)   # "file: name old -> new"
    skipped: list[str] = field(default_factory=list)   # "name: reason"
    backups: list[str] = field(default_factory=list)


def _backup(path: Path) -> Path:
    dest = path.with_suffix(path.suffix + ".bak")
    i = 1
    while dest.exists():
        dest = Path(f"{path}.bak.{i}")
        i += 1
    dest.write_bytes(path.read_bytes())
    return dest


def _bump_npm_range(rng: str, latest: str) -> str | None:
    if not TRIPLE.search(rng):
        return None
    return TRIPLE.sub(latest, rng, count=1)


def apply_plan(root: str | Path, plan: Plan, include: set[str] | None = None,
               dry_run: bool = False) -> ApplyResult:
    include = include or {"patch"}
    root = Path(root)
    res = ApplyResult()
    eligible = [i for i in plan.items
                if i.risk in include
                and i.latest
                and i.dep.current_source in ("lock", "pin")]
    for item in plan.items:
        if item not in eligible:
            if item.risk in ("major",):
                n = len(item.advisories)
                extra = f" — ⚠ {n} open advisor{'y' if n == 1 else 'ies'}, plan it soon" if n else ""
                res.skipped.append(f"{item.dep.name}: major — upgrade deliberately, never auto-bumped{extra}")
            elif item.risk == "unknown":
                res.skipped.append(f"{item.dep.name}: unknown version — resolve first ({item.note})")
            elif item.risk in include:
                res.skipped.append(f"{item.dep.name}: current is a range floor, not exact — add a lockfile")
            continue
    by_file: dict[Path, list] = {}
    for item in eligible:
        if item.dep.ecosystem == "npm":
            by_file.setdefault(root / "package.json", []).append(item)
        else:
            req = root / "requirements.txt"
            proj = root / "pyproject.toml"
            by_file.setdefault(req if req.exists() else proj, []).append(item)
    for path, items in by_file.items():
        if not path.exists():
            for item in items:
                res.skipped.append(f"{item.dep.name}: {path.name} not found")
            continue
        if not dry_run:
            res.backups.append(str(_backup(path)))
        text = path.read_text(encoding="utf-8")
        for item in items:
            d = item.dep
            assert item.latest
            if path.name == "package.json":
                data = json.loads(text)
                done = False
                for section in ("dependencies", "devDependencies",
                                "peerDependencies", "optionalDependencies"):
                    if d.name in (data.get(section) or {}):
                        new = _bump_npm_range(data[section][d.name], item.latest)
                        if new and new != data[section][d.name]:
                            data[section][d.name] = new
                            res.changed.append(f"{path.name}: {d.name} {d.current} -> {item.latest}")
                            done = True
                text = json.dumps(data, indent=2) + "\n"
                if not done:
                    res.skipped.append(f"{d.name}: range {d.wanted!r} has no version triple to bump")
            else:
                new_text, n = re.subn(
                    rf"(?m)^(\s*{re.escape(d.name)}\s*==\s*){re.escape(d.current or '')}\s*$",
                    rf"\g<1>{item.latest}", text, count=1)
                if n:
                    text = new_text
                    res.changed.append(f"{path.name}: {d.name} {d.current} -> {item.latest}")
                else:
                    res.skipped.append(f"{d.name}: pin line not found or not ==")
        if not dry_run:
            path.write_text(text, encoding="utf-8")
    return res


def format_apply(res: ApplyResult, dry_run: bool = False) -> str:
    head = "depwake apply (dry run — nothing written):" if dry_run else "depwake apply:"
    lines = [head]
    for c in res.changed:
        lines.append(f"  BUMP {c}")
    for s in res.skipped:
        lines.append(f"  SKIP {s}")
    for b in res.backups:
        lines.append(f"  backup: {b}")
    if not res.changed:
        lines.append("  nothing to bump.")
    return "\n".join(lines)
