# レビュー観点: fixtureモード(tasks S1 — 審査員実行経路)

対象ファイル(今回新設のfixtureモードを含む全体を読んでレビューせよ。
未コミット差分を見たければ `git -C <repo> diff HEAD` を実行してよい):
- <repo>/backend/server.py (fixture分岐+索引+起動フラグ)
- <repo>/extension/panel.js (health fixture表示)
- <repo>/tests/test_server.py (FixtureModeTest)
- <repo>/README.md (審査員手順)

参照(契約の正本):
- <repo>/backend/rules.py (evaluate()のverdict形)
- <repo>/backend/paypal.py (live経路の解決順)
- <repo>/backend/fixtures/ (実fixture)

## レビュー観点(敵対的に)
1. **live経路との等価性**: fixture分岐はpaypal.pyの解決順(order_id優先→capture解決→order取得)と論理等価か。fixtureモードでlive経路のペイロード契約が崩れないか(応答キー・エラー形)
2. **モード混入リスク**: _fixture_modeの切替が漏れた経路はあるか(例: fixture中にpaypal.get_token()が呼ばれる経路、live時にfixture索引が使われる経路)
3. **状態リーク**: _fixture_trackersのメモリ状態がorder/captureをまたいで混入しないか。サーバ再起動なしで複数ID操作したときの分離性
4. **認証**: fixtureモードでも/trackのX-Preflight-Token検査が通っているか(審査員手順がtoken貼付を含む設計)
5. **README手順の正確さ**: 書かれた手順が実際のコード・manifest・options.htmlの振る舞いと一致するか(capture_id表・起動コマンド・トークンパス・拡張の読み込み方)
6. **テストの妥当性**: FixtureModeTestがlive経路をmockせずfixture実データで検証しているか、状態の後始末(他テストへの污染)が正しいか

出力形式: 指摘を「必須修正(P0)/推奨修正(P1)/任意修正(P2)」の3段で、対象ファイルと行番号つきで列挙。最後に `VERDICT: PASS` または `VERDICT: ISSUES` の1行。
