# paypal-ai-hack-2026 — 外に出すもの: PayPal AI Hackathon 2026への提出物(締切 2026-11-12)

## For judges — run it yourself (English)

**Preflight for PayPal** is a Chrome extension + local backend that checks a
PayPal order against Seller Protection requirements *before* the seller ships,
shows which conditions are not met, and registers tracking back to PayPal.

### Option A — fixture mode (no PayPal account needed, ~2 minutes)

The backend ships with real API responses captured from a PayPal sandbox
(`backend/fixtures/`). Fixture mode serves them locally — no credentials,
no network calls to PayPal.

```bash
cd paypal-ai-hack-2026
python3 -m backend.server --fixture
# → "fixture mode — 6 orders, 6 captures loaded"
# → a local auth token is written to ~/.config/studio/preflight-token
```

1. Open `chrome://extensions` → enable **Developer mode** → **Load unpacked**
   → select the `extension/` directory.
2. Open the extension's **options** page → paste the token from
   `~/.config/studio/preflight-token` → save.
3. Open the **side panel**, paste a fixture **capture id** below, press **Check**:

   | capture_id | scenario |
   |---|---|
   | `3J366679AY2283450` | physical goods, **no shipping address**, disputed order — main demo |
   | `4EC24563F7235632E` | physical goods with address (mostly compliant) |
   | `2B190886TP583404W` | physical goods, full shipping address on file |
   | `13E67607MS6117934` | digital goods declared |
   | `76X32521BG861322V` | high-value order ($800, signature threshold) |
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
   `~/.config/studio/paypal-sandbox.env`.
2. Run the backend **without** `--fixture`: `python3 -m backend.server`.
3. Same extension setup; ids are then read from a real
   `sandbox.paypal.com` order you create (buyer→seller sandbox payment),
   or pasted manually.

### Verify the build

```bash
python3 -m pytest tests/     # 91 tests
node scratch/check_panel.cjs # 31 browser checks (requires playwright)
```

## 現在位置(2026-10-11時点)

- **本命候補**: Seller Protection適合チェッカー — 出荷前に「この注文はPayPal売り手保護の対象外・理由・処方」を教えるpre-flightチェッカー
- **判定**: 仮想審査員最終判定=**Go 36/50**(存在証明終了・建造フェーズへ)。詳細=`bd/IDEA-seller-protection-checker_premises.md`
- **実測で確定済み**: ①旗` seller_protection.status`はsandboxスタブ(6ケース全てELIGIBLE固定) ②Disputesライフサイクルは実物(証拠要求`PROOF_OF_FULFILLMENT`・資金保留`HOLD_PLACED`実演可・adjudicateは未到達) ③tracking登録書き込みは実物(閉ループ修正が組める)
- **現在工程**: `SPEC-preflight-checker_requirements.md`で3段階要件の段1

## 認証情報(解決済み)

`sandbox`認証情報は `~/.config/studio/paypal-sandbox.env` に登録済み(Repo外)。sandbox買い手= `sb-k6b9g53303451@personal.example.com`、売り手=`sb-watcy53292435@business.example.com`(merchant_id `4D4RCZX94MX7L`)。

## ディレクトリ

- `bd/` — business-design成果物(生成記録・前提整理・Gate判定)
  - `GEN-paypal-ai-hack-2026_candidates.md` — 全生成・殺し・スイープの記録(追補5まで)
  - `IDEA-seller-protection-checker_premises.md` — 本命の前提整理+Gate 0条件+Guzco部分占有の更新
  - `IDEA-agent-pay-test-harness_premises.md` / `IDEA-agent-spend-watch_premises.md` — 殺された候補(参照用)

## 関連資産(リポジトリ外)

- `/Users/tatsuyasasaki/Developer/_archive/agent-pay-guardian/sandbox/order.py` — PayPal sandbox対話スクリプト(改造して実測に使う。畳んだPJだが資産は生きている・_archiveへ2026-10-11移動)
- `~/Developer/_ops/docs/ref/REF-paypal-winners-analysis_20261010.md` — 勝者分析(審査5軸)
- `~/Developer/_ops/docs/ref/REF-hackathon-ai-screening_20261010.md` — AI審査フィルター対策(**提出時に必読**)
- `~/.agents/skills/business-design/` — 本PJの実走でv1.20〜v1.22まで改訂済み
