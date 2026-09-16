"""Manifest parsing: package.json (+ lock), requirements.txt, pyproject.toml.

Every dep becomes a Dep(name, ecosystem, wanted, current, current_source):
- wanted: the range/pin written in the manifest.
- current: the actually-installed version (lockfile) or the range floor
  when no lock exists — always labeled via current_source so plans never
  present guesses as facts.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Dep:
    name: str
    ecosystem: str  # "npm" | "pypi"
    wanted: str
    current: str | None       # None when unresolvable
    current_source: str       # "lock" | "pin" | "floor" | "unknown"


REQ_LINE = re.compile(r"^\s*([A-Za-z0-9_.\-]+(?:\[[A-Za-z0-9_,\-]+\])?)\s*(.*)$")
REQ_PIN = re.compile(r"==\s*([^;\s]+)")
REQ_FLOOR = re.compile(r"(?:>=|~=|>|===)\s*([^;\s,]+)")


def _normalize_floor(v: str | None) -> str | None:
    """Pad partial floors ("2" -> 2.0.0) so >=2,<4 yields a usable floor.

    Still labeled `floor` downstream — padding is arithmetic, not knowledge.
    """
    if not v:
        return None
    v = v.strip().rstrip(".*")
    parts = v.split(".")
    if not all(p.isdigit() for p in parts) or len(parts) > 3:
        return None
    return ".".join(parts + ["0"] * (3 - len(parts)))


def _floor_npm_range(rng: str) -> str | None:
    """Best-effort floor of an npm range: ^4.17.0 -> 4.17.0, * -> None."""
    rng = rng.strip()
    if not rng or rng in ("*", "latest", "x"):
        return None
    m = re.search(r"(\d+\.\d+\.\d+[^,\s|]*)", rng)
    return m.group(1) if m else None


def parse_package_json(root: Path) -> list[Dep]:
    manifest = json.loads((root / "package.json").read_text(encoding="utf-8"))
    wanted: dict[str, str] = {}
    for section in ("dependencies", "devDependencies",
                    "peerDependencies", "optionalDependencies"):
        wanted.update(manifest.get(section, {}) or {})
    locked = _read_npm_lock(root)
    deps = []
    for name, rng in sorted(wanted.items()):
        if name in locked:
            deps.append(Dep(name, "npm", rng, locked[name], "lock"))
            continue
        floor = _floor_npm_range(rng)
        deps.append(Dep(name, "npm", rng, floor,
                        "floor" if floor else "unknown"))
    return deps


def _read_npm_lock(root: Path) -> dict[str, str]:
    lock = root / "package-lock.json"
    if not lock.exists():
        return {}
    try:
        data = json.loads(lock.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    out: dict[str, str] = {}
    packages = data.get("packages")
    if isinstance(packages, dict):  # lockfileVersion 2/3
        for path, meta in packages.items():
            if not path or not path.startswith("node_modules/"):
                continue
            name = path[len("node_modules/"):]
            if "/" not in name and meta.get("version"):
                out[name] = meta["version"]
    else:  # lockfileVersion 1
        for name, meta in (data.get("dependencies") or {}).items():
            if isinstance(meta, dict) and meta.get("version"):
                out[name] = meta["version"]
    # shrinkwrap twin
    shrink = root / "npm-shrinkwrap.json"
    if shrink.exists() and not out:
        try:
            data = json.loads(shrink.read_text(encoding="utf-8"))
            for name, meta in (data.get("dependencies") or {}).items():
                if isinstance(meta, dict) and meta.get("version"):
                    out[name] = meta["version"]
        except json.JSONDecodeError:
            pass
    return out


def parse_requirements(path: Path, _seen: set[Path] | None = None) -> list[Dep]:
    path = Path(path)
    _seen = _seen or set()
    if path in _seen:
        return []  # include cycle — report once, never loop
    _seen.add(path)
    deps: list[Dep] = []
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    # join continuations before parsing
    lines: list[str] = []
    buf = ""
    for line in raw.splitlines():
        if line.rstrip().endswith("\\"):
            buf += line.rstrip()[:-1]
            continue
        lines.append(buf + line)
        buf = ""
    if buf:
        lines.append(buf)
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-r ", "--requirement ", "-r\t", "--requirement=")):
            inc = line.split(None, 1)[1] if " " in line or "\t" in line \
                else line.split("=", 1)[1]
            deps.extend(parse_requirements(path.parent / inc.strip(), _seen))
            continue
        if line.startswith("-"):
            continue  # options (-c constraints, --index-url, ...) are out of scope
        m = REQ_LINE.match(line)
        if not m:
            continue
        name, spec = m.group(1), m.group(2).strip()
        # strip environment markers for version parsing ("pkg==1.0; python_version>'3'")
        spec = spec.split(";")[0].strip()
        pin = REQ_PIN.search(spec)
        if pin:
            deps.append(Dep(name, "pypi", spec or "any", pin.group(1), "pin"))
            continue
        mfloor = REQ_FLOOR.search(spec)
        floor = _normalize_floor(mfloor.group(1)) if mfloor else None
        deps.append(Dep(name, "pypi", spec or "any", floor,
                        "floor" if floor else "unknown"))
    return sorted(deps, key=lambda d: d.name.lower())


def parse_pyproject(path: Path) -> tuple[list[Dep], list[str]]:
    """Returns (deps, notes). Optional-dependency groups are reported in
    notes, not deps: counting uninstalled extras as stale would be noise."""
    try:
        data = tomllib.loads(path.read_bytes().decode("utf-8", errors="replace"))
    except (ValueError, OSError):
        return [], []
    notes: list[str] = []
    optional = data.get("project", {}).get("optional-dependencies", {}) or {}
    if optional:
        n = sum(len(v) for v in optional.values())
        notes.append(f"{n} optional deps ignored (extras: {', '.join(sorted(optional))})")
    reqs = data.get("project", {}).get("dependencies", []) or []
    deps = []
    for req in reqs:
        m = REQ_LINE.match(str(req).strip())
        if not m:
            continue
        name, spec = m.group(1), m.group(2).strip()
        spec = spec.split(";")[0].strip()
        pin = REQ_PIN.search(spec)
        if pin:
            deps.append(Dep(name, "pypi", spec, pin.group(1), "pin"))
            continue
        mfloor = REQ_FLOOR.search(spec)
        floor = _normalize_floor(mfloor.group(1)) if mfloor else None
        deps.append(Dep(name, "pypi", spec or "any", floor,
                        "floor" if floor else "unknown"))
    return sorted(deps, key=lambda d: d.name.lower()), notes


def discover(root: Path) -> tuple[list[Dep], list[str]]:
    """Collect deps from every supported manifest under root.

    Returns (deps, notes). Later manifests win on name collisions so the
    most specific pin (e.g. requirements.txt over pyproject) is reported.
    """
    root = Path(root)
    if not root.exists():
        raise ValueError(f"{root}: no such file or directory")
    found: dict[tuple[str, str], Dep] = {}
    notes: list[str] = []
    if (root / "package.json").exists():
        for d in parse_package_json(root):
            found[("npm", d.name)] = d
    else:
        notes.append("no package.json")
    reqs = root / "requirements.txt"
    if reqs.exists():
        for d in parse_requirements(reqs):
            found[("pypi", d.name)] = d
    else:
        notes.append("no requirements.txt")
    proj = root / "pyproject.toml"
    if proj.exists():
        pdeps, pnotes = parse_pyproject(proj)
        notes.extend(pnotes)
        for d in pdeps:
            found.setdefault(("pypi", d.name), d)
    else:
        notes.append("no pyproject.toml")
    manifests_seen = ((root / "package.json").exists() or reqs.exists()
                      or proj.exists())
    if not manifests_seen:
        raise ValueError(f"{root}: no supported manifest found "
                         "(package.json, requirements.txt, pyproject.toml)")
    if not found:
        notes.append("manifests present but declare zero dependencies")
    return sorted(found.values(), key=lambda d: (d.ecosystem, d.name.lower())), notes
