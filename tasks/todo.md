- [x] Restate goal + acceptance criteria
- Goal: extend the Gradescope CLI with submission management and QoL commands backed by the installed `gradescopeapi` package.
- Acceptance criteria: support logging in, listing courses, listing assignments, uploading a submission, and at least two QoL commands for quickly inspecting account/course workload; verify commands against the live account where safe.

- [x] Locate existing implementation / patterns
- Read `gscli.py` plus installed package modules for login, assignment listing, upload, and submission-related helpers.

- [x] Design: minimal approach + key decisions
- Keep everything in `gscli.py` to minimize blast radius.
- Implement only student-safe features that are supported or reasonably derivable from the scraped data.
- Compute assignment `open` status locally from release/due/late-due windows because the package does not expose it.
- Avoid destructive verification; do not perform a real upload without explicit user request.

- [x] Implement smallest safe slice
- [x] Add `submit-assignment` command with file validation and optional leaderboard name.
- [x] Add QoL commands (`deadlines`, `whoami`) using existing login/course/assignment APIs.
- [x] Improve assignment display to show stable assignment IDs needed for submission.

- [ ] Add/adjust tests
- Not applicable; this is a live integration CLI. Verification is command-based.

- [x] Run verification (lint/tests/build/manual repro)
- Verified help output for new commands.
- Verified `list-courses`, `list-assignments -c 1200912 --open-only`, `deadlines --limit 8`, and `whoami` against the live account.
- Verified upload command argument validation with `submit-assignment --dry-run`.

- [x] Summarize changes + verification story
- [ ] Record lessons (if any)

Working Notes
- Package upload support exists via `gradescopeapi.classes.submission.upload_assignment`.
- Package submission listing helpers are mostly instructor-oriented; avoid promising unreliable student-side history features.
- `Assignment` objects expose `assignment_id`, not `id`; CLI should display that field.

Results
- Replaced the one-off probe with a fuller CLI in `gscli.py`.
- Added `submit-assignment`, `deadlines`, and `whoami` commands.
- Updated assignment output to show Gradescope assignment IDs plus submission status and score fields when present.
- Kept upload verification non-destructive by using `--dry-run`; no real submission was sent during verification.
