#!/usr/bin/env python3
"""
PICU Evidence Daily — 統合パイプライン
=====================================
1. PubMed から最新論文を取得
2. Claude API で構造化要約を生成
3. インフォグラフィック画像を生成
4. (オプション) Instagram に自動投稿

Usage:
    # フルパイプライン（投稿前に確認あり）
    python pipeline.py

    # 特定PMIDの論文を処理
    python pipeline.py --pmid 39876543

    # 画像生成まで（投稿なし）
    python pipeline.py --no-post

    # 自動投稿モード（確認なし、cron向け）
    python pipeline.py --auto

環境変数:
    ANTHROPIC_API_KEY     - Claude API キー（必須）
    NCBI_API_KEY          - PubMed API キー（推奨、rate limit緩和）
    INSTAGRAM_ACCESS_TOKEN - Instagram トークン（投稿時のみ）
    INSTAGRAM_ACCOUNT_ID   - Instagram アカウントID（投稿時のみ）
    CLOUDINARY_CLOUD_NAME  - Cloudinary クラウド名（画像ホスティング用）
    CLOUDINARY_API_KEY     - Cloudinary APIキー
    CLOUDINARY_API_SECRET  - Cloudinary APIシークレット
    LINE_NOTIFY_TOKEN      - LINE通知トークン（承認フロー用、任意）
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# .envを読み込む（scriptsの親ディレクトリにある）
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

# 同ディレクトリのモジュールをインポート
sys.path.insert(0, str(Path(__file__).parent))

from pubmed_fetcher import fetch_latest, efetch, normalize_title
from summarizer import summarize_with_claude

# 画像生成エンジン: 背景画像+Playwright
from infographic_bg import generate_carousel
print("[Pipeline] Using background-image renderer")

from instagram_poster import generate_caption, post_carousel, upload_to_cloudinary


def notify_line(message, token=None):
    """LINE Notifyで通知を送信"""
    token = token or os.environ.get("LINE_NOTIFY_TOKEN")
    if not token:
        return

    from urllib.request import Request, urlopen
    from urllib.parse import urlencode

    url = "https://notify-api.line.me/api/notify"
    data = urlencode({"message": message}).encode()
    req = Request(url, data=data, method="POST",
                  headers={"Authorization": f"Bearer {token}"})
    try:
        with urlopen(req, timeout=10) as resp:
            print("[LINE] Notification sent")
    except Exception as e:
        print(f"[LINE] Notification failed: {e}")


HISTORY_FILE = "posted_articles.json"   # logs/ 以下に置く
OLD_PMID_FILE = "posted_pmids.json"


def _load_history(log_dir: Path) -> tuple:
    """投稿履歴を読み込む。破損時はsys.exitで停止（重複投稿防止）。
    returns: (records, pmid_set, doi_set, title_norm_set)
    """
    new_file = log_dir / HISTORY_FILE
    old_file = log_dir / OLD_PMID_FILE
    records  = []

    if new_file.exists():
        try:
            with open(new_file, encoding="utf-8") as f:
                records = json.load(f)
            if not isinstance(records, list):
                raise ValueError("posted_articles.json is not a list")
        except Exception as e:
            print(f"[CRITICAL] 投稿履歴ファイルが壊れています: {e}")
            print("[CRITICAL] 重複投稿を防ぐためパイプラインを停止します。")
            sys.exit(1)
    elif old_file.exists():
        print("[History] posted_pmids.json → posted_articles.json へ移行します")
        with open(old_file, encoding="utf-8") as f:
            old_pmids = json.load(f)
        records = [
            {"pmid": p, "doi": "", "title": "", "title_normalized": "",
             "journal": "", "year": "", "first_author": "",
             "posted_at": "", "instagram_media_id": ""}
            for p in old_pmids
        ]
        with open(new_file, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        print(f"[History] {len(records)} 件を移行しました")

    pmid_set  = {r["pmid"]             for r in records if r.get("pmid")}
    doi_set   = {r["doi"]              for r in records if r.get("doi")}
    norm_set  = {r["title_normalized"] for r in records if r.get("title_normalized")}
    return records, pmid_set, doi_set, norm_set


def _is_posted(article: dict, pmid_set: set, doi_set: set, norm_set: set) -> bool:
    """PMID / DOI / タイトル正規化 のいずれかが一致したら投稿済み"""
    if article.get("pmid") and article["pmid"] in pmid_set:
        return True
    doi = article.get("doi", "")
    if doi and doi in doi_set:
        return True
    tn = normalize_title(article.get("title_en", ""))
    if tn and tn in norm_set:
        return True
    return False


def _save_history(article: dict, media_id: str, log_dir: Path) -> None:
    """投稿成功後にのみ呼ぶ。失敗時は呼ばない。"""
    new_file = log_dir / HISTORY_FILE
    records  = []
    if new_file.exists():
        with open(new_file, encoding="utf-8") as f:
            records = json.load(f)

    records.append({
        "posted_at":          datetime.now().isoformat(),
        "pmid":               article.get("pmid", ""),
        "doi":                article.get("doi", ""),
        "title":              article.get("title_en", ""),
        "title_normalized":   normalize_title(article.get("title_en", "")),
        "journal":            article.get("journal", ""),
        "year":               article.get("year", ""),
        "first_author":       article["authors"][0] if article.get("authors") else "",
        "instagram_media_id": media_id,
    })

    with open(new_file, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"[History] 投稿履歴を保存 (PMID: {article.get('pmid')})")


def run_pipeline(args):
    """メインパイプライン"""
    base_dir = Path(args.output_dir)
    data_dir = base_dir / "data"
    output_dir = base_dir / "output"
    log_dir = base_dir / "logs"

    for d in [data_dir, output_dir, log_dir]:
        d.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d")

    # 投稿履歴を読み込み（破損時はsys.exitで停止）
    _, pmid_set, doi_set, norm_set = _load_history(log_dir)

    # ===== Step 1: 論文取得 =====
    print("\n" + "="*60)
    print("Step 1: PubMed から最新論文を取得")
    print("="*60)

    ncbi_key = os.environ.get("NCBI_API_KEY")

    if args.pmid:
        # 特定のPMIDを処理
        articles = efetch([args.pmid], api_key=ncbi_key)
        if not articles:
            print(f"PMID {args.pmid} が見つかりません")
            return
    else:
        articles = fetch_latest(
            days_back=args.days_back,
            top_n=args.top_n,
            api_key=ncbi_key
        )

    if not articles:
        print("新しい論文が見つかりませんでした。")
        notify_line(f"[PICU Evidence Daily] {date_str}: 新しい論文なし")
        return

    # 投稿済みを除外（PMID / DOI / タイトル正規化で判定）
    new_articles = [a for a in articles if not _is_posted(a, pmid_set, doi_set, norm_set)]
    if not new_articles:
        print("すべて投稿済みです。")
        return

    # 最もスコアの高い論文を選択
    article = new_articles[0]
    print(f"\n選択された論文:")
    print(f"  PMID: {article['pmid']}")
    print(f"  Type: {article['study_type']}")
    print(f"  Journal: {article['journal']}")
    print(f"  Title: {article['title_en'][:80]}...")

    # ===== Step 2: 構造化要約 =====
    print("\n" + "="*60)
    print("Step 2: Claude API で構造化要約を生成")
    print("="*60)

    summary = summarize_with_claude(article, api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # 要約を保存
    summary_path = data_dir / f"summary_{article['pmid']}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"要約を保存: {summary_path}")

    # ===== Step 3: インフォグラフィック生成 =====
    print("\n" + "="*60)
    print("Step 3: インフォグラフィック生成")
    print("="*60)

    slide_paths = generate_carousel(summary, str(output_dir))

    print(f"生成完了: {len(slide_paths)} 枚")
    for p in slide_paths:
        print(f"  {p}")

    # ===== Step 4: 投稿 =====
    if args.no_post:
        print("\n[--no-post] 投稿はスキップします。")
        print("生成された画像を確認してください。")
        return

    caption = generate_caption(summary)
    print(f"\n生成されたキャプション:\n{'-'*40}")
    print(caption)
    print(f"{'-'*40}")

    if not args.auto:
        # 手動確認モード
        notify_line(
            f"\n[PICU Evidence Daily] 投稿候補\n"
            f"PMID: {article['pmid']}\n"
            f"{summary['title_jp']}\n"
            f"Journal: {article['journal']} ({article['year']})\n"
            f"Key: {summary['key_finding'][:80]}..."
        )

        response = input("\n投稿しますか? (y/n): ").strip().lower()
        if response != "y":
            print("投稿をキャンセルしました。")
            return

    # 画像をアップロード
    print("\n画像をアップロード中...")
    image_urls = []
    for p in slide_paths:
        url = upload_to_cloudinary(str(p))
        image_urls.append(url)

    # Instagram投稿
    print("\nInstagramに投稿中...")
    try:
        media_id = post_carousel(image_urls, caption)
        print(f"\n投稿完了! Media ID: {media_id}")

        # 投稿成功後にのみ履歴保存（失敗時は保存しない）
        _save_history(article, media_id, log_dir)

        notify_line(f"[PICU Evidence Daily] 投稿完了!\n{summary['title_jp']}")
    except Exception as e:
        print(f"\n投稿エラー: {e}")
        notify_line(f"[PICU Evidence Daily] 投稿エラー: {e}")


def main():
    parser = argparse.ArgumentParser(description="PICU Evidence Daily Pipeline")
    parser.add_argument("--pmid", help="特定のPMIDを処理")
    parser.add_argument("--days-back", type=int, default=7,
                        help="何日前まで遡って検索するか (default: 7)")
    parser.add_argument("--top-n", type=int, default=5,
                        help="候補論文数 (default: 5)")
    parser.add_argument("--no-post", action="store_true",
                        help="画像生成まで（投稿しない）")
    parser.add_argument("--auto", action="store_true",
                        help="自動投稿モード（確認なし）")
    parser.add_argument("--output-dir", default=".",
                        help="出力ディレクトリ (default: .)")
    args = parser.parse_args()

    run_pipeline(args)


if __name__ == "__main__":
    main()
