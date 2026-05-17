# PICU Evidence Daily — 開発ログ

コードの変更経緯・設計判断・トラブルシューティングを記録する。
git commit メッセージで分かる「何を変えたか」ではなく、「なぜそうしたか」を残す。

---

## 2026-05-10

### キャプション末尾に論文URLを追加
**ファイル:** `scripts/instagram_poster.py` / `generate_caption()`

DOI があれば `https://doi.org/{doi}`、なければ `https://pubmed.ncbi.nlm.nih.gov/{pmid}/` をハッシュタグの直前に挿入。
Instagram はリンクをタップできないが、コピーして開ける。生物医学論文の多くは DOI で確実に辿れるため DOI 優先とした。

---

### Slide 3「対象」見出し重なり修正
**ファイル:** `scripts/infographic_bg.py` / `s3_background()`

**問題:** 背景PNG に焼き込まれた「対象」見出し（y ≈ 715–865px）に `pop_html` が重なって読めなくなる。

**原因:** `pop_html` の `top:760px` が見出し帯の内部だった。また `bg_html` に `max-height` がなく、長文のときに見出し帯まで伸びていた。

**修正:**
- `bg_html`: `max-height:510px; overflow:hidden` を追加 → y=670px で打ち切り（見出し帯開始 715 より手前）
- `pop_html`: `top:760px` → `top:870px`（見出し帯終了 865 の下）、`max-height:360px; overflow:hidden` 追加

**数値の根拠:**
- 「対象」見出しの実測値: y=715〜865px（背景PNG を目視確認）
- `bg_html` の上端が y=160px なので、510px の余裕で 670px まで → 715 との間に 45px のバッファ
- `pop_html` の下限: 870 + 360 = 1230px（フッター余白 120px 確保）

---

### QA チェック 2種追加
**ファイル:** `scripts/infographic_bg.py` / `_render_html_to_png()`

既存の `canvas_overflow` / `container_clipping` に加え:

**`heading_body_overlap`**
背景PNG の見出し帯（`_SLIDE_HEADING_ZONES` で定義）と `.text-block` の Y 軸重複を Playwright JS で検出。
重複が 10px 超でエラー（10px 閾値は float 誤差・padding を除外するため）。
フォントスケールを下げても解消しない場合は投稿をブロックする。

**`text_block_overlap`**
`.text-block` 同士の X/Y 両軸重複を検出。X>5px かつ Y>10px で報告。
Slide 4 の PICO-O 行が「方法」見出し帯に侵入するケースなどで有効。

**見出し帯の座標定義 (`_SLIDE_HEADING_ZONES`)**
```
Slide 3: [90,165] (背景) / [715,865] (対象)
Slide 4: [50,130] (PICO) / [710,845] (方法)
Slide 5: [38,155] (結果) / [638,758] (二次結果)
Slide 6: [38,140] (批判的吟味)
Slide 7: [70,240] (Take Home Message)
```
これらは背景 PNG を目視で実測した値。背景画像を差し替えた場合は再測定が必要。

**Slide 7 の特殊挙動:**
コンテンツ div が `height:550px; overflow:hidden; display:flex; justify-content:center` のため、テキストが 550px を超えると上方向にはみ出して論理的に見出し帯と重なる（視覚上は overflow:hidden でクリップされる）。`heading_body_overlap` が検知してフォントスケールリトライを促す動作は正しい。

---

### フォントスケールリトライ機構
**スケール:** `[1.0, 0.88, 0.78, 0.70]`

いずれのスケールでも QA が通らない場合は `RuntimeError` を raise → 投稿ブロック。
スケール 0.70 = 元サイズの 70%。これ以上小さくすると可読性が著しく損なわれるため上限とした。
スケールを選んだ根拠: 0.88 ≈ 1段階縮小（読みやすさ維持）、0.78 ≈ 2段階、0.70 = 限界。

---

## 2026-05-08

### Instagram トークン失効と更新手順
**症状:** Run #12 は成功したがアカウントに投稿が見当たらない → ログ確認で `OAuthException 190/460`。

**原因:** Facebook がセッションを無効化（パスワード変更・長期未更新等）。

**更新手順:**
1. Facebook Developers の Graph API Explorer を開く
2. アプリ: `picu-evidence-daily`、権限: `instagram_basic, instagram_content_publish, pages_show_list, pages_read_engagement, business_management` を選択してトークン生成
3. `fb_exchange_token` エンドポイントで短期→長期トークンに交換（有効期限 60 日）
4. `.env` の `INSTAGRAM_ACCESS_TOKEN` を更新
5. GitHub Secret `INSTAGRAM_ACCESS_TOKEN` を REST API 経由で更新

**長期トークン交換コマンド（概要）:**
```
GET https://graph.facebook.com/v21.0/oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id={FB_APP_ID}
  &client_secret={FB_APP_SECRET}
  &fb_access_token={SHORT_LIVED_TOKEN}
```

---

### `instagram_poster.py` の HTTP エラーサイレント問題
**症状:** API エラーが発生しても例外が握りつぶされてパイプラインが成功扱いになっていた。

**修正:** `urllib.error.HTTPError` をキャッチして `RuntimeError` に変換、レスポンスボディをログ出力するよう全 API 関数に追加。

---

### GitHub Actions コミットステップ失敗（Run #13）
**症状:** `git pull --rebase` が `output/` ディレクトリの unstaged 変更で失敗。

**原因:** Actions が生成した PNG ファイルが unstaged のまま rebase を試みていた。

**修正:** コミットステップから `git pull --rebase` を削除。`git add logs/posted_articles.json` → `git diff --staged --quiet || git commit` のみ実行するよう変更。

---

## レイアウト設計の原則（スライド共通）

### 座標系
- キャンバス: 1080 × 1350 px（Instagram 縦型）
- 背景画像: PNG で見出し文字が焼き込み済み → テキストは絶対配置でオーバーレイ
- 座標原点: 左上

### テキストはみ出し防止の方針
1. `max-height + overflow:hidden` を持つコンテナを使う（QA の `container_clipping` で検出可能）
2. 見出し帯の Y 範囲に `.text-block` の top/bottom が侵入しないよう絶対配置を設計
3. フォントスケールで対応できない構造的な問題（位置ズレ等）は、スケール変更前に先に位置を修正する

### 日本語改行制御
- `.text-block` に `word-break:normal; line-break:strict` を適用
- 改行させたくない語句（薬剤名・統計値・略語など）は `<span class="nowrap">` でラップ
- `_NOWRAP_TERMS` と `_NOWRAP_PATTERNS` で管理。長い語句を先に定義しないと部分マッチで短い方に吸収される

---

## 既知の制限事項

- **Slide 7 の `height:550px`**: `justify-content:center` のために固定高が必要。`max-height` に変えると縦中央が崩れる。テキストが長すぎる場合は `heading_body_overlap` → フォントスケールリトライで対応。
- **背景座標は目視測定**: 背景 PNG を差し替えたら `_SLIDE_HEADING_ZONES` の値を再測定すること。
- **Instagram アクセストークンの有効期限**: 長期トークンでも 60 日。GitHub Actions が失敗したら真っ先にトークン期限を確認する。
- **LINE_NOTIFY_TOKEN**: ローカル実行時はネットワーク到達不可でエラーになるが、パイプラインはブロックされない（通知失敗は非致命的扱い）。
