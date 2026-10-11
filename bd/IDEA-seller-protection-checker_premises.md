# 事業設計 前提整理: Seller Protection適合チェッカー(seller-protection-checker)
Created: 2026-10-11 / モード: 早駆け(提出物型 — PayPal AI Hackathon・締切2026-11-12)
領域トリアージ判定: **入場**(追補4・「非agentic×加盟店」セル — 前6案の死に方(不能/占有/荷重不足/自己完結)を全て回避した初めての候補。詳細は`GEN-*_candidates.md`追補4)

[思考ツール: 分解統合 + 国内外先例の照合 + 領域トリアージ]

**15秒の一文**: 「出荷する前に『この注文はPayPalに守ってもらえない』を教える」— Seller Protectionの条件とPayPal公式の詐欺パターンを注文に照合し、**対象外の理由と対象に戻す処方**を出荷前に提示する

## ① マクロ環境(早駆け圧縮)
| # | トレンド | アイデアとの接続 | 追/向 | 出典 |
|---|---|---|---|---|
| 1 | PayPal公式がSeller Protectionの条件と詐欺パターンを文書化しつつ「出荷前に自分で注文を確認せよ」と手に委ねている | **その手作業の自動化が本件** — スポンサー自身の文書が「この作業が要るが、やるのはあなた」と明言 | 追 | paypal.com Seller Protection条件・詐欺パターン文書(HELP1029・HELP201・ecommerce security guide) |
| 2 | Seller ProtectionはPayPalのStripeへの差別化要因 | 保護利用の拡大=スポンサーの競争優位の増幅。「PayPalが食える市場」の法則に合致 | 追 | paypal.com/us/business/risk-management |
| 3 | 紛争処理系は全員係争後(Chargeflow=PayPalサービス・DisputeOps・Anixem等) | **出荷前の予防層は空き** — 「保護条件の適合」は「詐欺リスク」とも「紛争処理」とも違う第3の層 | 追(空白) | 追補4スイープ |
| 4 | orders/shipment APIは公開・sandbox動作 | 荷重APIが実在・実装可能 | 追 | developer.paypal.com + @paypal/agent-toolkit |

### 先例3社(停止・同型を優先)
| 事業 | 状態 | 同じ/違う | 沈んだ理由の適用可否 |
|---|---|---|---|
| Verdikx | 活動中 | 同じ「注文時の証拠確保」/違い=証拠保存+詐欺スコアで、**Seller Protectionの適合条件の診断ではない** | 近接だがジョブが違う(証拠保管≠適合診断) |
| Chargehound(PayPal買収) | 活動中 | 同じ「紛争」/違い=**係争後の対応自動化**で出荷前ではない | 係争後の占有者。自案は時間軸が別 |
| PayPal標準の取引詳細 | 出荷中 | 「対象/非対象」の旗は出すが**理由と処方は出さない** | 旗だけでは対象外の修正方法が分からない=差分の実体 |

## ② 領域スコープ
- 関連領域: PayPalセラーの注文リスク管理 / Seller Protection適合 / 出荷前診断 / 詐欺パターン検知 / 証拠衛生
- 選択スコープ: **出荷前の「Seller Protection適合診断」** — orders/shipment APIで注文を読み、PayPal公式の保護条件と詐欺パターンに照合し、「対象外の理由+対象に戻す処方」を提示する
- 選択理由: PayPal固有の仕様(保護条件・公式詐欺パターン)が荷重=「PayPal無しに作れない」が成立。対象者=全PayPalセラー(実在)。スイープで同ジョブの占有者なし →訂正: Guzcoがサービス一機能として部分占有(下の更新節)。「セルフサーブ製品の占有者なし」が正

## ③ 立ち位置
- 実施主体: 個人(ソロ)
- 必然性: ①PayPal sandbox Orders実装経験+API資産(orders/shipment)が直結(技術Edge) ②PayPal公式の保護条件・詐欺パターンの文書を仕様の根拠にできる(調査Edge) ③「紛争前の診断」というジョブの位置は、紛争処理勢(係争後)とリスク勢(詐欺スコア)の間の穴
- 他ではできない理由: 大手はエンタープライズ向けで小規模セラーの「出荷前に1件ずつ教えてほしい」をしない。PayPal自身は条件を文書化するが診断は提供しない

