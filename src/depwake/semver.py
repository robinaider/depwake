"""Semver parsing + risk classification. No network, no opinions beyond semver."""

from __future__ import annotations

import re
from dataclasses import dataclass

VER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def parse(v: str | None) -> Version | None:
    """Parse X.Y.Z, tolerating leading v and partial real-world versions
    ("3.19" -> 3.19.0, "2" -> 2.0.0). Non-numeric (latest, *) -> None."""
    if not v:
        return None
    v = v.strip()
    m = VER.match(v)
    if m:
        return Version(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r"^v?(\d+)(?:\.(\d+))?$", v)
    if m:
        return Version(int(m.group(1)), int(m.group(2) or 0), 0)
    return None


def classify(current: Version, latest: Version) -> str:
    """patch | minor | major | same. Pre-1.0 minors count as major:
    in 0.x, semver says anything may break."""
    if (current.major, current.minor, current.patch) >= \
       (latest.major, latest.minor, latest.patch):
        return "same"
    if current.major != latest.major:
        return "major"
    if current.major == 0 and current.minor != latest.minor:
        return "major"
    if current.minor != latest.minor:
        return "minor"
    return "patch"


RISK_BLURB = {
    "patch": "Safe fixes only — apply today.",
    "minor": "Features + fixes, backwards compatible — apply this week.",
    "major": "May break — read the changelog, upgrade deliberately.",
    "same": "Up to date.",
}
