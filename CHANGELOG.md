# Changelog — all notable changes, newest first.

## [0.3.1] — scorecard hardening
### Added
- OpenSSF Scorecard push: SHA-pinned Actions, minimal tokens, injection-free
  action, Dependabot (actions/pip), CodeQL (Python), self-score workflow,
  Sigstore-attested releases with PyPI OIDC trusted publishing.
- `docs/SCORECARD.md`: per-check evidence table + repo-settings click-list.

## [0.3.0] — smooth
### Added
- Colors (TTY-aware, NO_COLOR respected, never in pipes), stderr progress
  with timings, `--quiet`.
- Config file (`depwake.toml`, package.json key, or pyproject tool table):
  `ignore` list + `fail_on` default. CLI flags always win; ignores noted.
- `-o/--output` report files, JSON `counts` + `advisory_count`,
  `--min-severity` display filter (Unscored always shown — unknown ≠ safe).
- Apply next-step hints (refresh lockfiles, re-plan).

## [0.2.0] — trust
### Added
- OSV advisory enrichment: batch detect + full records, severity labels,
  fixed-in versions, 🔒 sorting/counts, Markdown security section.
- Registry cache (~/.cache/depwake, 1h TTL): ~7s → ~1s on 44 deps.
- `--offline` (graceful unknown) and `--no-advisories` / `--no-cache` escapes.
- `verify`: facts-vs-assumptions report + `--strict` gate, no network.
- requirements `-r` includes (+cycles), continuations, markers; pyproject
  optional groups honestly noted; partial floors padded ("2" → 2.0.0);
  two-part real versions parsed ("3.19"); zero-dep projects exit 0.
- GitHub Action, pre-commit hook, CI matrix, `demo.sh`, `benchmarks/BENCH.md`.

## [0.1.0]
### Added
- `plan`: risk-grouped upgrades (patch/minor/major/unknown) across
  package.json (+lock/shrinkwrap), requirements.txt, pyproject.toml.
- `apply`: patch-only auto-bumps (opt-in minor), numbered .bak backups,
  majors never touched, `--dry-run`.
- Markdown (PR-ready), JSON, and `--fail-on` CI gate.
- Skill (`skills/depwake/SKILL.md`) + AGENTS.md. Stdlib only.