## ④ 価値単位
- 主語: **出荷前の「保護適合診断」の仕組み**(注文→条件照合→対象外理由+処方)
- 定義: 「支払いが通ったか」でも「紛争に勝つか」でもなく「**この注文はSeller Protectionの条件を満たして出荷できるか**」を事前に診断する層
- 選択理由: 保護条件はPayPal固有の公開仕様・詐欺パターンはPayPal公式文書=両方とも「スポンサー自身の仕様書きに由来する」差分

## ⑤ 人物像(JTBD準拠)
### Primary: PayPalで物販を受ける小規模セラー
- 状況: 注文が入り発送準備をしている。Seller Protectionの条件(取引明細の住所に送る・追跡情報・非除外品目等)を細部まで覚えていない。「保護されるか」は対象旗だけでは分からず、対象外のまま出荷→紛争で商品と金を両方失うリスクを抱えている
- ジョブ: 機能=出荷前に「この注文は保護対象か」を確認し、対象外なら何を修正すれば対象になるかを知る / 感情=「気づかず保護外で出荷して負ける」不安の解消 / 社会=「PayPalに守ってもらえる取引をしている」という安心
- スイッチ: Push=条件の複雑さ・「対象外で出荷した」後悔 / Pull=出荷前に理由と処方が出る診断 / Anxiety=誤診(対象と誤判定して実は対象外) — 対策=判定はルール層(決定的)で行いAI層は説明と詐欺照合のみ / Habit=PayPalの取引詳細を目視するが細部は読まない
- 顧客寿命: PayPalが診断を内蔵するまで(=PayPalが「出すのは旗だけで診断は手に委ねる」現状の解消)
- 証拠強度: **中〜強** — PayPal公式の条件文書・詐欺パターン文書・「自分で確認せよ」の要求は一次情報=困りが実在。対象者の実在性(全セラー)は先行層問題を持たない

### Secondary: PayPal新規導入の小規模セラー
- 状況: PayPalを始めたばかりでSeller Protectionの存在自体を知らない/使い方を知らない
- ジョブ: 機能=初注文から保護適合を意識させる / 感情=「PayPalに守られる」ことを学ぶ / 社会=「守られたセラー」としての信頼

## ⑥ 問題の質(6属性・出典つき)
| 属性 | 証拠 |
|---|---|
| よくある | **全PayPalセラー=実在** — 物販セラー全員がSeller Protectionの対象・非対象に関わる(出典: PayPal Seller Protection条件の適用範囲=全取引) |
| 増えている | PayPalのagentic推進+Seller Protectionの拡張=保護の複雑さが増す方向(出典: PayPal risk-managementページ) |
| 急ぐ | **出荷後には遅い** — 対象外条件で出荷すると紛争で負ける。診断は出荷前にしか効かない |
| 高くつく | 対象外出荷の損失=商品+送料+金額の全損+紛争手数料(出典: PayPalの詐欺パターン文書「商品も金も失う」) |
| やらざるを得ない | PayPal公式が「出荷前に注文を自分で確認せよ」と要求=手作業が課されている |
| 頻繁 | 受注ごと=毎日出荷するセラーなら日次 |
証拠あり: **6/6**(全て一次情報: PayPal公式文書)

## ⑦ 利用者制約
- 「血肉になることしかいや」— 保護プログラムの衛生管理はPayPal固有だが、「条件適合の事前診断」という製品核は他PSP(Stripe Seller Protection等)にも横展開できる=提出後も生きる資産

## 構造破壊の準備(破壊対象の思い込み3つ)
| # | 思い込み | 破壊する構造 |
|---|---|---|
| 1 | 「Seller Protectionは取引が非対象か対象かの旗だけ」 | 旗の裏の**条件の内訳と処方**(なぜ非対象か・どうすれば対象になるか)が実際の価値 |
| 2 | 「紛争対策=係争後の対応」 | **出荷前の診断**で防げる紛争がある=時間軸を前にずらす |
| 3 | 「詐欺対策=リスクスコア」 | PayPal公式が**文書化した詐欺パターン**(住所変更要求・前払いラベル・過払い等)の照合は「スコア」でなく「**スポンサー自身の文書との照合**」=審査員が書いたルールを審査員の前で自動化する形 |

