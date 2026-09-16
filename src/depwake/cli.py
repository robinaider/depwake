"""`depwake` CLI. Stdlib only. Exit codes: 0 clean, 1 findings, 2 usage."""

from __future__ import annotations

import argparse
import sys
import time

from . import __version__
from .apply import apply_plan, format_apply
from .cache import get as cache_get
from .cache import put as cache_put
from .color import enabled as color_enabled
from .config import load as load_config
from .manifests import discover
from .plan import build
from .registry import Latest, fetch, fetch_advisories
from .report import format_json, format_markdown, format_text

RISK_ORDER = {"major": 0, "minor": 1, "patch": 2}


def _version_fetcher(args: argparse.Namespace):
    def go(eco: str, name: str) -> Latest:
        if args.offline:
            return Latest(None, "", "offline mode (--offline)")
        key = f"latest:{eco}:{name}"
        if not args.no_cache:
            hit = cache_get(key)
            if isinstance(hit, dict) and "version" in hit:
                return Latest(hit.get("version"), hit.get("url", ""), hit.get("error", ""))
        got = fetch(eco, name, args.timeout)
        if not args.no_cache:
            cache_put(key, {"version": got.version, "url": got.url, "error": got.error})
        return got
    return go


def _advisory_fetcher(args: argparse.Namespace):
    def go(deps: list[tuple[str, str, str]]):
        if args.offline or args.no_advisories:
            return {}
        out: dict = {}
        missing = []
        for eco, name, ver in deps:
            key = f"osv:{eco}:{name}:{ver}"
            hit = None if args.no_cache else cache_get(key)
            if isinstance(hit, list):
                from .registry import Advisory
                out[(eco, name)] = [Advisory(**a) for a in hit]
            else:
                missing.append((eco, name, ver))
        if missing:
            fresh = fetch_advisories(missing, args.timeout)
            by_key = {(e, n): v for e, n, v in missing}
            for k, advs in fresh.items():
                out[k] = advs
                if not args.no_cache and k in by_key:
                    cache_put(f"osv:{k[0]}:{k[1]}:{by_key[k]}",
                              [a.to_dict() for a in advs])
        return out
    return go


def _shared_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--timeout", type=float, default=10.0, help="Registry timeout (s).")
    p.add_argument("--no-advisories", action="store_true", help="Skip OSV advisory lookup.")
    p.add_argument("--no-cache", action="store_true", help="Bypass the registry cache.")
    p.add_argument("--offline", action="store_true",
                   help="No network: versions/advisories become unknown with reasons.")
    p.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    p.add_argument("--quiet", action="store_true", help="Only the report on stdout.")


def _resolve_config(args: argparse.Namespace) -> tuple[list, list, list, str]:
    """Apply config file: ignore list + fail_on default.

    Returns (deps, notes, ignored_names, fail_on). Ignored deps vanish from
    counts but always leave a note — silent filtering would be lying by omission.
    """
    cfg = load_config(args.root)
    deps, notes = discover(args.root)
    ignored = sorted({d.name for d in deps if d.name.lower() in set(cfg.get("ignore", []))})
    if ignored:
        deps = [d for d in deps if d.name not in ignored]
        notes.append(f"ignored {len(ignored)} dep(s) per config: {', '.join(ignored)}")
    fail_on = args.fail_on if getattr(args, "fail_on", None) else cfg.get("fail_on", "never")
    return (deps, notes, ignored, fail_on)


def _say(args: argparse.Namespace, msg: str) -> None:
    if not args.quiet:
        print(f"depwake: {msg}", file=sys.stderr)


def cmd_plan(args: argparse.Namespace) -> int:
    try:
        deps, notes, _, fail_on = _resolve_config(args)
    except ValueError as exc:
        print(f"depwake: error: {exc}", file=sys.stderr)
        return 2
    color = color_enabled(args.color)
    _say(args, f"checking {len(deps)} dep(s)…")
    t0 = time.time()
    plan = build(deps, fetcher=_version_fetcher(args), timeout=args.timeout,
                 advisory_fetcher=_advisory_fetcher(args),
                 min_severity=args.min_severity,
                 reach_root=args.root if getattr(args, "reach", False) else None)
    plan.notes.extend(notes)
    _say(args, f"done in {time.time() - t0:.1f}s")
    if args.format == "json":
        rendered = format_json(plan)
    elif args.format == "markdown":
        rendered = format_markdown(plan, args.root)
    else:
        rendered = format_text(plan, color=color)
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(rendered if rendered.endswith("\n") else rendered + "\n",
                                     encoding="utf-8")
        print(f"wrote {args.output}")
        return 0 if fail_on == "never" else _gate(plan, fail_on)
    if args.format == "markdown":
        print(rendered, end="")
    else:
        print(rendered)
    if fail_on == "never":
        return 0
    return _gate(plan, fail_on)


