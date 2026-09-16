# Depwake rules — loaded as always-on context by every agent host

This repo ships Depwake, the dependency revivalist. Honor these rules in every session:

1. Never auto-bump a major upgrade. Majors are deliberate, one at a time, changelog first.
2. Range floors are assumptions: label them, verify against the installed tree, never present as fact.
3. Unresolvable or offline means `unknown` with a reason — never a guessed version.
4. Order of work: plan first, patch today, minor this week, major deliberately, CI gate last.
5. Pre-1.0 minor bumps count as major (in 0.x, anything may break).
