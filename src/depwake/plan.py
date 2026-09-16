"""Upgrade planning: deps + latest versions -> risk-grouped plan."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from .manifests import Dep
from .registry import Advisory, Latest, fetch, fetch_advisories
from .semver import RISK_BLURB, classify, parse

ORDER = {"major": 0, "minor": 1, "patch": 2, "same": 3, "unknown": 4}
SEV_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Unscored": 4}


@dataclass
class Item:
    dep: Dep
    latest: str | None
    url: str
    risk: str            # major | minor | patch | same | unknown
    note: str = ""       # why this row needs attention (or why we can't tell)
    advisories: list[Advisory] = field(default_factory=list)

    def worst_severity(self) -> str:
        if not self.advisories:
            return ""
        return min((a.severity for a in self.advisories),
                   key=lambda s: SEV_ORDER.get(s, 9))

    def to_dict(self) -> dict:
        return {"name": self.dep.name, "ecosystem": self.dep.ecosystem,
                "wanted": self.dep.wanted, "current": self.dep.current,
                "current_source": self.dep.current_source,
                "latest": self.latest, "url": self.url,
                "risk": self.risk, "note": self.note,
                "advisories": [a.to_dict() for a in self.advisories]}


@dataclass
class Plan:
    items: list[Item]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        counts = self.counts()
        return {"items": [i.to_dict() for i in self.items], "notes": self.notes,
                "counts": counts, "advisory_count": self.advisory_count()}

    def grouped(self) -> dict[str, list[Item]]:
        groups: dict[str, list[Item]] = {k: [] for k in ORDER}
        for item in sorted(self.items,
                           key=lambda i: (ORDER[i.risk], not i.advisories,
                                          i.dep.ecosystem, i.dep.name.lower())):
            groups[item.risk].append(item)
        return groups

    def counts(self) -> dict[str, int]:
        out = {k: 0 for k in ORDER}
        for item in self.items:
            out[item.risk] += 1
        return out

    def advisory_count(self) -> int:
        return sum(len(i.advisories) for i in self.items)


def _security_note(item: Item) -> str:
    n = len(item.advisories)
    worst = item.worst_severity()
    top = sorted(item.advisories, key=lambda a: SEV_ORDER.get(a.severity, 9))[0]
    fixed = f"fixed in {top.fixed_in}" if top.fixed_in else "no fix published yet"
    return (f"🔒 {n} advisor{'y' if n == 1 else 'ies'} (worst {worst}): "
            f"{top.id} — {fixed}")


def build(deps: list[Dep],
          fetcher: Callable[[str, str], Latest] = fetch,
          timeout: float = 10.0,
          advisory_fetcher: Callable[[list[tuple[str, str, str]]],
                                     dict[tuple[str, str], list[Advisory]]]
          | None = fetch_advisories,
          with_advisories: bool = True,
          min_severity: str | None = None) -> Plan:
    items: list[Item] = []
    for dep in deps:
        if dep.current is None:
            items.append(Item(dep, None, "", "unknown",
                              "no lockfile pin and no parseable range floor — "
                              "add a lockfile for exact tracking"))
            continue
        current = parse(dep.current)
        if current is None:
            items.append(Item(dep, None, "", "unknown",
                              f"unparseable current version {dep.current!r}"))
            continue
        try:
            got = fetcher(dep.ecosystem, dep.name)
        except Exception as exc:  # a fetcher must never kill a plan
            got = Latest(None, "", f"lookup failed: {exc}")
        if not got.version:
            items.append(Item(dep, None, got.url, "unknown", got.error or "lookup failed"))
            continue
        latest = parse(got.version)
        if latest is None:
            items.append(Item(dep, got.version, got.url, "unknown",
                              f"unparseable latest version {got.version!r}"))
            continue
        risk = classify(current, latest)
        note = ""
        if risk == "same" and dep.current_source == "floor":
            note = "range floor looks current, but without a lockfile this is an assumption"
        elif risk != "same" and dep.current_source == "floor":
            note = "computed from range floor (no lockfile) — verify against installed tree"
        items.append(Item(dep, str(latest), got.url, risk, note or RISK_BLURB[risk]))
    plan = Plan(items)
    if with_advisories and advisory_fetcher is not None:
        try:
            adv = advisory_fetcher([(i.dep.ecosystem, i.dep.name, i.dep.current or "")
                                    for i in items if i.dep.current])
        except Exception:
            adv = {}
        # Unscored advisories always survive the filter: unknown != safe.
        threshold = SEV_ORDER.get(min_severity or "Unscored", 4)
        hidden = 0
        for item in items:
            found = adv.get((item.dep.ecosystem, item.dep.name), [])
            kept = [a for a in found
                    if a.severity == "Unscored" or SEV_ORDER.get(a.severity, 9) <= threshold]
            hidden += len(found) - len(kept)
            if kept:
                item.advisories = kept
                item.note = f"{_security_note(item)}. {item.note}".strip()
        if hidden:
            plan.notes.append(f"{hidden} advisor{'y' if hidden == 1 else 'ies'} "
                              f"below --min-severity {min_severity} hidden")
    return plan
