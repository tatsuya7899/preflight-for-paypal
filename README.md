# paypal-ai-hack-2026 — 外に出すもの: PayPal AI Hackathon 2026への提出物(締切 2026-11-12)

## 現在位置(2026-10-11時点)

- **本命候補**: Seller Protection適合チェッカー — 出荷前に「この注文はPayPal売り手保護の対象外・理由・処方」を教えるpre-flightチェッカー
- **判定**: Gate 0仮想審査員=**条件つきGo**(現形30/50・条件充足で35〜38見込み)。詳細=`bd/IDEA-seller-protection-checker_premises.md`
- **直前の未検証ゲート**: sandboxでDIGITAL_GOODS注文→captureが`seller_protection.status=NOT_ELIGIBLE`を実際に返すか。**返らなければNoGoに再判定**

## ブロッカー(再開時に最初にやること)

PayPal sandbox認証情報の取得が詰まっている:

1. PayPalアカウントが**Google経由で作成済み=パスワード未設定**。Developer Dashboardはメール+パスワードを要求するためログインできない
2. **手順**: paypal.comにGoogleログイン→設定→セキュリティ→パスワード新規作成→developer.paypal.comにメール+パスワードでログイン
3. 認証情報は `python3 ~/Developer/_ops/scripts/store_studio_env.py --file paypal-sandbox.env --set PAYPAL_CLIENT_ID --set PAYPAL_CLIENT_SECRET` で `~/.config/studio/` に登録(中身を表示しない)

## ディレクトリ

- `bd/` — business-design成果物(生成記録・前提整理・Gate判定)
  - `GEN-paypal-ai-hack-2026_candidates.md` — 全生成・殺し・スイープの記録(追補5まで)
  - `IDEA-seller-protection-checker_premises.md` — 本命の前提整理+Gate 0条件+Guzco部分占有の更新
  - `IDEA-agent-pay-test-harness_premises.md` / `IDEA-agent-spend-watch_premises.md` — 殺された候補(参照用)

## 関連資産(リポジトリ外)

- `/Users/tatsuyasasaki/Developer/_incubator/agent-pay-guardian/sandbox/order.py` — PayPal sandbox対話スクリプト(改造して実測に使う)
- `~/Developer/_ops/docs/ref/REF-paypal-winners-analysis_20261010.md` — 勝者分析(審査5軸)
- `~/Developer/_ops/docs/ref/REF-hackathon-ai-screening_20261010.md` — AI審査フィルター対策(**提出時に必読**)
- `~/.agents/skills/business-design/` — 本PJの実走でv1.20〜v1.22まで改訂済み
