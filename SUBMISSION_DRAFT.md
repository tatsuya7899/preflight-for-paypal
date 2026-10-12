# Devpost 提出文面ドラフト(2026-10-12)

Devpostフォーム各項目への転記用。AI審査フィルター対策(REF-hackathon-ai-screening)7項目を適用済み:
①1文目に要約+数値 ②ルーブリック語彙を見出し化 ③テーマ語彙(agentic commerce・Seller Protection・Orders/Trackers/Disputes API) ④README=一次文書 ⑤字幕経由語彙 ⑥具体名詞密度 ⑦差分の明示命名。

**正直表記の制約**(逸脱禁止): fixture由来を明記・LLM層は`ran=false`退化を開示・法的助言でない明記・裁定結果の予測をしない・実セラー検証は未検証と明記。

---

## Project name

Preflight for PayPal

## Tagline / Elevator pitch(1行)

Seller Protection readiness for sellers: 7 checks, 6 fixture orders, 1 captured sandbox dispute — check before you ship, inside the PayPal console.

## About this project — Inspiration

PayPal's `seller_protection.status` flag says `ELIGIBLE` — but it is a *declared-data snapshot*, not a decision on whether the seller's *actions* satisfy the US Seller Protection terms (ver. 2026-01-26). In our sandbox measurements the flag stayed `ELIGIBLE` on orders missing a shipping address, missing tracking, and carrying digital goods — while a card-funded capture flipped to `NOT_ELIGIBLE` the moment `payment_source` changed. A seller who trusts the flag ships unprotected, and when an item-not-received dispute lands they lose the goods **and** the payment.

## What it does

Preflight is a Chrome extension living inside the PayPal merchant console. Before shipping, the seller pastes a capture/order ID and Preflight evaluates the transaction against 7 checks mapped to the current US Seller Protection terms — each check carrying the real clause name it derives from. Results split honestly into **pass / fail / not assessable** (conditions the Orders API cannot see are never presented as failures). Every fail ships a fixed prescription, including "do not ship" where correction is impossible.

The demo walks three acts:

1. **Diagnose** — capture `3J366679AY2283450` shows `ELIGIBLE` yet fails two Basic Requirements (no shipping address, no tracking).
2. **Correct** — registering UPS tracking `1Z999AA10123456784` writes through PayPal's Shipping Trackers API; re-check flips `TRACKING_REQUIRED` fail→pass while the unfixable address fail honestly remains.
3. **Correspondence** — the same capture later became real sandbox dispute `PP-R-XGB-10190971`; the `PROOF_OF_FULFILLMENT` evidence slot carries a "requested in dispute" marker. **The evidence PayPal demands after a dispute is what Preflight surfaces before shipment.**

## How we built it

- **Orders API** (`GET /v2/checkout/orders`) + **Payments capture** — transaction shape, shipping address presence, `seller_protection` flag read as declared data.
- **Shipping Trackers API** (`/v1/shipping/trackers-batch`, `GET /v1/shipping/trackers`) — the write-back correction loop, verified live in sandbox.
- **Disputes API** (`/v1/customer/disputes`) — real sandbox dispute record driving the evidence-correspondence layer.
- **Deterministic rule layer** (`backend/rules.py` + `backend/policy.py`) — every check cites its clause by real section name, pinned to document version 2026-01-26 (audited against the current legalhub text; invented section numbers were found and removed in `bd/AUDIT-seller-protection-terms_20261012.md`).
- **Honest-degrading LLM meaning layer** (`backend/meaning.py`) — reports `ran=false` without a key; the product never hides its unavailability.
- **Chrome extension (MV3)** side panel + **Python stdlib** localhost backend (127.0.0.1-only bind, token auth on the write path, constant-time token compare, 1 MB body cap).
- **Judge-runnable fixture mode** — 6 orders / 6 captures / 1 dispute captured from a real sandbox, served locally with an in-memory tracker store so the register→re-check loop works without any PayPal account.
- **110 pytest cases + 37 browser checks** green; the demo video is produced by a Playwright harness that asserts on-screen content, not just file existence.

## Challenges we ran into

