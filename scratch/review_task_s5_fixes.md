Adversarial review — FINAL state of the S5 demo-recording work after the
previous review's findings were all fixed. Repo: _incubator/paypal-ai-hack-2026.

Previous review (20261012-141123) found: srt/video duration mismatch (fixed by
re-timing the recording to ~120s via an absolute `until(t)` schedule),
generate_token before bind (fixed — now after), GUID-named webm vs doc claim
(fixed — script renames to demo.webm), cross-repo playwright require (fixed —
local devDependency 1.57.0), missing content assertions (fixed — 5 checks),
tracker dup (fixed — upsert), unauthenticated /check undocumented (fixed —
comment), shared token file undocumented (fixed — comment), tracking-number
provenance wording (fixed — dispute fixture verified).

Now attack the FIXES themselves and anything still unverified:

1. scratch/record_demo.cjs — final version:
   - The `until(sec)` absolute-timeline schedule: any way it can drift badly
     (e.g. locator action slower than the remaining budget) such that acts
     land in wrong subtitle windows? Playwright's default action timeout could
     stall a beat — is there a failure mode that produces a misaligned but
     "successful" video?
   - Content assertions (disputeVisible/requestedBadge/baBefore/baAfter/
     fixNote): can they pass while the VIDEO still shows something wrong
     (e.g. assertion runs after a later re-render changed the DOM)? ZWSP
     stripping correct?
   - `fs.renameSync` picking "newest .webm that isn't demo.webm": race/stale
     file risk — could it rename an OLD leftover webm if the new recording
     failed to write?
   - Anything in the harness that still lets a broken artifact reach
     demo/demo.webm?

2. backend/server.py:
   - generate_token moved after bind — any path where the server serves
     requests before the token exists, or any caller of make_server that
     relied on the old order?
   - tracker upsert by tracking_number — edge cases (None, empty, dup across
     different capture_ids)?
   - tests/test_server.py — do the new tests actually cover the dispute-block
     attachment AND its absence without dispute?

3. package.json / check_panel.cjs — plain `require("playwright")` resolves
   locally now; version pinned ^1.57.0 (user edited to caret). Any risk the
   browser cache version mismatches (chrominum revision is keyed to the
   playwright version — ^ could pull a newer minor whose browsers are absent)?

4. demo/DEMO_SCRIPT.md + subtitles_en.srt — any remaining honesty/discipline
   gaps a hostile reviewer could flag (claims the video can't back, timing
   that doesn't match the new 120s schedule, unlabeled fixture claims)?

Read the actual files. Fail loudly on anything that could embarrass the
submission.
