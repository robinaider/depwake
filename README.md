# Depwake ⏰

[![CI](https://github.com/robinaider/depwake/actions/workflows/ci.yml/badge.svg)](https://github.com/robinaider/depwake/actions/workflows/ci.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/robinaider/depwake/badge)](https://scorecard.dev/viewer/?uri=github.com/robinaider/depwake)

**Wake your sleeping dependencies.**

Your side project has 47 outdated packages, 3 security advisories, and a `package.json` from 2023. Dependabot spams you with 40 context-free PRs. Depwake does the opposite: one risk-grouped plan — patch today, minor this week, major deliberately — and safe auto-bumps for the boring parts.

```bash
pip install depwake
depwake plan ./my-project              # risk-grouped plan, Markdown/JSON too
depwake apply ./my-project --dry-run   # preview safe bumps (patch only)
depwake apply ./my-project             # bump patches, .bak backups, majors never touched
depwake verify ./my-project --strict   # facts vs assumptions, no network
```

> ⭐ If dependency hell has ever eaten your weekend, star this — it helps other devs find it.

Advisories included: every plan queries OSV and sorts 🔒 rows first —
urllib3 1.26 alone carries 20 advisories ([measured](benchmarks/BENCH.md)).

## Before / after

```bash
$ depwake plan ./my-project
depwake plan: 4 dep(s) — 1 major, 3 minor, 0 patch, 0 unknown
  MAJOR   npm  express 4.17.0 -> 5.2.1 [floor]
  MINOR   npm  lodash 4.17.20 -> 4.18.1 [floor]
  MINOR   pypi requests 2.28.0 -> 2.34.2
  MINOR   pypi six 1.16.0 -> 1.17.0
```

```bash
$ depwake plan ./my-project --format markdown > UPGRADE.md   # paste into a PR
$ depwake plan ./my-project --fail-on major                  # CI gate: exit 1 while majors pend
```

## Why not Dependabot / Renovate?

| | Depwake | Bots |
|---|---|---|
| Unit of work | one grouped plan, you decide the order | N noisy PRs, no prioritization |
| Risk language | patch today / minor this week / major deliberately | version numbers, you interpret |
| Honesty | range floors labeled `[floor]`; offline → `unknown`, never guessed | — |
| Scope | works without installs, lockfiles optional but rewarded | needs full install + config |
| Agent-native | `SKILL.md` your coding agent can run | docs page, if you're lucky |

Dependabot is a fine notifier. Depwake is the Sunday-morning plan *and* the safe pair of hands.

## Supported

`package.json` (+ `package-lock.json` / `npm-shrinkwrap.json`), `requirements.txt`, `pyproject.toml`. Pre-1.0 minors count as major (in 0.x, anything may break). Needs network for latest versions; offline degrades to `unknown`, never to guesses.

## Contributing — built for drive-by PRs

- 📦 New manifest format = one parser + fixtures (`good first issue`)
- 🔌 New ecosystem (crates.io, RubyGems…) = one fetcher + tests
- 🌍 Translations welcome (`README.<lang>.md`)
- Rules: stdlib only, every feature ships with a test, never auto-bump a major

## Roadmap

- [x] v0.1 — plan / apply, 3 manifest formats, Markdown + JSON + CI gate
- [x] v0.2 — OSV advisories, cache, `--offline`, `verify`, includes/markers/optionals, Action + CI + demo, real-repo validation
- [x] v0.3 — colors, progress, config file, `-o`, severity filter, JSON counts, apply hints
- [ ] Advisory reachability (is the vulnerable function even imported?)
- [ ] `depwake PR` — open the grouped upgrade as draft PRs per risk tier (needs GitHub)
- [ ] Lockfile generation for lockless projects (`--write-lock`)

## License

MIT — see [LICENSE](LICENSE).
