## What this PR does (one paragraph)

## Verification (commands you ran + output)
- [ ] `python3 -m unittest discover -s tests` green, hermetic (no network)
- [ ] Stubbed registry/advisories for new behavior (tests never touch network)
- [ ] `benchmarks/BENCH.md` updated if any number a user could quote changed

## Checklist
- [ ] Stdlib only in `src/depwake/` (no new dependencies)
- [ ] Never auto-bumps majors, never guesses versions
- [ ] Docs touched if flags/output changed (README, SKILL.md as needed)
