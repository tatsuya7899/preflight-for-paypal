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

## 差し戻し

- 同一指摘の往復は2回まで。3ラウンドを超えたら振動とみなし人間裁定
