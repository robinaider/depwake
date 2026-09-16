# Examples

There are no committed fixture projects here on purpose.

The demo (`demo.sh`) generates its stale project — deliberately vulnerable
pins like `requests==2.28.0` — into a tmp dir at runtime. Committing those
manifests would trip vulnerability scanners (including Scorecard's
Vulnerabilities check) on this repo itself. Tests do the same via tmp dirs.
