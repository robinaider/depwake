# Contributing to Depwake

Small, reviewable PRs. No permission needed to start.

## Fastest first PRs
1. **New manifest format** (poetry.lock, yarn.lock, Gemfile…) — one parser + fixtures + tests.
2. **New ecosystem fetcher** (crates.io, RubyGems…) — one function in `registry.py` + stubbed tests.
3. **Advisory enrichment** — surface `npm audit` / `pip-audit` data inside the risk groups.
4. **Translations** — `README.<lang>.md`.

## Rules
- Stdlib only in `src/depwake/`.
- Every feature ships with a test (stub the registry — tests never touch network).
- Never auto-bump majors, never guess versions.
- MIT; PRs are MIT-licensed too.

## Dev loop
```bash
python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m depwake plan /tmp/depdemo
```