## 対象者接点設計
- 対象者=全PayPalセラー(実在・先行層問題なし)。接点=sandbox注文の読み取り(orders API)+shipment情報(tracking登録の有無)=**技術的接点はAPIで届く**
- 行動的接点: 出荷前という「まだ間に合う瞬間」に介入するため、利用者が「警戒している」必要がない(到達パラドックスを回避 — 注意喚起でなく作業の一部として出す形)

## 競合スイープの検索語と出典(実行済み記録)
| 層 | 検索語 | 出典 |
|---|---|---|
| 同ジョブ | "PayPal Seller Protection eligibility checker before shipping" / "is this order protected" tool | ~~「出荷前の適合診断」を名乗る製品なし~~ **→下の更新節で訂正: Guzcoが同ジョブをサービス一機能として提供済み(セルフサーブ製品は引き続き未発見)** |
| 別形同ジョブ | "chargeback prevention evidence readiness" / "pre-dispute" | Verdikx(証拠保存)・DisputeOps(係争後)・Verifi(自動返金)=いずれも出荷前の適合診断でない |
| スポンサー自前 | PayPal公式文書 | 対象旗は出すが理由・処方・詐欺照合なし。詐欺パターンと条件は文書化=**スポンサーネイティブ空白が実在** |
| コード層 | GitHub "seller protection" "paypal eligibility" | (補足: ツール系の占有者はリポジトリに住む——コード層スイープも実行済み・該当なし) |

### 競合スイープの更新(2026-10-11・生成の分業の実走で発見)

**新事実: Guzco(guzco.ai)が同ジョブを部分占有** — 「Seller Protection requirements checked at checkout and pre-shipment・address mismatches・missing signature on high-value orders・ineligible item typesをfulfilmentへflag」と製品ページ(guzco.ai/solutions/paypal)で明言。上表の「製品なし」判定はこの時点で更新必要となった(Guzcoはスイープ時に見落とし)。ただし構造: Guzcoは**紛争対応のdone-for-youサービス**(Talk to an Expert型・Shopify連携・中規模セラー向け)の一機能としての事前チェック。「出荷前適合診断を主看板にしたセルフサーブ型ツール」は引き続き未発見。**残る差別化**: ①セルフサーブ×長尾(紛争サービス料金が見合わない層) ②PayPal自身の`seller_protection.status`旗をオラクルとして並置表示(~~Guzcoは自社ルール判定~~ →追補1で撤回・反証あり) ③AIの意味層(カテゴリ詐称検出) ④診断→追跡登録→再検証の閉ループをワンクリックで。Gate 0審査員へは「サービスの一機能 vs セルフサーブの製品」の棲み分けで説明する。

**生成の分業(v1.22)の実証記録**: 2系統の生成エージェント(殺し履歴・本候補の存在を知らないクリーンルーム系α / スポンサーネイティブ・ヒューリスティック系β)を並列走行。結果: **βは本候補と同一点に独立収束**=ヒューリスティックの最適解が本候補を指す裏付け(収束の証拠)。αは異なる3候補(紛争対応Copilot・回収交渉Autopilot・Console拡張)を生成=他の空き地の輪郭も確認(発散の実績)。併せてαの新発見: **sandbox Disputes APIは全ライフサイクル再現可能**(create dispute/require-evidence/provide-evidence/settleの限定メソッド+buyer側クレデンシャル)=Gate 0条件2の2幕デモで「保護外注文が実際に紛争に負ける」まで実演できる可能性が開けた。

