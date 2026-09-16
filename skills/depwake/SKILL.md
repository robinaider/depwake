---
name: depwake
description: Revive stale dependencies — risk-grouped upgrade plan, safe auto-bumps, never touch majors. Use when returning to an old project, before upgrades, in CI to gate major drift, or when asked to update dependencies.
allowed-tools: Bash Read Glob Grep Edit
---

# Depwake — wake your sleeping dependencies

You are the maintainer who inherited a 3-year-old side project and lived.
Rules: never auto-bump a major. Never present a range floor as an installed
fact. Offline or unresolvable means `unknown`, never a guess.

## Ladder (first rung that holds)

1. **Inventory.** `depwake plan <root>` — all manifests, grouped by risk.
2. **Safe wins first.** `depwake apply <root> --dry-run`, review, then apply (patch only).
3. **This week.** Re-run with `--include-minor` for the minor tier.
4. **Deliberately.** Majors get a changelog-reading session, one at a time, newest-last.
5. **Gate it.** `depwake plan --fail-on major` in CI so drift never silently returns.

## Commands

```bash
depwake plan <root> [--format text|markdown|json] [--fail-on major|minor|patch|never]
depwake plan <root> -o UPGRADE.md --format markdown   # report to file
depwake apply <root> [--include-minor] [--dry-run]
depwake verify <root> [--strict]                      # facts vs assumptions, offline
```

Config (`depwake.toml`, package.json `depwake` key, or pyproject `[tool.depwake]`):
`ignore = [...]` for pinned-forever deps, `fail_on` default gate. Flags win.

## Reporting back

- Lead with counts (X patch / Y minor / Z major), not the full list.
- Every major gets: current → latest, registry link, and the honest one-liner on why it matters.
- Floor-sourced rows (`[floor]`) get a verify-against-installed-tree warning.
- `unknown` rows are a TODO list (add a lockfile), not a failure.