def _gate(plan, fail_on: str) -> int:
    threshold = RISK_ORDER[fail_on]
    bad = [i for i in plan.items if i.risk in RISK_ORDER and RISK_ORDER[i.risk] <= threshold]
    return 1 if bad else 0


def cmd_apply(args: argparse.Namespace) -> int:
    try:
        deps, notes, _, _ = _resolve_config(args)
    except ValueError as exc:
        print(f"depwake: error: {exc}", file=sys.stderr)
        return 2
    _say(args, f"checking {len(deps)} dep(s)…")
    plan = build(deps, fetcher=_version_fetcher(args),
                 timeout=args.timeout, advisory_fetcher=_advisory_fetcher(args))
    include = {"patch"} | ({"minor"} if args.include_minor else set())
    res = apply_plan(args.root, plan, include=include, dry_run=args.dry_run)
    print(format_apply(res, dry_run=args.dry_run))
    if res.changed and not args.dry_run:
        npm = any(c.startswith("package.json") for c in res.changed)
        pypi = any(not c.startswith("package.json") for c in res.changed)
        hints = []
        if npm:
            hints.append("npm install  (refresh the lockfile)")
        if pypi:
            hints.append("pip install -r requirements.txt  (or reinstall your project)")
        hints.append("re-run depwake plan to confirm")
        print("  next: " + " → ".join(hints))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """How much of this project is exactly known? Facts (lock/pin) vs
    assumptions (range floors) vs blind spots (unknown). No network."""
    try:
        deps, notes = discover(args.root)
    except ValueError as exc:
        print(f"depwake: error: {exc}", file=sys.stderr)
        return 2
    exact = [d for d in deps if d.current_source in ("lock", "pin")]
    floors = [d for d in deps if d.current_source == "floor"]
    unknown = [d for d in deps if d.current_source == "unknown"]
    lines = [f"depwake verify: {len(exact)}/{len(deps)} exact, "
             f"{len(floors)} range-floor assumptions, {len(unknown)} unknown"]
    for d in floors:
        lines.append(f"  FLOOR   {d.ecosystem:4} {d.name} {d.wanted} (add a lockfile)")
    for d in unknown:
        lines.append(f"  UNKNOWN {d.ecosystem:4} {d.name} {d.wanted}")
    for note in notes:
        lines.append(f"  note: {note}")
    print("\n".join(lines))
    if args.strict and (floors or unknown):
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="depwake",
        description="Wake your sleeping dependencies — risk-grouped plans, safe auto-bumps.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    pl = sub.add_parser("plan", help="Risk-grouped upgrade plan (patch/minor/major/unknown).")
    pl.add_argument("root", nargs="?", default=".", help="Project directory.")
    pl.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    _shared_flags(pl)
    pl.add_argument("--fail-on", choices=["major", "minor", "patch", "never"], default=None,
                    help="Exit 1 if upgrades at/above this risk are pending "
                         "(default: config fail_on, else never).")
    pl.add_argument("-o", "--output", default=None, help="Write report to file instead of stdout.")
    pl.add_argument("--min-severity", choices=["Critical", "High", "Medium", "Low"], default=None,
                    help="Only attach advisories at/above this severity (Unscored always shown).")
    pl.add_argument("--reach", action="store_true",
                    help="Scan source for advisory reachability (who imports what).")
    pl.set_defaults(func=cmd_plan)

    ap = sub.add_parser("apply", help="Auto-bump patch (and optionally minor). Never major.")
    ap.add_argument("root", nargs="?", default=".")
    _shared_flags(ap)
    ap.add_argument("--include-minor", action="store_true", help="Also bump minor upgrades.")
    ap.add_argument("--dry-run", action="store_true", help="Show what would change.")
    ap.set_defaults(func=cmd_apply)

    vf = sub.add_parser("verify", help="Facts vs assumptions: lock/pin coverage, no network.")
    vf.add_argument("root", nargs="?", default=".")
    vf.add_argument("--strict", action="store_true",
                    help="Exit 1 unless every dep is exactly known.")
    vf.set_defaults(func=cmd_verify)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
