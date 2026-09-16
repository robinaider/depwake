#!/usr/bin/env bash
# Depwake 60-second demo — plan, gate, and dry-run on fixtures. Needs network
# for live registry data (or pass --offline to see graceful degradation).
#
# The stale project is GENERATED into a tmp dir, never committed: those pins
# are deliberately vulnerable (that's the demo), and committed vulnerable
# manifests would trip scanners on this repo itself. See examples/README.md.
set -u
cd "$(dirname "$0")"
if command -v depwake >/dev/null 2>&1; then
  D="depwake"
else
  export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"  # zero-install fallback
  D="python3 -m depwake"
fi

DEMO_DIR="$(mktemp -d "${TMPDIR:-/tmp}/depwake-demo.XXXXXX")"
trap 'rm -rf "$DEMO_DIR"' EXIT
cat > "$DEMO_DIR/package.json" <<'EOF'
{"dependencies": {"express": "^4.17.0", "lodash": "~4.17.20", "ms": "~2.1.2"}}
EOF
cat > "$DEMO_DIR/package-lock.json" <<'EOF'
{
  "name": "stale-project",
  "lockfileVersion": 3,
  "packages": {
    "": {},
    "node_modules/lodash": {"version": "4.17.20"},
    "node_modules/ms": {"version": "2.1.2"}
  }
}
EOF
cat > "$DEMO_DIR/requirements.txt" <<'EOF'
requests==2.28.0
six==1.16.0
EOF

echo "=== 1/4  verify: facts vs assumptions ==="
$D verify "$DEMO_DIR"
echo
echo "=== 2/4  plan: risk groups + advisories ==="
$D plan "$DEMO_DIR" || true
echo
echo "=== 3/4  gate: fail while majors pend ==="
$D plan "$DEMO_DIR" --fail-on major > /dev/null || echo "(exit 1 — majors pending, as designed)"
echo
echo "=== 4/4  apply: safe preview, majors untouched ==="
$D apply "$DEMO_DIR" --dry-run
echo
echo "Done. Your repo next: depwake plan .  |  depwake apply . --dry-run"
