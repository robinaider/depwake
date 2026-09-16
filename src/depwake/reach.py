"""Reachability: is a vulnerable dep actually imported anywhere we can see?

An advisory for a package you never import is still worth patching — but
it can wait behind the one you `import` on every request. v1 is deliberately
narrow and honest about blind spots:

- pypi: stdlib `ast` over `*.py` (static imports only).
- npm: regex over `require()` / `import` / `import()` in js/ts sources.
- Dynamic imports (`importlib`, `eval(require(x))`, plugins) are invisible:
  anything unmapped is "unknown", never "safe". Unknown != safe.
"""

from __future__ import annotations

import ast
import fnmatch
import re
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
             "dist", "build", ".tox", ".pytest_cache", ".eggs", "vendor"}

JS_IMPORT = re.compile(
    r"""(?:require\s*\(\s*["']([^"'"]+)["']\s*\))"""
    r"""|(?:import\s+(?:[^'"]*?\s+from\s+)?["']([^"'"]+)["']\s*)"""
    r"""|(?:import\s*\(\s*["']([^"'"]+)["']\s*\))"""
)

# import-name -> dist-name where they differ (stdlib-clean, extend by PR).
PY_ALIASES = {
    "PIL": "pillow", "yaml": "pyyaml", "dateutil": "python-dateutil",
    "sklearn": "scikit-learn", "bs4": "beautifulsoup4",
    "Crypto": "pycryptodome", "cv2": "opencv-python", "jwt": "pyjwt",
    "serial": "pyserial", "magic": "python-magic", "gi": "pygobject",
    "attr": "attrs", "dotenv": "python-dotenv",
}


def _norm_pypi(name: str) -> str:
    return name.lower().replace("-", "_")


def _norm_dist(name: str) -> str:
    return name.lower().replace("_", "-")


def _walk(root: Path, exts: tuple[str, ...]):
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix not in exts:
            continue
        if any(part in SKIP_DIRS or fnmatch.fnmatchcase(part, "*.egg-info")
               for part in p.parts):
            continue
        if p.stat().st_size > 500000:
            continue
        yield p


def _py_imports(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, ValueError, OSError):
        return set()
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level or not node.module:
                continue  # relative import: our own code, not a dep
            out.add(node.module.split(".")[0])
    return out


def _js_spec(spec: str) -> str | None:
    if spec.startswith((".", "/", "http:", "https:", "#")):
        return None
    if spec.startswith("@"):
        parts = spec.split("/")
        return "/".join(parts[:2]) if len(parts) >= 2 else spec
    return spec.split("/")[0]


def _js_imports(path: Path) -> set[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    out: set[str] = set()
    for m in JS_IMPORT.finditer(text):
        spec = next((g for g in m.groups() if g), None)
        if spec:
            norm = _js_spec(spec)
            if norm:
                out.add(norm)
    return out


def collect(root: str | Path) -> dict[str, dict[str, int]]:
    """Map ecosystem -> {imported name -> files importing it}."""
    base = Path(root)
    found: dict[str, dict[str, int]] = {"pypi": {}, "npm": {}}
    if not base.is_dir():
        return found
    for p in _walk(base, (".py",)):
        for name in _py_imports(p):
            found["pypi"][name] = found["pypi"].get(name, 0) + 1
    for p in _walk(base, (".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs")):
        for name in _js_imports(p):
            found["npm"][name] = found["npm"].get(name, 0) + 1
    return found


def lookup(dep_name: str, ecosystem: str,
           imported: dict[str, dict[str, int]]) -> tuple[bool | None, str]:
    """(reachable?, evidence). None = unknown, and unknown != safe."""
    table = imported.get(ecosystem, {})
    if ecosystem == "pypi":
        cands = {_norm_pypi(dep_name)}
        for imp, dist in PY_ALIASES.items():
            if _norm_dist(dist) == _norm_dist(dep_name):
                cands.add(imp)
                cands.add(_norm_pypi(imp))
        for c in cands:
            for imp, n in table.items():
                if _norm_pypi(imp) == c:
                    return True, f"imported as {imp!r} in {n} file(s)"
        if not table:
            return None, "no Python source scanned"
        return False, "not imported anywhere we can see"
    # npm: names match 1:1 (scopes preserved).
    if dep_name in table:
        return True, f"imported in {table[dep_name]} file(s)"
    if not table:
        return None, "no JS/TS source scanned"
    return False, "not imported anywhere we can see"