- The sandbox `seller_protection` flag is a stub: six varied orders all returned `ELIGIBLE`. That measurement became the product's thesis — the flag alone cannot tell a seller they are unprotected, so the semantic/action layer had to be built on top rather than trusting the flag.
- Seller Protection terms are prose. Mapping each check to the *current* US version required a clause-by-clause audit; the $750 signature-confirmation check exists only in other regions' terms, so it was downgraded to a fixed not-assessable note rather than a fabricated failure.
- Dispute creation in sandbox needs buyer-side credentials (`PayPal-Auth-Assertion` + `buyer_transaction_id`), so a second dispute had to be documented as a manual-UI step — the evidence-request machinery itself was still verified end-to-end on a real dispute.

## Accomplishments we're proud of

- The flag-vs-conditions gap is not asserted — it is **measured** (six-order variation matrix; card vs. wallet payment-source flip measured live).
- The product closes a real write loop through PayPal's API, not a screenshot of one.
- Every claim a judge can click is backed by a captured response, a test, or an audit note — including the things that did *not* work.

## What we learned

`payment_source` moves the flag: a card-funded capture returned `NOT_ELIGIBLE` where wallet-funded captures returned `ELIGIBLE` — meaning sellers taking card-side payments sit outside Seller Protection entirely. Also: the Disputes API's evidence-request lifecycle (`require-evidence` → `provide-evidence` → adjudication) is fully drivable in sandbox, which is what let us prove the pre-shipment/post-dispute correspondence.

## What's next for Preflight for PayPal

Real-seller validation (one seller walkthrough on a sandbox-replayed live order — currently unverified and labeled as such), live-mode hardening for app review, and coverage of the remaining non-assessable conditions as PayPal exposes more signals.

## Judging-criteria map

- **Technical implementation** — deterministic rule layer over the Orders API and Shipping Trackers API with per-check clause citations pinned to ver. 2026-01-26, an honest-degrading LLM layer, token-authenticated localhost backend, and a dispute record via the Disputes API.
- **Design** — the flag-vs-conditions gap is surfaced inside the merchant console at the moment of shipping, not in a separate dashboard after the dispute arrives.
- **Impact** — sellers lose goods *and* payment when a dispute arrives unprotected; pre-shipment warnings map 1:1 onto the evidence types PayPal later requests, demonstrated on a real sandbox dispute.
- **Innovation** — for agentic commerce, declared data must be verified at the edge: Preflight turns the flag's declaration into checked conditions with fixed prescriptions, never predicting dispute outcomes.
- **Presentation** — 2-minute 3-act demo video plus a judge-runnable fixture mode: no PayPal account, ~2 minutes.

## Honest limitations

Fixture mode labels its data source on screen; the LLM semantic layer reports unavailable rather than faking output; the tool is not legal advice and never predicts dispute outcomes; business/customer validation is explicitly unverified. `ELIGIBLE` is always presented as PayPal's declared data, not our endorsement.

## Built with

`paypal-orders-api` `paypal-shipping-trackers-api` `paypal-disputes-api` `chrome-extension` `manifest-v3` `python` `javascript` `playwright` `sandbox-testing` `agentic-commerce`

## Try it out / repo

- **Repository**: {公開リポジトリURL — 要人間判断。非公開のままでは審査員がビルドできない。fixtureモードは認証情報不要}
- **Demo video**: {YouTube URL — demo/demo.webm (119.96s) + demo/subtitles_en.srt を人間がアップロード}
- **Judge quickstart**: `python3 -m backend.server --fixture` → `~/.config/studio/preflight-token` を拡張optionsへ → capture `3J366679AY2283450` で Check(README §Option A・約2分)

## 提出前の人間作業(APIではできない分)

1. **動画アップロード**: `demo/demo.webm`をYouTube限定公開へ+`demo/subtitles_en.srt`を字幕として追加(字幕経由でルーブリック語彙が機械審査に届く)
2. **リポジトリ公開判断**: Devpost「working build」要件のため公開リポジトリが実質必須。`bd/`(企画工程文書・内部メモ)を公開履歴に含めてよいか要判断——含めないなら提出用に別リポジトリを切る
3. **フォーム転記**: 上記各項目をDevpostへ貼付
4. **S6(実セラー実演)**: 人間調達依存・提出には「unverified」と明記済みでブロックなし
