# レビュー観点: extension/panel.html + panel.js(tasks#11 拡張パネル実装)

対象ファイル:
- /Users/tatsuyasasaki/Developer/_incubator/paypal-ai-hack-2026/extension/panel.html
- /Users/tatsuyasasaki/Developer/_incubator/paypal-ai-hack-2026/extension/panel.js

参照(契約の正本):
- /Users/tatsuyasasaki/Developer/_incubator/paypal-ai-hack-2026/extension/background.js (check/track/healthメッセージ)
- /Users/tatsuyasasaki/Developer/_incubator/paypal-ai-hack-2026/extension/content.js (extract応答形)
- /Users/tatsuyasasaki/Developer/_incubator/paypal-ai-hack-2026/backend/rules.py (evaluate()のverdict形)
- /Users/tatsuyasasaki/Developer/_incubator/paypal-ai-hack-2026/backend/server.py (/check,/trackの応答形・エラー形)
- /Users/tatsuyasasaki/Developer/_incubator/paypal-ai-hack-2026/scratch/verdict_F.json (実verdict例・修正済み生成物)

## レビュー観点(敵対的に)
1. **メッセージ契約の一致**: panel.jsが送るペイロードがbackground.js/content.jsの受け側と完全一致するか(キー名・型)
2. **MV3制約**: inline scriptなし・inlineイベントハンドラなし・CSP違反なし
3. **表示の正直さ**: データが無いものを出さないか(実在しないdispute情報・SEEN IN A REAL CASE等を捏造していないか)。「not run」「cannot produce」等の否定表現が正しく表示されるか
4. **証拠スロットの導出ルールの妥当性**: deriveSlotState()の論理 — fail参照+全failが「do not ship」→unfillable、fail参照+修正可能ならfillable、pass参照のみ→小チップ。このルールが「スロット=その証拠をこの注文でまだ作れるか」の意味に一致するか、反例はないか
5. **track→re-checkの流れ**: carrier=OTHERのバリデーション・/track失敗時の扱い・成功後に再checkを呼ぶか・before/afterが前verdictとの実差分を出すか
6. **XSS/注入**: verdict由来の文字列がinnerHTMLに入る箇所でesc()抜けがないか
7. **chrome API不在時**: 拡張コンテキスト外で開いたとき異常終了しないか
8. **文言規律**: 「declared-data snapshot」併記・裁定予測をしない表現・「not legal advice」の存在

出力形式: 指摘を「必須修正(P0)/推奨修正(P1)/任意修正(P2)」の3段で、対象ファイルと行番号つきで列挙。最後に `VERDICT: PASS` または `VERDICT: ISSUES` の1行。
