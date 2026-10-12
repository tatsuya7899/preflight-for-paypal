# AUDIT — US Seller Protection条項照合(提出パス側タスク S2)

日付: 2026-10-12 / 実施: 監督(一次文書取得+突合)

## 照合対象文書(ピン)

- **文書**: PayPal's Seller Protection Program(US版)
- **URL**: https://www.paypal.com/us/legalhub/paypal/seller-protection
- **版**: "Last updated on January 26, 2026"
- policy.py側のピン定数: `POLICY_DOC_NAME`/`POLICY_DOC_VERSION`/`POLICY_DOC_URL`

## 発見と処置

### ①条項番号「§1(a)〜§2」は文書に実在しない【必須修正→完了】

- **発見**: policy.pyの`clause`文字列が「§1(a)」「§1(b)」「§1(c)」「§1(d)」「§2」を引用していたが、現行文書は番号付き条項を持たず、名前付き節(Basic Requirements / Item Not Received Additional Requirement / Intangible Goods Additional Requirements / Establishing Proof… / Ineligible Items and Transactions)のみ。番号は設計書段階からの創作。
- **処置**: 全7行+MISMATCH写像2行の`clause`を実在の節名+" (ver. 2026-01-26)"付きに書換え。審査員が文書を開いて番号を探しても存在しない=虚偽引用だったため修正必須。

### ②署名確認($750)は現行US版に存在しない【必須修正→完了】

- **発見**: `HIGH_VALUE_SIGNATURE`チェックが「$750以上=署名確認必須」としてfailを出していた。しかし現行US版文書に「signature」の文字は**全文に一度も出現しない**(取得した全221行を確認)。$750閾値表は**他地域版**(SEA/CEMEA= sellerprotection-sea / sellerprotection-cemea)にのみ残存。M2/M7レビューの「版ドリフト兆候」が的中した形。
- **処置**: 当該チェックを`fixed_status: "not_assessable"`(処方専用)に降格 — 現行規約に無い要件を違反と言う=要件の捏造になるためfailは論理上あり得ない。`evaluate()`にfixed_status強制を新規実装(これまでは注記のみで強制機構なし)。処方文言は「defensive practice — not required by current US terms」へ変更。`HIGH_VALUE_NO_SIGNATURE` fraudパターンは残すが説明を「defensive practice(not a requirement)」に訂正。
- **影響**: order_D($800)のverdictで同チェックがfail→not_assessableに変化。テスト2件更新、verdict_F.json再生成、READMEの表記訂正。

### ③除外カテゴリの文言に現行版に無い項目+虚偽陽性リスク【必須修正→完了】

- **発見**: キーワードリストに現行Ineligible Itemsに無い「custom-made item」「ticket for an event」、条件付き除外(UT申立+発効>24h前という品目テキストから判定不能)の「travel ticket」、部分一致で必ず誤爆する「land」(Thailand等に一致)・「car」(care/cargo/cardに一致)・「cash」(cashmereに一致)を含有。「gold」も品物の金(金ネックレス=通常の物理商品)を誤爆するため除去。
- **処置**: 現行Ineligible節に整合させて再構成 — 除去: 上記7件+「property (real estate)」(括弧付きリテラルは実テキストに一致しない)。追加: motorcycle/recreational vehicle/residential property/industrial machinery/prepaid・pre-paid card/stored value/investment/nft/non-fungible/gambling/casino/lottery/crowdfunding/bill payment。NFTは金額ゲート付き除外($10,000.01以上=常に除外・以下はUT申立のみカバー)のため限定事項をコメント明記。

## 確認済み(変更不要だった条項)

- **SHIP_TO_TRANSACTION_ADDRESS** — 「ship to the shipping address on the Transaction Details page」Basic Requirementsに実在 ✓
- **TRACKING_REQUIRED** — 「valid proof of shipment or delivery」Basic Requirementsに実在(tracking number=発送証明の構成要素) ✓
- **PHYSICAL_GOODS_DECLARED** — 「physical, tangible good that can be shipped」Basic Requirementsに実在 ✓
- **INTANGIBLE_ADDITIONAL_REQS** — 同名節が実在(UT申立での旗marked eligible+履行証拠) ✓
- **SHIP_WITHIN_DAYS** — 「pre-ordered/made-to-order=出品で指定した期間内に発送必須・それ以外は7日以内発送を**推奨**」——既修正のrequired/recommended分割は現行版と一致確認 ✓

## 残置・限定事項

- fraud patternのHIGH_VALUE_NO_SIGNATUREは「defensive practice」ラベルで残置(要件ではないがリスク兆候として有用)。
- NFT除外は金額条件のためキーワード一致では「カテゴリ該当の可能性」止まり — check basisが「matched excluded keyword」と正直に書く範囲で運用(偽failでなくヒューリスティックであることはbasisに出る設計)。
- 句レベルの誤爆は設計上残置("boat shoes"→boat、"motorcycle helmet"→motorcycle、"10% donation to charity"→donation、"investment piece"→investment)。旗のbasisが一致キーワードを表示し処方が「verify」と言うため、セラーの判断材料として許容範囲と判断。
- 版ドリフト再発リスク: 提出前に同URLの"Last updated"日付が変わっていないか最終確認要(タスクS5の提出物検収時に再実行)。

## 独立レビュー(2026-10-12)の指摘と対処

ext_review(--files、swe-2-medium)で重要な指摘(P2)3件・軽微な指摘(P3)3件:

| 指摘 | 対処 |
|---|---|
| 重要(P2): 複数形取りこぼし——`\bmotorcycle\b`が"motorcycles"に不検出。真の不適格をpassと誤表示 | パターンに`s?`許容を追加(`\bmotorcycles?\b`) |
| 重要(P2): 綴り揺れ取りこぼし——"gift-card"/"stored-value"/連続空白/"pre paid card"が不検出 | テキストとキーワード双方を区切り正規化(ハイフン・連続空白→単一空白)してから一致 |
| 重要(P2): 死にキーワード——`"item that violates paypal's acceptable use policy"`は全文一致しないと発火しない | `"acceptable use policy"`の短形に置換 |
| 軽微(P3): "motor vehicle"/"recreational vehicle"は`vehicle`が内側一致するため冗長 | 害なし・対象外カテゴリの文書化として残置 |
| 軽微(P3): fixed_status強制ループの実効テストなし(ループを消しても全テスト通る) | `TestFixedStatusEnforcement`追加——fixed_statusを"fail"に一時差替えてevaluate()が"fail"を出すことを検証(ループ非依存では有り得ない挙動) |
| 軽微(P3): レビュー範囲外のfixture/panel整合が未照合 | 本レビュー後にverdict_F.json再生成+resplice+パネルテスト31/31を実行済み(下記検証) |

## 検証

- `pytest tests/` = **101件+13サブテスト全Green**
- パネルブラウザテスト = **31/31 FAIL 0**(verdict_F.json再生成+panel_v6.html resplice後)
- 全fixture再評価: HIGH_VALUE_SIGNATUREが全注文でnot_assessableになったことを実測
- verdict_F.json/panel_v6.htmlに旧条項形式(§引用・signature=fail)の残存なしをgrep確認
