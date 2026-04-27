# PICU Evidence Daily — セットアップ・運用ガイド

小児集中治療領域の最新エビデンスを毎日Instagram投稿する自動化システム。

## 目次

1. 全体構成
2. 初期セットアップ
3. API設定
4. ローカルでのテスト実行
5. GitHub Actionsによる自動化
6. 日常運用フロー
7. カスタマイズ
8. トラブルシューティング

---

## 1. 全体構成

```
picu-evidence-daily/
├── scripts/
│   ├── pubmed_fetcher.py   # PubMed E-utilities で論文取得
│   ├── summarizer.py       # Claude API で構造化要約を生成
│   ├── infographic.py      # Pillow でインフォグラフィック画像生成
│   ├── instagram_poster.py # Instagram Graph API で投稿
│   ├── pipeline.py         # 統合パイプライン（メイン実行ファイル）
│   └── config.env.example  # 環境変数テンプレート
├── .github/workflows/
│   └── daily_post.yml      # GitHub Actions 定時実行設定
├── data/                   # 取得した論文データ（JSON）
├── output/                 # 生成されたインフォグラフィック画像
├── logs/                   # 投稿済みPMID記録
├── requirements.txt
└── SETUP_GUIDE.md          # このファイル
```

処理フロー: PubMed検索 → 論文選定（スコアリング） → Claude要約 → 画像生成 → Instagram投稿

---

## 2. 初期セットアップ

### 2.1 Python環境

```bash
# Python 3.10以上推奨
python --version

# リポジトリをクローン（またはダウンロード）
git clone https://github.com/YOUR_USERNAME/picu-evidence-daily.git
cd picu-evidence-daily

# 依存パッケージをインストール
pip install -r requirements.txt
```

### 2.2 日本語フォント

インフォグラフィック生成には日本語フォントが必要。

**macOS:**
```bash
# macOSはヒラギノが標準搭載。infographic.pyのフォントパスを変更:
# FONT_CJK = "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"
# または Noto Sans CJK をインストール:
brew install --cask font-noto-sans-cjk-jp
```

**Ubuntu/Debian:**
```bash
sudo apt-get install -y fonts-noto-cjk
```

**フォントパスの設定:** `scripts/infographic.py` 冒頭のフォントパスを環境に合わせて変更してください。

```python
# macOS の場合
FONT_CJK = "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"
FONT_LATIN = "/System/Library/Fonts/Helvetica.ttc"
FONT_LATIN_BOLD = "/System/Library/Fonts/HelveticaNeue.ttc"

# Ubuntu (Noto Sans CJK) の場合
FONT_CJK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_LATIN = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_LATIN_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
```

---

## 3. API設定

### 3.1 Anthropic Claude API（必須）

1. https://console.anthropic.com/ でアカウント作成
2. API Keys から新しいキーを作成
3. 環境変数に設定:
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-xxxxxxxxxxxxx"
   ```

料金目安: 1論文の要約で約 $0.01〜0.03（claude-sonnet-4-20250514使用時）。毎日1投稿で月額 $0.30〜0.90 程度。

### 3.2 NCBI PubMed API Key（推奨）

1. https://www.ncbi.nlm.nih.gov/account/ でNCBIアカウント作成
2. Settings → API Key Management で生成
3. 環境変数に設定:
   ```bash
   export NCBI_API_KEY="xxxxxxxxxxxxxxxx"
   ```

API Keyなしでも動作するが、rate limitが3 req/sec → 10 req/secに緩和される。

### 3.3 Instagram Graph API（投稿用）

これが最も手順が多い部分です。

#### Step 1: Facebook Developer アカウント
1. https://developers.facebook.com/ でアカウント作成
2. 「マイアプリ」→「アプリを作成」→ ビジネスタイプ選択

#### Step 2: Instagram Business/Creator Account
1. Instagramアプリでプロフェッショナルアカウントに切り替え
2. Facebookページを作成し、Instagramアカウントと連携

#### Step 3: Graph API トークン取得
1. Graph API Explorer (https://developers.facebook.com/tools/explorer/) を開く
2. 必要な権限を追加:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_show_list`
   - `pages_read_engagement`
