Adversarial review — ROUND 3: verify the round-2 fixes themselves.
Repo: this repository. Prior reports: independent-review rounds 1 and 2
(external ext_review process, 2026-10-12).

Round-2 fixes to attack (all committed as 2aafe45):

1. tests/test_server.py tearDown now removes server.TOKEN_PATH BEFORE
   stopping the patch. Confirm ordering is correct in the actual file and no
   other test class has the same trap (search the file for token patches).
2. backend/server.py:
   - generate_token() now runs AFTER HTTPServer() bind in make_server.
     Correct? Any window where requests arrive before the token file exists?
   - os.open(O_WRONLY|O_CREAT|O_TRUNC, 0o600) + chmod — right flags, right
     mode semantics, no fd leak on exception?
   - secrets.compare_digest on /track — correct usage?
   - MAX_BODY_BYTES/_BodyTooLarge — does the 413 path actually work (the
     exception is raised inside _read_json_body, caught in do_POST)? Any path
     where a big body still gets read? Check _BodyTooLarge placement and that
     `import` surface is fine (secrets was already imported?).
   - do_POST catch order: _BodyTooLarge first, then JSON errors — correct?
3. scratch/record_demo.cjs:
   - until()/beatLags drift detection — worstLag computed AFTER the last
     until(120) call; is the recording actually failed when a beat slips, or
     can the throw happen after context.close() already committed the video?
   - mtime filter `v.t >= recStart - 1000` — recStart is `t0` set right before
     Act 1, but the browser context (and its video writer) is created EARLIER
     in the script — verify recStart precedes any webm creation and the filter
     can't reject the real output.
   - Any path where a GUID webm lingers undeleted while demo.webm is fine —
     cosmetic, fine to note only.
4. SPEC-preflight-checker_design.md ID-contract edit — does the revised text
   now match what server.py actually does on ALL failure branches (capture
   unresolvable vs order unresolvable)?
5. demo/subtitles_en.srt — #9/#10 boundary now at 1:38 matching
   until(98); any other cue that mismatches the harness schedule (Act beats:
   4/8/12/40/44/48/52/56/70/82/98/110/120)?

Read the actual files; confirm or refute each fix; flag anything new.