## Gate 0追加確認(提出物型判定): **適用**(核がソフトウェア提出物のため)
| 確認項目 | 対応 |
|---|---|
| 「既存の仕組みで足りる」反論 | 最接近=PayPal取引詳細の対象旗(実名: Seller Protection適合表示)。**残る差分**: 旗は出すが「理由・処方・詐欺パターン照合」は出さない — PayPal公式が「自分で確認せよ」と手作業を要求しているのが証拠 |
| 証拠の外部性 | **PayPal sandboxの実注文データ=第三者発行** + Seller Protection条件=PayPal公式文書=両方とも自己生成でない外部アンカー |
| 計量の判定主体 | 適合判定は**ルール層(決定的: 追跡番号有無・住所一致・品目除外等の機械照合)**が本体。AI層は**詐欺パターンの意味照合・処方生成・除外品目の意味判定**に限定 — オラクル不信を回避する2層設計(判定=ルール、説明=AI) |
| 評価セットの健全性 | 判定基準=PayPal公式の保護条件・詐欺パターン(自己生成でない)。評価入力=sandbox注文(自分で作るが、条件照合の正解は公式文書由来=クリーン) |
| 差分の実体対応 | 「出荷前の適合診断」=orders読取り+条件照合エンジン+詐欺パターンマッチャー+処方生成器+警告UIの名指し |
| 先行技術スイープ(実施済み) | 上記「競合スイープ」に記録+コード層を含む |
| 空白の理由と土台の実在性 | 空白の理由=PayPalが条件を文書化するが診断を提供しない(機能の設計判断=空白は意図的)。土台=orders/shipment API公開・sandbox動作確認済み=**実在** |
| 実演入力の外部性 | sandbox注文は自分で作るが、**判定の正解=PayPal公式の条件文書**=自己生成でない(「この注文は対象外」の正解はPayPalが決めている) |
| 検証器のSUT実在 | SUT=PayPal sandbox上の注文=**実在**(公開APIで作成・読取可能)。模擬でなく実API |
| 外部依存の物理検証(3分類) | ①orders API=検証済み(agent-pay-guardian資産) ②shipment API=公開・sandbox ③Seller Protection条件=公式文書=即時確認可。**承認待ちの依存なし**(Agent Readyのような申請制でない) |
| 本体の最低品質 | sandboxで「対象外注文→診断→理由・処方提示→修正→対象内」の前後を完走 |

## PayPal技術の荷重(スポンサー必然性の明記)
| 要素 | 荷重の形 |
|---|---|
| orders/shipment API | 診断対象の入力=**荷重そのもの** |
| Seller Protection適合条件 | PayPal固有の仕様=「PayPal無しに作れない」が成立 |
| 公式詐欺パターン文書 | PayPalが文書化したパターンを照合=**スポンサー自身の言葉に由来する差分** |
| AI(要件の意味ある統合) | 詐欺パターンの意味照合(「この注文は文書化されたパターンに一致するか」の意味判定)+除外品目の意味判定+処方の自然言語生成=**判定の説明層で荷重**(ルール層だけでは「なぜ」が出せない) |

## 検証充足計画(各Gate条件をどう満たすかの事前宣言)
| Gate | 条件 | 充足経路 |
|---|---|---|
| Gate 0 | 仮想審査員レビュー | 本書+公式審査基準+スポンサー文書を委任文に明記して実施(次工程) |
| 対話相当(Gate 2) | 対象者=全PayPalセラー(実在)のため会話ルート理論上は可能 — ただし締切(11/12)までの期間・相手調達の現実を見て「**PayPalセラーの実利用者への実演**」を最低ラインに代替検証として選択(会話10件でなく「実セラーが実注文で使った」1回の実演を目指す) | — |
| 実演(提出物型Gate 4相当) | sandbox注文の作成→診断→警告→修正→対象内の完走+sandbox上での実演記録 | 外部アクセス不要=全て手の届く範囲 |

## 前提の最もリスクの高い仮定
- **「PayPalが既に対象旗を出しているのに、なぜ別のツールが要るか」** — 差分は「理由+処方+詐欺パターン照合」の3層。この差分が審査員に「PayPalの機能で足りるのでは」と読まれるか(=仮想審査員が最も攻める点)。対抗=「旗はYes/Noだけで、なぜ・どう修正するかは出さない」はPayPal公式文書の記述から一次情報で立つ

## Gate 0条件1の実測結果(2026-10-11・sandbox実測): **スタブ判明**

`sandbox/verify_sp.py`+`verify_sp2.py`+`capture_check.py`で6注文を作成→sandbox個人アカウント(sb-k6b9g53303451@personal.example.com)で承認→capture。結果:

| # | 条件 | captureのseller_protection |
|---|---|---|
| A | PHYSICAL_GOODS+住所あり($10・対照) | `ELIGIBLE` + [ITEM_NOT_RECEIVED, UNAUTHORIZED_TRANSACTION] |
| B | DIGITAL_GOODS($10) | `ELIGIBLE` + 同一カテゴリ |
| C | PHYSICAL_GOODS・shipping欠落 | `ELIGIBLE` + 同一カテゴリ |
| D | PHYSICAL_GOODS $800+住所(署名閾値越え) | `ELIGIBLE` + 同一カテゴリ |
| E | items無し・金額のみ | `ELIGIBLE` + 同一カテゴリ |
| F | shipping_preference:NO_SHIPPING | `ELIGIBLE` + 同一カテゴリ |

