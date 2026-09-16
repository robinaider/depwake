#!/usr/bin/env bash
# Depwake 60-second demo — plan, gate, and dry-run on fixtures. Needs network
# for live registry data (or pass --offline to see graceful degradation).
set -u
cd "$(dirname "$0")"
if command -v depwake >/dev/null 2>&1; then
  D="depwake"
else
  export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"  # zero-install fallback
  D="python3 -m depwake"
fi

echo "=== 1/4  verify: facts vs assumptions ==="
$D verify examples/stale-project/
echo
echo "=== 2/4  plan: risk groups + advisories ==="
$D plan examples/stale-project/ || true
echo
echo "=== 3/4  gate: fail while majors pend ==="
$D plan examples/stale-project/ --fail-on major > /dev/null || echo "(exit 1 — majors pending, as designed)"
echo
echo "=== 4/4  apply: safe preview, majors untouched ==="
$D apply examples/stale-project/ --dry-run
echo
echo "Done. Your repo next: depwake plan .  |  depwake apply . --dry-run"
