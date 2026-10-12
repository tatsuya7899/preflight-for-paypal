# 敵対的レビュー観点 — S2 規約条項照合監査の実装

対象: paypal-ai-hack-2026 の規約突合変更(ファイル全体をレビュー。差分は `git diff` で自身で確認可)。

## 背景

`backend/policy.py` の条項文言を現行US Seller Protection規約(ver. 2026-01-26,
https://www.paypal.com/us/legalhub/paypal/seller-protection)に照合して修正した。
監査記録は `bd/AUDIT-seller-protection-terms_20261012.md`。

主な変更:
1. `clause` 文字列を創作番号(§1(a)等)から実在の節名+版ピンへ書換
2. HIGH_VALUE_SIGNATURE を `fixed_status: not_assessable` に降格(現行US版に
   signature-confirmation要件が存在しないため)。`rules.py` の `evaluate()` に
   fixed_status 強制ループを新設
3. 除外カテゴリキーワード再構成 + `rules.py` のマッチャを部分一致→語境界正規表現へ
4. EXCLUDED_CATEGORY の処方を「verify against」文言へ弱めた(ヒューリスティック旗)
5. テスト追加: 誤爆ガード・実ヒット・fixed_status・節名/版ピンの存在検査

## 壊しに来てほしい論点(優先度順)

- **fixed_status強制の副作用**: `evaluate()` の強制ループが semantic mismatch で
  意図的にfailへ書き換える行(例: MADE_TO_ORDER→SHIP_WITHIN_DAYS)まで巻き戻さないか。
  SHIP_WITHIN_DAYSにはfixed_statusが無いので影響しないはずだが、行の生成順序と
  強制ループの位置関係を確認せよ
- **語境界マッチの取りこぼし**: `\b` 正規表現で真の違反を逃す例があるか
  (ハイフン入りキーワード "real-estate"/"non-fungible"/"pre-paid card"、
  句キーワード "business for sale" の境界条件、"paypal's" のアポストロフィ)
- **キーワードの残存誤爆**: 再構成後リストで、現実的な商品名がまだ誤爆するもの
  (例: "vehicle"→"remote control vehicle"、"donation"→"10% donation to charity"、
  "investment"→"investment piece"等)。それらは「旗として許容」と「除去すべき」の
  どちらか(根拠つきで)
- **audit記録の自己撞着**: AUDIT文書の記述と policy.py/rules.py の実装が
  食い違う箇所(発見番号の対応、残置限定事項の記載と実装の差)
- **テストの盲点**: 新テスト群が実は旧挙動でも通る等の無効テスト、
  または fixture verdict_F.json / panel_v6.html の埋め込みJSONが新policyと
  不整合な箇所(ステータス値・clause文言の残存旧形式)
- README/tasks.md の表記と実挙動の差異

## 成果物

`scratch/review_result_s2.md` に指摘を記録。致命的/重要/軽微の3段で、
各指摘に根拠(ファイル:行)を付けること。