**判定**: 条件を最大限変えても常時`ELIGIBLE`+固定`dispute_categories`=**sandboxのseller_protectionは条件評価しないスタブ**。フィールド自体は実在(形式も本物)だが、デモで「PayPal自身の旗がNOT_ELIGIBLEを返す」は**sandboxでは作れない**。

**ただし死ではない可能性の反論**: 「旗は申告データしか見ない」は本製品の核心を裏付ける——PayPalの旗がELIGIBLEと言う注文でも、申告が意味的に嘘(カテゴリ詐称)なら紛争時に負ける。旗のスタブ性は「旗の上に意味層が要る」という製品の存在意義そのものの実演材料になりうる。

## 仮想審査員・条件1再判定(2026-10-11): **条件つきGo維持(29/50→条件充足で36〜38)**

- **旗は唯一のオラクルではなかった**: PayPal規約自体「marked eligible=必要条件の一つ」と明記→「旗ELIGIBLE≠裁定保証」は契約文言そのもの。正解のオラクルは規約文書
- **より強い代替オラクル発見**: sandbox Disputes API全工程(create-dispute→require-evidence→adjudicate→settle=限定メソッド実在・evidence_typeの実値が返る)=「出荷前に警告した証拠を紛争機械が後で要求する」まで実演可能=act-3オラクル
- **禁止事項**: 「旗ELIGIBLE vs 我々の違反」の裸の対置(審査員に「スタブが言ってるだけ」と読まれる)。旗には常時「宣言値スナップショット(必要条件)」ラベル+我々の診断は旗の定義域外に配置
- **dispute_categories=[INR,UNAUTHORIZED]は仕様正しい**(SNADはSeller Protection非対象)=「ELIGIBLEでもSNAD紛争は守らない」は追加の実演材料
- **新必須条件**: ①Disputes lifecycle実測(失敗=NoGo) ②payment_source変動で旗が動くか ③3幕構成のデモ再設計 ④意味層は無争議症例のみ ⑤規約はUS版にピン(デジタル品は無形品要件で対象になる管轄あり) ⑥tracking登録の書き込みもsandbox実測要(書き込みスタブの可能性)
- **条件②の降格注記(2026-10-11・M2/M7レビュー由来)**: ②は旗がスタブと判明したことで「オラクルが動くか」の前提自体が変化したため、必須条件から残条件(P1タスク)へ降格——変動確認は引き続き提出前に実施するが、Go判定のブロッカーではない

## Gate 0判定(仮想審査員・2026-10-11): **条件つきGo(現形30/50・条件充足で35〜38見込み)**

**審査員の事前検証で出た新事実**: `seller_protection.status`はOrders v2のcaptureリソースに実在(ELIGIBLE/PARTIALLY_ELIGIBLE/NOT_ELIGIBLE + dispute_categories)=**PayPal自身の旗をAPIで引ける=第三者発行オラクルが実在**。ただし旗は「資格の前提条件のスナップショット」で、請求時裁定に効く行為条件(指定住所発送・追跡・リダイレクト禁止・SNAD非対象・最終裁量)は旗の外に残る。

