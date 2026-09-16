# Security policy

Depwake **reads** your manifests and queries public registries (npm, PyPI,
OSV) over HTTPS. It writes only the manifest files you point `apply` at
(with numbered `.bak` backups), and never sends your code anywhere.

## Reporting a vulnerability

Open a GitHub issue titled `[security] …` (or email the maintainer address
listed on the repo). Please include a minimal repro. We aim to acknowledge
within 72 hours and will credit reporters in `CHANGELOG.md` unless you ask
otherwise.

## Scope notes

- `depwake plan`/`verify` never modify anything.
- `depwake apply` modifies only manifests under the given root, backs them
  up first, and never bumps majors. Review the `--dry-run` output first.
