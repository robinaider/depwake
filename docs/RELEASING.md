# Releasing Depwake

1. Bump version in `pyproject.toml` and `src/depwake/__init__.py`.
2. Add a `CHANGELOG.md` entry (honest numbers only — see `benchmarks/BENCH.md`).
3. Full verify: fresh venv → `pip install -e .` → `unittest discover` →
   `bash demo.sh`.
4. Tag `vX.Y.Z`, push, create GitHub Release from the CHANGELOG entry.
5. Preferred: let `release.yml` publish — PyPI via OIDC trusted publishing
   (one-time setup: PyPI → project → Publishing → add GitHub publisher
   for this repo + workflow).
6. Post-release: confirm `pip install depwake==X.Y.Z` works from a clean
   machine and the pre-commit hook `rev:` still resolves.