**承認条件(全て必須・順序つき)**:
1. **事前検証ゲート(最優先・半日)**: sandboxでDIGITAL_GOODS/住所欠落の注文を作りcaptureが実際に`NOT_ELIGIBLE`を返すか確認。**常時ELIGIBLEかフィールド欠落ならPayPal旗オラクル消滅→NoGoに再判定**
2. **デモ機構の正直化**: 同一取引の旗反転は機構的に不可能(NOT_ELIGIBLEの典型原因=デジタル品・除外品目・分割払いは出荷前に直せない)。2幕構成に再設計: ①NOT_ELIGIBLE注文→条件名指し→履行方法変更で再作成→PayPal旗がELIGIBLE ②ELIGIBLE注文への**DON'T SHIP判定**(詐欺パターン一致=本当の劇薬)。ツール表示の横に常にPayPal自身の旗を並置
3. **AI荷重の山場確定**: 「APIカテゴリ詐称の意味キャッチ」(APIはPHYSICAL_GOODS申告だが意味的にデジタル/オーダーメイド)をデモに必須化。処方は固定表(LLMに規約解釈をさせない — 規約を書いた審査員の前で間違った助言を言うリスク回避)
4. **書き込みアクション追加**: 追跡番号をPayPal側に登録するワンクリック修正で診断→処置→再検証の閉ループ
5. **詐欺パターンの正直な二分**: API可視シグナル vs メッセージ依存パターンをUIで分けて表示。「APIに無いものは見えない」と言う誠実さ=審査員の信頼
6. 補助(任意): 「agent起点の注文こそ適合チェックが要る」の一線でagenticレーンの空気に乗る(偽装は見抜かれるので薄く)

**審査員の指摘で崩れた本書の記述**: 「同一取引で対象外→修正→対象内」の実演設計は機構的に不可能と判明(条件2で再設計必須)。「頻繁=日次」の主張は実態より強い(紛争率<1%=深刻だが散発的→「毎注文にかかるpre-flightチェック」の言い換えで正当化する方針)。

## Disputes APIライフサイクル実測(2026-10-11・ケースPP-R-XGB-10190971): **act-3オラクル実在確認**

買い手がResolution Centerから手動でINR紛争を作成(対象=FのNO_SHIPPING注文・capture `3J366679AY2283450`)→エスカレート→証拠提出→追加情報、までAPIで実測した記録。

**確認できた実機械(全て実API応答)**:

| 観測 | 実値 |
|---|---|
| 紛争詳細GET(直接) | 200・全項目返却(一覧APIは空=伝播なし・直接IDのみ可視) |
| ライフサイクル遷移 | `INQUIRY` →(買い手昇格)→ `CHARGEBACK` / status `UNDER_REVIEW`→`WAITING_FOR_SELLER_RESPONSE`→証拠提出で`UNDER_REVIEW`戻り |
| **証拠要求(自動)** | 昇格と同時に `evidence_type=PROOF_OF_FULFILLMENT` `source=REQUESTED_FROM_SELLER` が追加=**PayPal機械が「履行証拠を出せ」を実値で要求** |
| **資金保留** | `fund_movements`に `DEBIT $9.34` `reason=HOLD_PLACED` + `transaction_status=HELD` =紛争額が売り手残高から実際に保留 |
| 売り手行動 | `provide_evidence`(200受理)・`accept_claim`・`provide_supporting_info`のリンクが状態に応じてHATEOASで出現/消滅 |
| 状態機械の正当性 | 状態外の操作は `ACTION_NOT_ALLOWED_IN_CURRENT_DISPUTE_STATE` で確実に拒否 |
| 紛争取引の保護判定 | `seller_protection_eligible=true` `seller_protection_type=EXPANDED_SELLER_PROTECTION` (NO_SHIPPING注文にもかかわらず=こちら側もスタブ挙動) |

**未達**: `adjudicate`リンクは最後まで出現せず(UNDER_REVIEW/CHARGEBACKで`provide_supporting_info`のみ残る)。裁定=PayPal内部の時限処理の可能性。sandboxでBUYER_FAVOR/SELLER_FAVORの終着をAPI引きする経路は未発見(accept_claimで売り手負け返金に自力閉じる経路はWAITING_FOR_SELLER_RESPONSE時に存在した)。

**デモへの含意**: 審査員のact-3条件の核心「出荷前に警告した証拠を紛争機械が後で要求する」は**PROOF_OF_FULFILLMENT要求+資金保留で実演可能=合格相当**。裁定結果の実演は欠けるが、因果連鎖(警告→紛争→証拠要求→資金凍結)は全部実API。デモ台本: 「我々の警告した証拠種別 = PayPalが実際に要求したevidence_type」を1対1で画面に並べる。

## Shipment tracking登録実測(2026-10-11): **書き込みは実物=スタブでない**

`POST /v1/shipping/trackers-batch` + `GET /v1/shipping/trackers?transaction_id=` を実測(`sandbox/tracking_test.py`):