3. 「Generate Access Token」でユーザートークンを取得
4. 長期トークンに変換:
   ```
   GET https://graph.facebook.com/v19.0/oauth/access_token
     ?grant_type=fb_exchange_token
     &client_id={app-id}
     &client_secret={app-secret}
     &fb_exchange_token={short-lived-token}
   ```

#### Step 4: Instagram Account ID 取得
```
GET https://graph.facebook.com/v19.0/me/accounts?access_token={token}
```
→ Facebookページの `id` を取得

```
GET https://graph.facebook.com/v19.0/{page-id}?fields=instagram_business_account&access_token={token}
```
→ `instagram_business_account.id` が Instagram Account ID

#### Step 5: 環境変数に設定
```bash
export INSTAGRAM_ACCESS_TOKEN="EAAxxxxxxxxx"
export INSTAGRAM_ACCOUNT_ID="17841400000000000"
```

**重要:** 長期トークンも60日で期限切れ。自動更新の仕組みが必要（後述）。

### 3.4 Imgur API（画像ホスティング用）

Instagram Graph APIは公開URLの画像しか受け付けないため、一時的な画像ホスティングが必要。

1. https://api.imgur.com/oauth2/addclient でアプリ登録
2. Client IDを取得
3. 環境変数に設定:
   ```bash
   export IMGUR_CLIENT_ID="xxxxxxxxxxxxxxx"
   ```

**代替案:** AWS S3、Cloudflare R2、Google Cloud Storageなども利用可能。その場合は `instagram_poster.py` の `upload_to_imgur` を差し替えてください。

### 3.5 LINE Notify（任意・通知用）

投稿候補の確認通知やエラー通知に使用。

1. https://notify-bot.line.me/ でトークン取得
2. 環境変数に設定:
   ```bash
   export LINE_NOTIFY_TOKEN="xxxxxxxxxxxxxxxxx"
   ```

### 環境変数の一括設定

```bash
cp scripts/config.env.example .env
# .env を編集して各値を設定
# 以下で読み込み（bash/zshの場合）
export $(cat .env | grep -v '^#' | xargs)
```

---

## 4. ローカルでのテスト実行

### 画像生成のみテスト（API不要）

```bash
cd scripts
python infographic.py
# → output/ に4枚のサンプル画像が生成される
```

### PubMed検索テスト（NCBI API Key推奨）

```bash
cd scripts
python pubmed_fetcher.py
# → 直近30日の小児集中治療関連論文を検索
```

### フルパイプライン（投稿なし）

```bash
cd scripts
python pipeline.py --no-post --output-dir ..
# → PubMed検索 → Claude要約 → 画像生成 まで実行
```

### フルパイプライン（投稿前確認あり）

```bash
cd scripts
python pipeline.py --output-dir ..
# → 最後に投稿確認のプロンプトが表示される
```

### 特定論文を指定

```bash
cd scripts
python pipeline.py --pmid 39876543 --no-post --output-dir ..
```

---

## 5. GitHub Actionsによる自動化

### 5.1 リポジトリ設定

1. GitHubにprivateリポジトリを作成
2. コードをプッシュ
3. Settings → Secrets and variables → Actions で以下を設定:
   - `ANTHROPIC_API_KEY`
   - `NCBI_API_KEY`
   - `INSTAGRAM_ACCESS_TOKEN`
   - `INSTAGRAM_ACCOUNT_ID`
   - `IMGUR_CLIENT_ID`
   - `LINE_NOTIFY_TOKEN`（任意）

### 5.2 ワークフロー

`.github/workflows/daily_post.yml` が毎朝7:00 JST（22:00 UTC）に自動実行。

手動実行もGitHubのActions画面から可能（workflow_dispatch）。

### 5.3 トークン自動更新

Instagram長期トークンは60日で期限切れ。以下のワークフローを追加して自動更新:

