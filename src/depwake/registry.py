"""Latest-version lookup over plain HTTPS. Stdlib only.

Injectable fetch() keeps everything deterministic in tests and lets future
versions plug caches/mirrors without touching callers.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass

UA = "depwake/0.2.0"
OSV_ECO = {"npm": "npm", "pypi": "PyPI"}


@dataclass
class Latest:
    version: str | None
    url: str          # registry/homepage link for the "why" column
    error: str = ""   # non-empty when lookup failed (offline, 404, ...)


def _get(url: str, timeout: float) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": "depwake/0.1.0",
                                               "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except Exception as exc:  # network, TLS, 404, timeout — all just "unknown"
        return 0, str(exc).encode()


def fetch_npm(name: str, timeout: float = 10.0) -> Latest:
    status, body = _get(f"https://registry.npmjs.org/{name}/latest", timeout)
    if status != 200:
        return Latest(None, f"https://www.npmjs.com/package/{name}",
                      f"npm registry: HTTP {status or 'unreachable'}")
    try:
        version = json.loads(body).get("version")
    except json.JSONDecodeError:
        version = None
    if not version:
        return Latest(None, f"https://www.npmjs.com/package/{name}", "no version field")
    return Latest(version, f"https://www.npmjs.com/package/{name}")


def fetch_pypi(name: str, timeout: float = 10.0) -> Latest:
    base = name.split("[")[0]
    status, body = _get(f"https://pypi.org/pypi/{base}/json", timeout)
    if status != 200:
        return Latest(None, f"https://pypi.org/project/{base}/",
                      f"PyPI: HTTP {status or 'unreachable'}")
    try:
        info = json.loads(body).get("info", {})
    except json.JSONDecodeError:
        return Latest(None, f"https://pypi.org/project/{base}/", "bad JSON")
    version = info.get("version")
    url = info.get("home_page") or info.get("project_url") or f"https://pypi.org/project/{base}/"
    if not version:
        return Latest(None, url, "no version field")
    return Latest(version, url)


def fetch(ecosystem: str, name: str, timeout: float = 10.0) -> Latest:
    if ecosystem == "npm":
        return fetch_npm(name, timeout)
    return fetch_pypi(name, timeout)


@dataclass
class Advisory:
    id: str
    summary: str
    severity: str   # Critical | High | Medium | Low | Unscored
    score: float | None
    fixed_in: str | None  # None when no fixed version published
    url: str

    def to_dict(self) -> dict:
        return {"id": self.id, "summary": self.summary, "severity": self.severity,
                "score": self.score, "fixed_in": self.fixed_in, "url": self.url}


def _label(score: float | None) -> str:
    if score is None:
        return "Unscored"
    if score >= 9.0:
        return "Critical"
    if score >= 7.0:
        return "High"
    if score >= 4.0:
        return "Medium"
    if score > 0:
        return "Low"
    return "Unscored"


def _fixed_in(vuln: dict) -> str | None:
    """Latest 'fixed' event across affected ranges, or None."""
    fixed: list[str] = []
    for aff in vuln.get("affected", []):
        for rng in aff.get("ranges", []):
            for ev in rng.get("events", []):
                if "fixed" in ev:
                    fixed.append(str(ev["fixed"]))
    return sorted(set(fixed))[-1] if fixed else None


def _advisory(vuln: dict) -> Advisory:
    scores = [s.get("score") for s in (vuln.get("severity") or [])
              if isinstance(s.get("score"), (int, float))]
    score = max(scores) if scores else None
    summary = (vuln.get("summary") or "")[:160]
    vid = vuln.get("id", "unknown")
    return Advisory(vid, summary, _label(score), score,
                    _fixed_in(vuln), f"https://osv.dev/vulnerability/{vid}")


def fetch_advisories(deps: list[tuple[str, str, str]],
                     timeout: float = 10.0) -> dict[tuple[str, str], list[Advisory]]:
    """Map (ecosystem, name) -> advisories affecting that exact version.

    One batch call to find who is affected, then one full-record call per
    affected dep. Any failure degrades to {} — advisories inform, never gate.
    """
    queries = [{"package": {"name": n.split("[")[0],
                            "ecosystem": OSV_ECO.get(e, e)}, "version": v}
               for e, n, v in deps]
    if not queries:
        return {}
    payload = json.dumps({"queries": queries}).encode()
    req = urllib.request.Request("https://api.osv.dev/v1/querybatch", data=payload,
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            batch = json.loads(resp.read()).get("results", [])
    except Exception:
        return {}
    out: dict[tuple[str, str], list[Advisory]] = {}
    for (eco, name, ver), res in zip([(e, n, v) for e, n, v in deps], batch):
        if not res.get("vulns"):
            continue
        single = json.dumps({"package": {"name": name.split("[")[0],
                                         "ecosystem": OSV_ECO.get(eco, eco)},
                             "version": ver}).encode()
        req = urllib.request.Request("https://api.osv.dev/v1/query", data=single,
                                     headers={"Content-Type": "application/json",
                                              "User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                full = json.loads(resp.read()).get("vulns", [])
            out[(eco, name)] = [_advisory(v) for v in full]
        except Exception:
            out[(eco, name)] = []
    return out