| 対象取引 | POST結果 | GET読戻し |
|---|---|---|
| A物理品(`4EC24563F7235632E`) | `errors: []` 受理 | `status=SHIPPED` `carrier=UPS` `tracking_number` `shipment_uploader=MERCHANT` 全実値 |
| F NO_SHIPPING・紛争中(`3J366679AY2283450`) | `errors: []` 受理 | 同上。**「発送しない宣言」の注文にも事後で追跡登録可能** |

HATEOASにPUT(replace)/PATCH(edit)リンク=更新系も開放。**診断→処置(追跡登録)→再検証(GET)の閉ループが全て実APIで構成可能**=審査員条件4(書き込みアクション)の技術的成立を確認。

## 実測の追加発見(2026-10-11・rules実装中): **PayPalはshipping省略時に買い手既定住所を自動注入する**

注文作成時にshippingを省略した注文Cで、`purchase_units[].shipping.address`には買い手の既定住所(JP)が入っていた。つまり**APIデータ上「住所が無い」は作りにくい**——住所の有無チェックは「merchantが配送先を確定したか」ではなく「API上に住所が見えるか」しか分からない。真の住所なし症例はshipping_preference=NO_SHIPPINGの注文F(`shipping=null`)。製品への含意: 「住所あり=pass」は形式的適合のみを意味し、merchantがその住所に送る意図があったかは判別不能=正直な限界としてUI文言に反映する価値あり。

## 最終判定(仮想審査員・2026-10-11): **Go — 36/50**

条件つきGoから**Go**へ昇格。NoGo連動条件だった2つ(Disputes lifecycle実測・tracking書き込み実測)が共に実測通過したため「存在証明の段階は終了」。残条件(3幕構成・無争議症例・US規約ピン)は建造要件へ降格。帯の下位(36)理由: adjudicate未達・payment_source未検証・紛争n=1・**製品本体がまだ0行**(sandbox/は検証プローブのみ)。

**act-3オラクル成立の論理**: オラクルに必要なのは「PayPal機械が後でXを要求する」であって裁定結果ではない。`PROOF_OF_FULFILLMENT`要求=警告証拠種別と1対1一致、`HOLD_PLACED`=「警告を無視した代償」の視覚的実演(裁定文より強い幕の閉じ方)。adjudicate不在は欠陥でなく構造(裁定はPayPalレビューチームの人的工程=Guzco公式playbookと一致)。

**文言規律(義務)**: 「あなたは負けます」は禁止。言えるのは「PayPalが要求した証拠=我々が警告した証拠」「資金が凍結された」まで。パンチライン候補: **「The flag evaluates what you declared. The dispute evaluates what you did.」**(US規約「may be eligible」「sole discretion」の文言に依拠=sandbox依存を脱した主張)。規約上「旗」は常時「declared-data snapshot」ラベル併記・「スタブ」の語は提出物に使わない。

**提出までのクリティカルパス**: P0-1 診断エンジン実装(ルール層+意味層+固定処方表) / P0-2 US規約ピン(Intangible Goods Additional Requirementsの存在=「デジタル一律対象外」は誤ルール) / P0-3 3幕デモ台本+録画 / P1 紛争n=2再現・payment_source変動・AI審査フィルター対策7項目・README=デモ台本化・Guzco差分1文。

**製品化の率直評価**: Guzco差別化は座標として立つが堀は未証明。弱さ4点: ①Sherlockリスク(PayPal本体が機能内蔵したら消える) ②distributionが本質的コスト(配送/OMS組込みが要) ③意味層のground truth依存 ④紛争率<1%で単体課金は薄い。現実的な行き先: 配送/リスティングツール組込みor証拠衛生〜係争証拠パッケージへ拡張。「旗は宣言値しか見ない(sandbox観測)」は問題の存在証明として使えるが文言は「sandboxで観測」に留める。

## 追補1(2026-10-11・Gate 1レビュー由来 — 未検証断定の訂正)

**訂正対象**: 「残る差別化 ②PayPal自身の`seller_protection.status`旗をオラクルとして並置表示(Guzcoは自社ルール判定)」の括弧内断定。

**反証**: Guzco公式ページ(guzco.ai/solutions/paypal)の案件UIスクリーンショットに「SP Eligible」「SP Not covered」のタグ表示がある(PayPalの旗か自社判定かの区別はつかないが、少なくとも保護適格の表示はしている)=括弧内の断定「Guzcoは自社ルール判定」は一次確認できず反証が存在するため撤回。

