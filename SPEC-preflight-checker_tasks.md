# preflight-checker — タスク

**前提**: SPEC-preflight-checker_design.md(敵対的レビュー通過・収束済み)
**日付**: 2026-10-11

## 実装順

| # | タスク | 種別 | 委任先 | 投資量 | 依存 | 完了判定 |
|---|---|---|---|---|---|---|
| 1 | コンソール注文詳細画面で取引IDがDOMから取得可能か確認(前提の未実測項) | 探索型 | 手動/playwright | 軽量 | — | DOMセレクタの有無を1行記録 |
| 2 | `backend/fixtures/`に実測6注文のcapture応答+紛争応答を保存 | 安定型 | builder | 軽量 | — | fixture6+1件がJSONで存在 |
| 3 | `backend/policy.py`(条件名・条項・処方・不一致→check写像・carrier enum) | 安定型 | builder | 標準 | — | importして全定数にアクセス可 |
| 4 | `backend/paypal.py`(OAuth/order取得/trackers POST・GET) | 安定型 | builder | 標準 | — | sandbox実APIでorder取得成功 |
| 5 | `backend/rules.py`(条件表+verdict組立) | 安定型 | builder | 標準 | 3 | 条件表の各行が判定関数を持つ |
| 6 | `tests/test_rules.py`(受入#1,3,6,7,8をfixtureでRed→Green) | 安定型 | builder | 標準 | 2,5 | 全テストGreen |
| 7 | `backend/meaning.py`(LLM意味分類+表駆動fraud・ran=false退化) | 安定型 | builder | 標準 | 3 | LLM無しでfraud部分だけ動く |
| 8 | `backend/server.py`(/check /track /health + X-Preflight-Token) | 安定型 | builder | 標準 | 4,5,7 | curlで/checkが200を返す |
| 9 | `tests/test_server.py`(受入#5の/track E2E含む) | 安定型 | builder | 標準 | 8 | 全テストGreen |
| 10 | `extension/manifest.json`+`background.js`+`content.js` | 安定型 | builder | 標準 | 1 | chrome://extensionsで読み込める |
| 11 | `extension/panel.html`+`panel.js`(診断UI・旗ラベル・前後比較・修正フォーム) | 安定型 | builder(/ui-quality経由委任) | 標準 | 8 | 受入#4,9の画面が出る |
| 12 | `extension/options.html`+`options.js`(トークン設定) | 安定型 | builder | 軽量 | 8 | トークン保存→/trackが認証通過 |
| 13 | E2E実クリック検証(受入#10・sandboxコンソールで拡張起動) | — | 手動/playwright | 軽量 | 10,11 | コンソール上で診断表示を確認 |
| 14 | 非自明実装の敵対的レビュー | — | Plan agent | 最上位 | 6,9,13 | P0/P1ゼロ |

- **1タスク=1ファイル編集→検証**(R2「修正はステップ・バイ・ステップ」)。同種修正でも一括置換にしない
- **並列にできる**: #1+#2(独立)、#3+#4+#10(独立)。#5以降は前段依存のため直列
- **並列指定なし**: 一発で通る見込みが薄いタスクは無い(全て実測済みAPIの写像+stdlib構成のため)

## 補足(本SPECの範囲外タスク・別工程)

- 3幕デモ台本+録画・README=デモ台本化・AI審査フィルター対策・紛争n=2再現・payment_source変動テスト → 提出パス側TODO(premises最終判定のP0-3/P1群)。本SPEC完了後に別工程で管理

### 提出パス側タスク(M2/M7独立レビュー2026-10-11由来・登録済み)

| # | タスク | 種別 | 委任先 | 依存 | 完了判定 |
|---|---|---|---|---|---|
| S1 | 審査員実行経路の整備: backendにfixtureモード起動手順をREADMEに明記(PayPal資格情報なしで動く検証経路)+セットアップ手順書(sandbox資格情報取得〜拡張sideload〜トークン貼付) | 安定型 | builder | #8 | Devpost要件「judges must be able to actually run a working build」を満たす手順がREADMEに存在 ✅**完了2026-10-12**: `--fixture`/PREFLIGHT_FIXTURE=1で起動・メモリtracker閉ループ動作・README英語手順(表6件)・fixtureテスト5件・独立レビュー指摘6件全反映 |
| S2 | 規約条項照合監査: policy.pyの条項根拠を現行US版(文書日付ピン)で再確認・SHIP_WITHIN_DAYSのrequired/recommended文言・HIGH_VALUE_SIGNATUREのfail→warning判定を含む | 探索型 | builder+web確認 | #3 | ✅**完了2026-10-12**: 現行US版(ver. 2026-01-26)と突合。発見3件——創作条項番号(§1(a)〜§2)を実在の節名へ書換・署名確認は現行US版に非存在のためfixed_status降格(fail不可能に)・除外キーワード再構成+語境界マッチ化。監査記録=`bd/AUDIT-seller-protection-terms_20261012.md`・98テスト全Green |
| S3 | payment_source変動で旗が動くかのテスト(Gate 0残条件②・sandboxスクリプト) | 探索型 | builder | #4 | ✅**完了2026-10-12**: **旗は動く**——card payment_sourceをinline指定したorder(52U286559X851562A)は承認UIなしで即capture(`3KA63732H29383712`)され`seller_protection.status=NOT_ELIGIBLE`を返した。ウォレット経由capture(fixture A〜F)は全て`ELIGIBLE`。つまりpayment_source変動=flag変動が実測で確認。card経由はSeller Protection対象外という製品裏付けも得た。実測スクリプト=`sandbox/s3_s4_probe.py` |
| S4 | 紛争n=2再現(UNAUTHORIZED系・デモ録画前・実API) | 安定型 | builder | #4,#8 | ⚠️**API経路尽き・人間依存に確定2026-10-12**: `POST /v1/customer/disputes`は`buyer_transaction_id`(buyer口座Activityでのみ取得可・order detailにも非露出)と`PayPal-Auth-Assertion` JWT(LIP同意フロー=`DISPUTE_CREATE`スコープ)を要求——セラー側client_credentialsだけでは作成不可(`TRANSACTION_NOT_ELIGIBLE`)。公式docs=resolution center UIからbuyerアカウントで発生させる手順のみ。**証拠要求の機械自体はn=1で実検証済み**(PROOF_OF_FULFILLMENT要求→提出→adjudicate)。2件目は人間がsandbox UIでUNAUTHORISED案件を起こす残置タスク——提出ブロッカーではない |
| S5 | 3幕デモ台本+録画+README台本化+AI審査フィルター対策(REF-hackathon-ai-screening) | 安定型 | builder+監督 | #11,S1 | ✅**完了2026-10-12**: `demo/demo.webm`(119.96s・字幕0:00–2:00と一致)をフレーム抽出で全幕目視検証——診断2FAIL・追跡登録「registered — re-check complete」・BEFORE/AFTER fail→pass転換・紛争バナー+「in dispute」バッジ全て確認。録画障害の根本原因=zenn previewが*:8000を占有し/healthが偽陽性→専用ポート8765+isOursマーカ判定+認証プリプローブで根治。硬化後ハーネス(内容アサーション+drift検知)で再録画済み |
| S6 | 実セラー実演(MSC(b)検収・相手の直近実注文のsandbox再現注文で実施) | — | **利用者(人間調達)** | #13 | 相手の「使い続けていい?」自発質問の有無が記録される(11/09逆算期限) |

## 差し戻し

- 同一指摘の往復は2回まで。3ラウンドを超えたら振動とみなし人間裁定
