# Preflight for PayPal

PayPal AI Hackathon 2026 submission.

## For judges — run it yourself (English)

**Preflight for PayPal — Seller Protection readiness for sellers: 7 checks,
6 fixture orders, 1 captured sandbox dispute — runnable in ~2 minutes with no
PayPal account.** A Chrome extension + local backend that checks a PayPal order
against Seller Protection requirements *before* the seller ships, shows which
conditions are not met, and registers tracking back to PayPal.

Unlike Guzco's done-for-you dispute playbooks, Preflight is self-serve and
lives inside the PayPal console — its claim is that **the evidence PayPal
demands after a dispute is what Preflight surfaces before shipment**, because
PayPal's `ELIGIBLE` flag is a *declared-data snapshot*, not a decision.

### Demo walkthrough — the 3 acts (also `demo/DEMO_SCRIPT.md` + `demo/demo.webm`)

1. **Diagnose** — paste capture id `3J366679AY2283450`, press **Check**.
   PayPal's flag says `ELIGIBLE` (labeled *declared-data snapshot*), yet two
   Basic Requirements of the US Seller Protection terms (ver. 2026-01-26)
   fail: no shipping address, no proof of shipment. Evidence slots below show
   what is missing and which of it is still fillable.
2. **Correct** — in §05 FIX, choose UPS, enter tracking `1Z999AA10123456784`,
   press **Register tracking** — a real write through PayPal's Shipping
   Trackers API (fixture mode simulates it in memory). §06 BEFORE/AFTER shows
   `TRACKING_REQUIRED` flip fail→pass; the missing-address fail honestly stays.
3. **Correspondence** — the same capture later became real sandbox dispute
   `PP-R-XGB-10190971` (item not received). The panel's amber banner names it,
   and the `PROOF_OF_FULFILLMENT` slot is marked **requested in dispute** —
   the exact evidence type flagged before shipment.

### Judging-criteria map

- **Technical implementation** — deterministic rule layer over the Orders API
  and Shipping Trackers API, plus an honest-degrading LLM meaning layer
  (`ran=false` without credentials). PayPal terms pinned to ver. 2026-01-26
  with a per-check clause citation (`backend/policy.py`); dispute handling
  via the Disputes API record.
- **Design** — the gap between PayPal's `ELIGIBLE` flag and actual conditions
  is surfaced inside the merchant console, at the moment of shipping — not in
  a separate dashboard after the fact.
- **Impact** — sellers lose goods *and* payment when a dispute arrives
  unprotected; pre-shipment warnings map 1:1 onto the evidence types PayPal
  later requests (demonstrated on a real sandbox dispute).
- **Innovation** — for agentic commerce, declared data must be verified at
  the edge: Preflight turns the flag's declaration into checked conditions
  with fixed prescriptions, never predicting dispute outcomes.
- **Presentation** — 2-minute 3-act demo video + judge-runnable fixture mode.

### Option A — fixture mode (no PayPal account needed, ~2 minutes)

The backend ships with real API responses captured from a PayPal sandbox
(`backend/fixtures/`). Fixture mode serves them locally — no credentials,
no network calls to PayPal.

```bash
git clone https://github.com/tatsuya7899/preflight-for-paypal.git
cd preflight-for-paypal
python3 -m backend.server --fixture
# → "fixture mode — 6 orders, 6 captures loaded"
# → a local auth token is written to ~/.config/preflight/preflight-token
```

1. Open `chrome://extensions` → enable **Developer mode** → **Load unpacked**
   → select the `extension/` directory.
2. Open the extension's **options** page → paste the token from
   `~/.config/preflight/preflight-token` → save.
3. Open the **side panel**, paste a fixture **capture id** below, press **Check**:

   | capture_id | scenario |
   |---|---|
   | `3J366679AY2283450` | physical goods, **no shipping address**, disputed order — main demo |
   | `4EC24563F7235632E` | physical goods with address (mostly compliant) |
   | `2B190886TP583404W` | physical goods, full shipping address on file |
   | `13E67607MS6117934` | digital goods declared |
   | `76X32521BG861322V` | high-value order ($800 — shows the signature-confirmation note, not a term violation) |
   | `8R484715XN459481P` | order with no items declared |

   (an **order_id** works too, e.g. `3UJ2460633408874H`)

4. Try the correction loop: in **§05 FIX**, pick a carrier, enter any tracking
   number, press **Register tracking** → the panel re-checks and §06
   **BEFORE / AFTER** shows `TRACKING_REQUIRED` flip from FAIL to PASS.
   Registrations are kept in memory for the running server only — nothing is
   sent anywhere.

**Honest limits of fixture mode**: IDs, amounts and flags come from captured
sandbox responses; the semantic (LLM) layer reports `ran=false` unless an LLM
key is configured; no real PayPal call is made. The panel labels PayPal's
`ELIGIBLE` flag as a *declared-data snapshot*, not a protection decision.

### Option B — live sandbox mode

1. Create a PayPal developer app (sandbox) → put
   `PAYPAL_CLIENT_ID=...` / `PAYPAL_CLIENT_SECRET=...` in
   `~/.config/preflight/paypal-sandbox.env`.
2. Run the backend **without** `--fixture`: `python3 -m backend.server`.
3. Same extension setup; ids are then read from a real
   `sandbox.paypal.com` order you create (buyer→seller sandbox payment),
   or pasted manually.

### Verify the build

```bash
python3 -m pytest tests/     # 110 tests
node scratch/check_panel.cjs # 37 browser checks (requires playwright)
```

## Repository layout

- `extension/` — Chrome MV3 extension (side panel + content extraction).
- `backend/` — Python stdlib localhost server (`server.py`, `paypal.py`,
  `rules.py`, `policy.py`, `meaning.py`) + `fixtures/` captured sandbox data.
- `demo/` — `demo.webm` (2-minute 3-act recording), `subtitles_en.srt`,
  `DEMO_SCRIPT.md` (the recording plan the video follows).
- `tests/` — 110 pytest cases + 13 subtests covering server, rules, policy,
  and the fixture register→re-check loop.
- `sandbox/` — the measured-probe scripts used against the real sandbox API
  (order variation, dispute lifecycle, tracker writes, payment_source
  comparison). They require `~/.config/preflight/paypal-sandbox.env` (or the
  author's legacy `~/.config/studio/` path) with real sandbox credentials.
- `scratch/` — development tooling: the Playwright demo recorder and panel
  check harness (`record_demo.cjs`, `check_panel.cjs`).
- `bd/` — the business-design working record kept as submission evidence:
  candidate generation, premise analysis, Lean Canvas, the clause-citation
  audit (`AUDIT-seller-protection-terms_20261012.md`) and the Go/NoGo decision
  log. Working notes are in Japanese; the audit and decision docs are the
  referenced evidence.

*Legacy note*: installs that already have `~/.config/studio/preflight-token`
or `~/.config/studio/paypal-sandbox.env` keep using them; fresh installs use
`~/.config/preflight/` as shown above.
