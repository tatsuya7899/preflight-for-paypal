あなたは独立レビューアとして別プロセスで起動されました。作成者の会話履歴は共有されていません。Chrome拡張のサイドパネルUI「Preflight for PayPal」第5版を敵対的に採点してください。合格にする義務はありません。曖昧なら差し戻してください。

## 分割・チェックポイント計画(厳守)
2分割で進め、各分割の終わりにチェックポイントとして中間成果を確定させてから採点表に進むこと:
- 分割A(内容照合): パネル内の全表示値を正本と突合。チェックポイント=「表示値の突合表」
- 分割B(視覚・宣言照合): スクショの目視欠陥列挙+方向宣言との整合。チェックポイント=「視覚欠陥一覧(なし含む)」

## 対象
- scratch/panel_v5.html — 採点対象のモック
- scratch/verdict_F.json — 実バックエンド(rules.evaluate(order_F, [], meaning.run(order_F)))の生出力。パネルのDATAオブジェクトはこの値だけを表示するはず
- scratch/shots/shot_s1.png — 360px幅のスクリーンショット(readで画像として見ること)
- backend/policy.py, rules.py, meaning.py — 実装正本
- backend/fixtures/order_F.json, backend/fixtures/dispute_PP-R-XGB-10190971.json — fixture正本

## 方向宣言
パラダイム=横ストリップ、メタファー=証拠袋。「出荷前チェックが求める証拠の形=紛争時にPayPalが要求する証拠カテゴリの形」が一致するのがこの製品の勘所。

## 前版v4で出た必須修正(P0)——全件が直ったか照合せよ
1. 架空の詐欺パターン名(NO_ADDRESS_SHIP_RISK・NO_SHIPPING_DECLARED_PHYSICAL_GOODS等)を表示していた → 実出力の警告は1件(NO_SHIPPING_ADDRESS_ON_FILE)・判定不能3件。パネルはこの実名のみを表示しているか
2. 創作したroutingステータスと不一致な件数 → 実値は3 pass/2 fail/2 not_assessable。summaryと7枚のカードが一致しているか
3. expected_evidenceの省略・捏造 → 7カード全行の配列が全表示されているか(8種のevidence_typeが存在するはず)
4. カード幅272pxで常時クリップ → 現在228px。1枚目が全文可読か

## P1推奨修正——確認せよ
5. 実案件事実(このcaptureの紛争レコードにPROOF_OF_FULFILLMENT×2・SUBMITTED_BY_SELLER)がタップなしで見えるか
6. capture_status=PENDING/BUYER_COMPLAINT(既に紛争中)の文脈バナーがあるか・追跡登録が紛争解決を約束しない表現か
7. 本文可読性(9〜10px多用の改善具合)
8. タップ領域(主要操作が概ね44px級か)
9. LLM退化の正直表示(meaning.ran=false時「semantic layer not run」と明示し、LLM由来の結果を見せない)
10. 裁定予測・保護効果の保証・証拠捏造に相当する表現がないか

## 採点軸(0-10・根拠1行ずつ)
第一原理への忠実さ(30%) / 情報の正確さ(25%) / メタファー一貫性(20%) / 可読性(10%) / インタラクション(10%) / クラフト(5%)

## 出力形式(厳守)
VERDICT: PASS | ISSUES

### チェックポイントA: 表示値の突合表
### チェックポイントB: 視覚欠陥一覧
### 軸別採点(6軸・根拠つき)
### 加重総合点
### 指摘(P0必須/P1推奨/P2任意)
### 最終判定: 承認(総合≥8.0かつ全軸≥7.0) / 差し戻し(理由)
