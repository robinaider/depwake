# Benchmarks — honest numbers, reproducible method

> Every number here reproduces with one command against live registries
> (versions drift upward over time — direction matters, digits may move).
> If a claim doesn't reproduce, that's a bug — file it.

## Real-repo validation (measured 2026-09-12, depwake 0.2.0)

| Repo | Deps | Plan | Advisories | Cold | Warm (cache) |
|---|---|---|---|---|---|
| `psf/requests` (pyproject, floors) | 4 | 4 major, 28 🔒 | urllib3 alone: 20, oldest fixed in 2.6.0 | ~5s | ~1s |
| `pallets/click` (no runtime deps) | 0 | graceful "zero dependencies" note, exit 0 | — | <0.1s | — |
| `expressjs/express` (package.json, no lock) | 44 | 10 major / 4 minor / 9 patch / 0 unknown, 2 🔒 | — | ~7s | ~1s |

Notes:
- requests' urllib3 1.26 floor carries 20 advisories — the single best
  argument for this tool: the plan sorts the scariest row first.
- click proves the empty case: manifests present, zero deps → informative
  note, not an error, not a traceback.
- express (no lockfile) proves floors at scale: all 44 resolved, every row
  labeled `[floor]` with a verify warning. No lockfile, no pretending.
- Scoped packages verified (`@types/node` → 22.20.2); offline mode and
  cache TTL covered by unit tests (0.01s suite, zero network).
- OSV severity is often `Unscored` (GitHub doesn't always publish CVSS to
  OSV) — the label says so instead of inventing a Low.

## Known limitations (good first issues)

1. Optional-dependency groups are noted, not resolved (counting uninstalled
   extras would be noise).
2. npm aliases / git URLs resolve to `unknown` with reasons (no silent mislookup).
3. Advisory details fetch per affected dep — fine at project scale, could
   batch further for monorepos.
