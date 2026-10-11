# paypal-ai-hack-2026 — 外に出すもの: PayPal AI Hackathon 2026への提出物(締切 2026-11-12)

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
