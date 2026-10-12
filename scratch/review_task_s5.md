Review target: demo recording harness + demo materials for the PayPal AI
Hackathon 2026 submission (repo: _incubator/paypal-ai-hack-2026).

Context: scratch/record_demo.cjs records a Playwright video of
extension/panel.html driving the REAL fixture backend (python3 -m
backend.server --fixture). Two failure classes were just fixed:
1. A foreign dev server (zenn preview, node, bound to *:8000 IPv6 accepting
   v4-mapped connections) squats on port 8000. The old waitHealth treated any
   200 as "our server up", read the token file before the spawned server
   rewrote it, and /track then 403'd mid-recording.
2. file:// page + localhost fetch needs a CORS shim via context.route.

Changes under review (diff vs HEAD via `git diff HEAD -- scratch/record_demo.cjs`):
- Dedicated port 8765 via PREFLIGHT_PORT env on the spawned server
- Pre-spawn guard: abort if /health is answered by OUR app (fixture key in
  JSON) = stale server; foreign squatters no longer matter on 8765
- isOurs(): require "fixture" key in /health JSON instead of mere 200
- Auth pre-flight probe: POST /track with bogus capture_id expects 404
  (auth passed but unknown id) — aborts recording before any video is made
- Verbose first-8 health polls + srv exitCode dump on timeout
- Page console error surfacing (page.on("console"))
- api() in the chrome-stub logs non-2xx to page console

Questions for the reviewer:
- Any remaining race where the recorded video could show a false success or
  silent failure? (e.g. token file rewritten between read and /track call —
  who else can write it?)
- Is the bogus-capture 404 probe sound given server.py auth order (token
  checked before handler → 403 vs 404 distinction)?
- Any way the recording could silently capture a stale server instead of the
  spawned one (port collision, PREFLIGHT_PORT env leak)?
- DEMO_SCRIPT.md + subtitles_en.srt: do they stay honest (fixture labeled,
  no dispute-outcome prediction, ELIGIBLE framed as declared-data snapshot)?
- Anything that would mislead a judge watching demo/demo.webm?

Read the full files; the video itself is 47.9s at demo/demo.webm (verified via
frame extraction: act1 2FAIL diagnosis, act2 registered→re-check→fail→pass
flip, act3 dispute banner + requested-in-dispute badge).