```yaml
# .github/workflows/refresh_token.yml
name: Refresh Instagram Token
on:
  schedule:
    - cron: '0 0 1,15 * *'  # 毎月1日と15日
jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - name: Refresh token
        run: |
          NEW_TOKEN=$(curl -s "https://graph.facebook.com/v19.0/oauth/access_token?\
          grant_type=fb_exchange_token&\
          client_id=${{ secrets.FB_APP_ID }}&\
          client_secret=${{ secrets.FB_APP_SECRET }}&\
          fb_exchange_token=${{ secrets.INSTAGRAM_ACCESS_TOKEN }}" | jq -r '.access_token')
          # GitHub CLI でSecretを更新
          gh secret set INSTAGRAM_ACCESS_TOKEN --body "$NEW_TOKEN"
        env:
          GH_TOKEN: ${{ secrets.GH_PAT }}
```

---

## 6. 日常運用フロー

### 全自動モード（推奨開始時はこちらから）

1. GitHub Actionsが毎朝自動実行
2. LINE通知で投稿候補を確認
3. 問題があればGitHubのActions画面から確認・再実行

### 半自動モード（品質管理重視）

1. `--no-post` で画像生成まで自動実行
2. 生成された画像を確認
3. 問題なければ手動で投稿コマンドを実行

### 手動モード

1. 気になる論文のPMIDを指定して実行
2. 画像を確認・必要に応じて修正
3. 投稿

---

## 7. カスタマイズ

### 対象ジャーナルの追加・変更

`pubmed_fetcher.py` の `TARGET_JOURNALS` リストを編集:

```python
TARGET_JOURNALS = [
    '"Pediatric critical care medicine"[Journal]',
    # 追加例:
    '"Resuscitation"[Journal]',
    '"Acta Paediatrica"[Journal]',
]
```

### 検索キーワードの変更

`pubmed_fetcher.py` の `PEDIATRIC_TERMS` を編集。

### インフォグラフィックのデザイン変更

`infographic.py` の `COLORS` ディクショナリでカラーパレットを変更可能:

```python
COLORS = {
    "bg":       "#FFFFFF",    # 白背景に変更
    "card_bg":  "#F5F5F5",
    "accent":   "#2196F3",    # 青アクセント
    # ...
}
```

### 要約プロンプトのカスタマイズ

`summarizer.py` の `SYSTEM_PROMPT` を編集することで、要約のスタイルやフォーマットを調整できる。

---

## 8. トラブルシューティング

**Q: PubMedから論文が取得できない**
- `--days-back 30` で検索期間を広げてみる
- NCBI API Keyが正しいか確認
- NCBIのサービス状況を確認: https://www.ncbi.nlm.nih.gov/stat

**Q: Claude APIでエラーが発生する**
- APIキーが有効か確認
- クレジット残高を確認（https://console.anthropic.com/）
- Rate limitの場合は少し待ってリトライ

**Q: Instagram投稿が失敗する**
- アクセストークンの期限切れが最も多い原因
- Instagram Account IDが正しいか確認
- 画像URLが公開アクセス可能か確認（Imgurの場合はClient IDを確認）

**Q: フォントが文字化けする**
- 日本語フォントがインストールされているか確認
- `infographic.py` のフォントパスが正しいか確認
- `fc-list | grep -i cjk` でCJKフォントの存在を確認

**Q: 投稿済みの論文が再度選ばれる**
- `logs/posted_pmids.json` が正しく更新されているか確認
- GitHub Actions使用時は、commitステップでpushが成功しているか確認

---

## アカウント運用のヒント

- 初期は `--no-post` で画像を確認してから手動投稿する習慣をつける
- 投稿時間は朝7:00前後が医療者のエンゲージメントが高い
- ハッシュタグは10-15個が最適（自動生成+固定タグ）
- ストーリーズへのシェアも手動で行うとリーチが伸びる
- 週末はエンゲージメントが下がるため、平日のみの運用も検討
