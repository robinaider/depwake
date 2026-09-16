# Security policy

Depwake **reads** your manifests and queries public registries (npm, PyPI,
OSV) over HTTPS. It writes only the manifest files you point `apply` at
(with numbered `.bak` backups), and never sends your code anywhere.

## Reporting a vulnerability

**Please do not open a public issue for security reports.** Disclose privately via
https://github.com/robinaider/depwake/security/advisories/new
so we can fix before details go public.

Please include a minimal repro and the version (`depwake --version`).
We aim to acknowledge within 72 hours and share a fix plan within 14 days,
and will credit reporters in `CHANGELOG.md` unless you ask otherwise.
We follow coordinated vulnerability disclosure: please allow up to 90 days
before public disclosure of the vulnerability.

## Supported versions

| Version | Supported |
|---|---|
| Latest PyPI release (`pip install -U depwake`) | ✅ |
| Older releases | ⚠️ best-effort — please upgrade, re-test, and re-report |

## Scope notes

- `depwake plan`/`verify` never modify anything.
- `depwake apply` modifies only manifests under the given root, backs them
  up first, and never bumps majors. Review the `--dry-run` output first.
