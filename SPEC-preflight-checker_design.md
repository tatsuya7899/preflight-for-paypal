# preflight-checker — 設計

**前提**: SPEC-preflight-checker_requirements.md(確定版)。[要確認] 残り0件
**日付**: 2026-10-11  **版**: 2(敵対的レビューP0×3・P1×6・P2×8を全件反映)
**索引照合**: DDIA #7(外部API連携=同期サービス呼出し・非同期不要) / AI #2(LLM判定=ジャッジバイアス前提の固定ルーブリック・規約解釈させない) / AI #6(書き込みアクション=人間承認ゲートReview必須)

## 方式(何をどう作るか)

**ブラウザ拡張(MV3)=薄いUI殻 + localhostバックエンド=頭脳**。拡張はコンソール画面から取引IDを拾い結果を描画するだけ。PayPal OAuth・ルール層・意味層・処方表は全部localhostのPython stdlibサーバに置く(既存`sandbox/`スクリプトと同じ依存ゼロ方針)。理由: ①client_secretを拡張に埋めると誰でも抜ける ②PayPal APIはブラウザ直叩きでCORSに引っかかる ③LLMキーも同じくサーバ側に隔離。

## 触るファイル(名指し)

| ファイル | 変更内容 | 新規/既存 |
|---|---|---|
| `extension/manifest.json` | MV3定義。content scriptは`*://*.sandbox.paypal.com/*`のみ・side panel・service worker・options page | 新規 |
| `extension/content.js` | コンソール画面の取引ID抽出(DOM)・swへのメッセージ送信 | 新規 |
| `extension/background.js` | service worker。sidePanel.open・content↔panel中継 | 新規 |
| `extension/panel.html` + `panel.js` | 診断結果UI(英語)・旗スナップショット・前後比較・修正フォーム。**backendへのfetchはこことswのみ**(content scriptからは呼ばない=CORS/Private Network Access回避) | 新規 |
| `extension/options.html` + `options.js` | backendトークン設定画面(P1-5対応) | 新規 |
| `backend/server.py` | localhost HTTPサーバ(stdlib http.server)。`POST /check` `POST /track` `GET /health` | 新規 |
| `backend/paypal.py` | OAuth・Orders取得・trackers-batch POST/trackers GET(既存sandbox/*.pyのロジック移植) | 新規 |
| `backend/rules.py` | 決定的ルール層+verdict組立(意味層結果を受けて統合) | 新規 |
| `backend/policy.py` | US版Seller Protection条件名・条項参照・処方文字列・不一致→check写像・carrier enumの静的データ | 新規 |
| `backend/meaning.py` | 意味層。①LLM意味分類(LLM依存) ②詐欺パターン照合(**表駆動・LLM不要**)の2部品に分離 | 新規 |
| `backend/fixtures/*.json` | 実測済み6注文(A〜F)のcapture応答+紛争応答を保存・テスト用 | 新規 |
| `tests/test_rules.py` | ルール層の単体テスト(fixturesを回す) | 新規 |
| `tests/test_server.py` | /check /track のE2E(sandbox実APIまたはfixtureモード) | 新規 |

## 既存アーキテクチャとの整合

- 既存のデータモデル/命名/依存の向きと矛盾しないか: 既存`sandbox/*.py`はurllib+stdlibのみ・env読込みパターン(`~/.config/{studio→preflight}/paypal-sandbox.env`・レガシーフォールバック付き)をそのまま`backend/paypal.py`に移植。新規依存は入れない
- SSOT(同じ目的の実装・文書が2つにならないか): sandbox/は検証プローブのまま保存(動く記録)。製品コードはbackend/extensionに新設・混ぜない

## ID契約(P0-1)

- `/check`入力は **`capture_id`(必須)** とする。コンソール画面・紛争API・trackers APIが使うIDはcapture側(sandbox実測: trackingは`4EC24563F7235632E`等capture IDで登録済み)
- order_id入力を受けた場合は `GET /v2/checkout/orders/{id}` で `purchase_units[].payments.captures[0].id` に解決(複数captureは先頭1件+verdictに全capture一覧を返す)
- capture_id→order_idの逆解決はcapture GETの`supplementary_data.related_ids.order_id`(**改訂2026-10-12**: 不在時は404エラーを返す——パネル側が404を「order_idでの再試行」トリガとして使うcapture_id→order_idフォールバックの前提。設計当初の「order_id=nullで返し手動入力を促す」案は実装上のフォールバック方式と競合するため廃止)
- verdictは `order_id`・`capture_id`の両方を返す

## データモデル・インターフェース

`POST /check` 入力 `{"capture_id": "..."}` または `{"order_id": "..."}` → 出力 `verdict`:

```json
{
  "order_id": "...", "capture_id": "...",
  "flags": [{"capture_id": "...", "status": "ELIGIBLE",
             "dispute_categories": ["ITEM_NOT_RECEIVED","UNAUTHORIZED_TRANSACTION"]}],
  "summary": {"n_pass": 0, "n_fail": 0, "n_not_assessable": 0},
  "checks": [
    {"condition": "SHIP_TO_TRANSACTION_ADDRESS", "status": "pass|fail|not_assessable",
     "basis": "shipping.address present", "clause": "US Seller Protection terms (ver. YYYY-MM-DD) — Basic Requirements: ...",
     "prescription": "...", "expected_evidence": ["PROOF_OF_FULFILLMENT"]}
  ],
  "meaning": {
    "ran": true,
    "semantic": {"category": "PHYSICAL", "confidence": 0.9,
                 "mismatch": null|"DIGITAL_DECLARED_AS_PHYSICAL",
                 "evidence_span": "item description says 'digital download'"},
    "fraud_warnings": [{"name": "...", "signal_basis": "..."}],
    "unassessable_patterns": [{"name": "...", "reason": "signal not in API"}]
  },
  "corrections": [{"action": "REGISTER_TRACKING", "label": "Add tracking to this order"}]
}
```

- **`expected_evidence`**: 各check行に「違反時に後で要求されうるPayPal証拠種別」をpolicy.pyの写像で付ける(P0-3。「警告=紛争機械の要求と1対1」の実演を運ぶ構造化フィールド)
- `flags`は全capture分配列。旗フィールド不在時はその要素を`{"status": null}`とし、UIは"not present in API response"表示(P2-8)。シナリオ4の「常時表示」はこの3値(値/不在/ラベル)で担保
- `fraud_warnings`(一致のみ)と`unassessable_patterns`(判定不能のみ)は配列分離(P2-7)。評価済み非一致パターンは返さない
- `meaning.ran=false`時: `semantic`はnull・意味層依存check行は`not_assessable`のまま残す(行を消さない=FR-8の「未実施」明示)。`fraud_warnings`/`unassessable_patterns`は**表駆動のためLLM不要・常に返す**(P1-3)
- `summary`集計は成功基準「2種類のverdict」の比較単位=「fail statusを含むcheck集合」で測る(P2-4)

`POST /track` 入力 `{"capture_id","tracking_number","carrier","carrier_name_other?"}` → trackers-batch POST → GET読戻しを返す。`GET /health` = backend生存確認+LLM利用可否。

## 非機能(性能・権限・セキュリティ・ログ)

- 権限: backendは127.0.0.1のみlisten。拡張のhost_permissionsは`127.0.0.1`+`*.sandbox.paypal.com`のみ(content scriptのmatchも同じ・本番paypal.comには注入しない=P1-4c)。**backendへの全fetchはpanel.js/service workerからのみ**
- 認証: `POST /track`は`X-Preflight-Token`ヘッダ必須(P1-5)。トークンはserver起動時に生成して`~/.config/preflight/preflight-token`に書き、拡張のoptionsページに人間が1回貼る(127.0.0.1はブラウザ内の全サイトから到達可能のため)
- 秘匿: client_secret・LLMキー・トークンはenvファイルのみ・レスポンス・ログに出さない(既存スクリプトと同じ)
- 失敗時: ①backend停止→拡張は"backend offline"表示 ②LLM不可(env無し・実行時失敗=quota/ネットワーク断も同じ)→`meaning.ran=false`で退化(P2-6) ③trackers POSTエラー→API応答をそのまま表示 ④注文ID同定失敗→手動入力フィールドを常時用意(**デモ再現性のため自動抽出に依存しない**)
- 性能: 1注文チェック=OAuth1回+order GET1回+trackers GET1回+LLM1回以内(+初回ID解決時capture GET1回)(P2-1)

## ルール層の条件表(US規約ピン)

| 条件 | 判定入力 | fail時の処方(固定文字列) |
|---|---|---|
| SHIP_TO_TRANSACTION_ADDRESS | `purchase_units[].shipping`有無+住所不一致(REDIRECT) | 住所無し: "Do not ship — obtain the buyer's confirmed address via a new transaction" / 不一致: "Ship only to the address on the transaction" (P2-5で分岐) |
| TRACKING_REQUIRED | `GET /v1/shipping/trackers?transaction_id=`で番号有無 | "Add tracking — button (REGISTER_TRACKING)" |
| PHYSICAL_GOODS_DECLARED | `items[].category` | 物理以外→INTANGIBLE_ADDITIONAL_REQS行へ遷移(**この行自体はfailにしない**) |
| INTANGIBLE_ADDITIONAL_REQS | 意味層`semantic.category`がDIGITAL/SERVICE系 | **status固定=`not_assessable`**+処方"Keep fulfillment logs/proof of service delivery per US Intangible Goods Additional Requirements"(「デジタル一律対象外」誤ルールの再現禁止=P1-2b) |
| HIGH_VALUE_SIGNATURE | 金額≥**$750 USD**(US規約署名確認閾値表・paypal.com/us/legalhub + seller-protection PDFで確認済み・P2-3解消) | "Use signature confirmation" |
| SHIP_WITHIN_DAYS | `order.create_time`+規約日数から残日数計算・閾値未満で警告 | "Ship within the required window" |
| EXCLUDED_CATEGORY | `items[].name`/`description`のpolicy.py除外語照合(車両・不動産等) | "Category excluded from Seller Protection" |

## 意味層の設計(AI #2・P1-2/P1-3反映)

- **2部品分離**: ①`semantic`=LLM依存(品目説明文→固定enum分類) ②`fraud`=表駆動(PayPal文書化パターン×API可視シグナルの静的写像・LLM不要)
- LLM出力enum: `DIGITAL|PHYSICAL|SERVICE|MADE_TO_ORDER|PRE_ORDER` + confidence + 根拠span
- **無争議症例のみフラグ**(説明文が明示的にdigital/made-to-orderを含む場合)。曖昧は`mismatch=null`
- 不一致→check発火の写像(policy.py固定表): `DIGITAL_DECLARED_AS_PHYSICAL`→INTANGIBLE_ADDITIONAL_REQS行+対応clause / `MADE_TO_ORDER_DECLARED_AS_STOCK`→SHIP_WITHIN_DAYS行+対応clause(P1-2a)
- 詐欺パターン: APIに無いシグナル依存パターンは`unassessable_patterns`に配置(判定不能枠・成功基準)。LLM停止でも返す
- LLMへの指示は分類のみ。**規約解釈・処方生成・裁定予測を一切させない**(処方=policy.py固定表)
- LLM検出: `ANTHROPIC_API_KEY`または`GEMINI_API_KEY`のenv有無で選択・無しまたは実行時失敗で`meaning.ran=false`(FR-8)

## 拡張側の責務(panel.js)

- 前回verdictを`sessionStorage`に`order_id`キーで保持→再チェック時にcheck行のstatus差分を「before→after」で描画(P0-2・シナリオ9)
- 修正フォーム: `REGISTER_TRACKING`選択時に追跡番号入力+キャリア選択を表示。carrierはpolicy.pyの固定enum(UPS/USPS/FEDEX/DHL/OTHER等)・OTHER時は`carrier_name_other`必須入力(P1-6)
- 旗ブロック: `flags`全件を「declared-data snapshot」ラベル付きで常時描画(値なし=not present表示)

## 検討した代替案と却下理由

| 案 | 却下理由 |
|---|---|
| もっと単純な案: CLIのみ(sandboxスクリプトを繋ぐ) | ユーザーがブラウザ拡張を選択済み(デモの見せやすさ=ハッカソン勝敗軸) |
| 拡張内に認証情報を埋めてPayPal直叩き | client_secretが拡張パッケージから誰でも抜ける+CORS |
| フルWebアプリ(別画面) | 拡張形態の決定と矛盾・「コンソール上に重ねる」が製品の売り |
| LLMに規約解釈させる柔軟な判定 | 審査員条件3違反(規約を書いた審査員の前で誤助言するリスク) |
| 裁定予測の表示 | FR-5違反・「負けます」とは言えない |
| 注文ID同定をDOM自動抽出のみに依存 | 未実測のため手動入力を常時併用(デモ再現性・前提欄の注記) |
| Orders v2 `/track`エンドポイント(trackers-batchの後継) | trackers-batchはdeprecatedだが**sandbox実測済み**を優先。後継は同POST系で移行コスト低い(P2-2注記) |

## テスト方針(受入シナリオ→テストの対応)

| 受入シナリオ# | テスト種別 | 機械判定 |
|---|---|---|
| 1,3(ルール層合否) | 単体(fixtures) | ✓ |
| 2(意味的不一致+clause併記) | 単体(fixture+LLMモック/明示的症例のみ) | ✓ |
| 4(旗ラベル常時・3値) | panel.js単体+E2E目視 | 半 |
| 5(追跡登録→読戻し) | E2E sandbox実API | ✓ |
| 6(無形品経路・not_assessable) | 単体(rules) | ✓ |
| 7,8(詐欺パターン可視/判定不能) | 単体(fixtures) | ✓ |
| 9(前後比較) | E2E(panelのsessionStorage差分を検証する結合テスト+手動確認) | 半 |
| 10(コンソール上で拡張起動) | 手動(sandboxコンソールで実クリック) | 手動 |

**先頭検証タスク**: コンソール注文詳細画面で取引IDがDOMから取得可能か(前提欄の未実測項) — 設計着手直後に手動確認。不可なら手動入力のみでも要件を満たせる(フォールバックは必須機能として残す)