**併せて確認した新事実**: Guzcoは「provider-specific evidence playbooks」としてreason-code→必須証拠フィールドの写像を公開済み(guzco.ai/resources・2026-07-24付)=条件↔証拠写像は文書形で既存。**SyncPal**(syncpal.co)は追跡番号のShopify/Woo→PayPal自動同期で書き込み側を隣接占有(同ジョブでなく隣接)。

**差別化の訂正後の残り**: ①セルフサーブ×長尾(Guzcoの料金形が見合わない層・PayPalコンソール内在形) ②旗と行為条件の**乖離の露出**(Guzcoは旗か自社判定のどちらかを出すが乖離は出していない=未発見) ③AIの意味層 ④診断→追跡登録→再検証の閉ループ。②が差別化の実質で、③は退化時も正直表示の設計。

**波及**: dtfのZ軸は「写像の存在」から「旗と条件の乖離の露出」に再特定済み(IDEA-..._dtf.mdレバーC参照)。

## 追補2(2026-10-11・Gate 3レビュー由来 — 競合スイープの追加層)

Canvas Gate 3の類似チェックで発見した追加占有・隣接者(上流反映・ADR同伴):

- **追跡同期系はカテゴリとして密**: SyncPalの他に**TrackiPal**(PayPal公式Approved Partner)・Synctrack・Proveway・Trackshore等。全件ストア側から同期する型で「どの注文に追跡が要るか」の診断はしない=書き込み側の隣接占有層
- **PayPal自前の予防層**: Chargeback Protection/危険取引の事前警告・取引詳細の旗=不正リスク側で「保護条件の適合」は診ない(GEN追補3と整合)
- **保証付きship判定層**: Riskified・Signifyd・Shopify Protect等はcheckout時点でapprove/rejectを返し係争責任を負う。「出荷するか」判断の別形占有者だがSP条件適合は診ず価格帯も中規模〜(長尾外)

**波及**: 占有の密度は「追跡書き込み側」と「ship判定側」に厚い。弊案の残る位置=「**この注文はどの保護条件が欠けているかの診断**を、PayPalコンソール内在・セルフサーブ・旗乖離の露出で出す」組合せ(未発見継続)。

## 追補3(2026-10-11・M2/M7独立レビュー由来 — 提出要件と規約の一次確認で得た新事実)

- **【重大】Devpost公式要件は「審査員が実際に動かせるワーキングビルド」** — "judges must be able to actually run or interact with a working build… A design mockup, static prototype, or non-functional demo does not meet this requirement"。デモ動画+READMEだけでは要件不適合。**backendのfixtureモード起動手順+sandbox資格情報取得〜拡張sideloadの導入手順書が提出要件に追加**となった
- **既存資産の再利用は規約適合** — "new or existing projects, as long as you make meaningful progress during the course of the hackathon"。提出窓は10/01開始=_archive資産改造+10/11以降の実装は窓内
- **MSC期日の実測値** — 結果発表=12/21・審査=12/01〜12/15(Devpost schedule)。「入賞」証拠の検収可能時点は11/12ではなく12/21
- **賞金上限の実測値** — 1プロジェクトの受賞上限=Grand Prize 1つ+スポンサー賞1つ(Section 8)=実質上限~$17,000級
- **紛争率<1%の外部傍証** — PayPal公式High Volume Dispute Fee発動閾値=1.5%・第三者推定=0.60%/txn。「<1%」は平均セラーの近似として妥当だが対象セグメント固有の率は引き続き未検証(「仮説」区分維持)
- **US規約の版ドリフト(文言監査が必須と確定)** — SHIP_WITHIN_DAYSは要件でなく推奨("it is recommended"=通常品7日・pre-order/MTOのみspecified timeframeが義務)。HIGH_VALUE_SIGNATUREは2026-01-26以降mandatory→recommendedに版ドリフト兆候(legalhub側は閾値表を掲載継続)=**条項根拠は現行US版の文書日付にピンが必要**。policy.pyのbasis文言に「required」誤記があると審査員の前で誤助言になる
- **Gate 0新必須条件②(payment_source変動)の降格明文化** — 旗スタブ判明でオラクル前提自体が変化したため残条件へ降格(P1タスクとして日程化)
