#!/usr/bin/env python3
"""
Instagram Graph API を使ってカルーセル投稿を行う。

前提条件:
1. Facebook Developer Accountでアプリ作成済み
2. Instagram Business Account または Creator Account
3. Facebook Page と Instagram Account が連携済み
4. 必要な権限: instagram_basic, instagram_content_publish, pages_show_list

環境変数:
- INSTAGRAM_ACCESS_TOKEN: 長期アクセストークン
- INSTAGRAM_ACCOUNT_ID: Instagram Business Account ID
"""

import json
import os
import re
import ssl
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen, Request

import certifi

_SSL_CTX = ssl.create_default_context(cafile=certifi.where())

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


def get_config():
    """環境変数から設定を取得"""
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    account_id = os.environ.get("INSTAGRAM_ACCOUNT_ID")

    if not token or not account_id:
        raise ValueError(
            "環境変数 INSTAGRAM_ACCESS_TOKEN と INSTAGRAM_ACCOUNT_ID を設定してください。\n"
            "取得方法は運用ガイドを参照してください。"
        )
    return token, account_id


def upload_image(image_url, caption=None, is_carousel_item=True,
                 token=None, account_id=None):
    """画像をInstagramにアップロード（コンテナ作成）

    Args:
        image_url: 公開アクセス可能な画像URL
        caption: キャプション（カルーセルの場合はメインコンテナのみ）
        is_carousel_item: カルーセルの個別アイテムかどうか
    """
    params = {
        "image_url": image_url,
        "access_token": token,
    }
    if is_carousel_item:
        params["is_carousel_item"] = "true"
    if caption and not is_carousel_item:
        params["caption"] = caption

    url = f"{GRAPH_API_BASE}/{account_id}/media"
    data = urlencode(params).encode()
    req = Request(url, data=data, method="POST")

    try:
        with urlopen(req, timeout=30, context=_SSL_CTX) as resp:
            result = json.loads(resp.read())
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Instagram API {e.code}: {body}") from e

    container_id = result.get("id")
    print(f"[Instagram] Image container created: {container_id}")
    return container_id


def create_carousel(children_ids, caption, token=None, account_id=None):
    """カルーセルコンテナを作成"""
    params = {
        "media_type": "CAROUSEL",
        "children": ",".join(children_ids),
        "caption": caption,
        "access_token": token,
    }

    url = f"{GRAPH_API_BASE}/{account_id}/media"
    data = urlencode(params).encode()
    req = Request(url, data=data, method="POST")

    try:
        with urlopen(req, timeout=30, context=_SSL_CTX) as resp:
            result = json.loads(resp.read())
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Instagram API {e.code}: {body}") from e

    carousel_id = result.get("id")
    print(f"[Instagram] Carousel container created: {carousel_id}")
    return carousel_id


def publish(container_id, token=None, account_id=None):
    """コンテナを公開"""
    params = {
        "creation_id": container_id,
        "access_token": token,
    }

    url = f"{GRAPH_API_BASE}/{account_id}/media_publish"
    data = urlencode(params).encode()
    req = Request(url, data=data, method="POST")

    try:
        with urlopen(req, timeout=30, context=_SSL_CTX) as resp:
            result = json.loads(resp.read())
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Instagram API {e.code}: {body}") from e

    media_id = result.get("id")
    print(f"[Instagram] Published! Media ID: {media_id}")
    return media_id


def check_container_status(container_id, token):
    """コンテナの処理状態を確認"""
    params = {
        "fields": "status_code",
        "access_token": token,
    }
    url = f"{GRAPH_API_BASE}/{container_id}?{urlencode(params)}"
    req = Request(url)

    try:
        with urlopen(req, timeout=30, context=_SSL_CTX) as resp:
            result = json.loads(resp.read())
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Instagram API {e.code}: {body}") from e

    return result.get("status_code")


def post_carousel(image_urls, caption, token=None, account_id=None):
    """カルーセル投稿の全フロー

    Args:
        image_urls: 公開アクセス可能な画像URLのリスト（2-10枚）
        caption: 投稿キャプション
    """
    if token is None or account_id is None:
        token, account_id = get_config()

    if len(image_urls) < 2:
        raise ValueError("カルーセルには最低2枚の画像が必要です")
    if len(image_urls) > 10:
        raise ValueError("カルーセルは最大10枚までです")

    print(f"[Instagram] Posting carousel with {len(image_urls)} images...")

    # 1. 個別画像のコンテナを作成
    children_ids = []
    for i, url in enumerate(image_urls):
        print(f"  Uploading image {i+1}/{len(image_urls)}...")
        container_id = upload_image(url, is_carousel_item=True,
                                     token=token, account_id=account_id)
        children_ids.append(container_id)
        time.sleep(1)  # Rate limit対策

    # 2. カルーセルコンテナを作成
    carousel_id = create_carousel(children_ids, caption,
                                   token=token, account_id=account_id)

    # 3. 処理完了を待機
    for attempt in range(10):
        status = check_container_status(carousel_id, token)
        if status == "FINISHED":
            break
        print(f"  Waiting for processing... (status: {status})")
        time.sleep(3)

    # 4. 公開
    media_id = publish(carousel_id, token=token, account_id=account_id)
    return media_id


def _strip_markup(text: str) -> str:
    """インフォグラフィック用マーカー（** / * / ||...||）を除去"""
    text = re.sub(r'\*{3}(.+?)\*{3}', r'\1', text)
    text = re.sub(r'\*{2}(.+?)\*{2}', r'\1', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', text)
    text = re.sub(r'\|\|(.+?)\|\|', r'\1', text)
    return text


def generate_caption(summary: dict) -> str:
    """要約データからInstagramキャプションを生成"""
    def clean(field):
        return _strip_markup(summary.get(field, "") or "").strip()

    def fmt(text):
        """段落区切り（\n\n）を保持しつつ各行を整形"""
        paras = [p.strip() for p in text.split("\n\n") if p.strip()]
        return "\n\n".join(
            "\n".join(ln.strip() for ln in p.split("\n") if ln.strip())
            for p in paras
        )

    hook        = clean("hook")
    background  = clean("background")
    primary     = clean("primary_result")
    secondary   = clean("secondary_results")
    take_home   = clean("take_home")
    limitations = clean("limitations")
    citation    = summary.get("citation", "")
    journal     = summary.get("journal", "")
    year        = summary.get("year", "")
    study_type  = summary.get("study_type", "")
    hashtags    = summary.get("hashtags", [])

    # --- 冒頭フック (hook疑問文 + 論文情報) ---
    hook_block = f"{hook}🤔\n\n今回は{journal} {year}の{study_type}を紹介します📄"

    # --- なぜ重要？ ---
    bg_block = f"📌 なぜ重要？\n{fmt(background)}" if background else ""

    # --- 結果 (primary_result + secondary_results) ---
    pri_text = fmt(primary)
    sec_lines = [ln.strip() for ln in secondary.split("\n") if ln.strip()]
    sec_text  = "\n".join(sec_lines[:6])

    result_parts = [pri_text] if pri_text else []
    if sec_text:
        result_parts.append(f"\n副次的に：\n{sec_text}")
    result_block = "📉 結果\n" + "\n".join(result_parts) if result_parts else ""

    # --- 臨床での見方 ---
    th_block = f"💡 臨床での見方\n{fmt(take_home)}" if take_home else ""

    # --- この研究の限界 ---
    lim_items = [item.strip() for item in limitations.split("\n\n") if item.strip()]
    lim_bullets = []
    for item in lim_items[:3]:
        lines = [ln.strip() for ln in item.split("\n") if ln.strip()]
        if lines:
            lim_bullets.append(f"・{lines[0]}")
    lim_block = ""
    if lim_bullets:
        lim_block = (
            "⚠️ この研究の限界\n"
            + "\n".join(lim_bullets)
            + "\n\nこの研究だけで全例に適用できるわけではありません。"
        )

    # --- CTA ---
    cta_block = (
        "─────────────────\n"
        "小児・集中治療の最新論文を、明日の臨床で使える形でまとめています🩺\n"
        "見逃したくない方はフォローしておいてください📚\n"
        "あとで読み返すなら保存がおすすめです🔖\n"
        "気になる点や現場の経験があればコメントで教えてください👇\n"
        "─────────────────"
    )

    # --- ハッシュタグ（論文テーマ優先 + 固定タグ） ---
    fixed_tags = [
        "PICUEvidenceDaily", "小児科", "集中治療", "医学論文",
        "エビデンス", "研修医", "看護師", "小児集中治療", "PICU",
    ]
    all_tags = list(dict.fromkeys(hashtags + fixed_tags))[:18]
    hashtag_str = " ".join(f"#{t}" for t in all_tags)

    # --- 組み立て ---
    blocks = [b for b in [
        hook_block,
        f"📰 {journal} {year}  |  {study_type}",
        bg_block,
        result_block,
        th_block,
        lim_block,
        cta_block,
        f"📎 {citation}",
        hashtag_str,
    ] if b]

    return "\n\n".join(blocks).strip()


# === 画像ホスティングのヘルパー ===

def upload_to_cloudinary(image_path):
    """Cloudinaryで画像をアップロードして公開URLを取得

    環境変数 CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET が必要
    """
    import cloudinary
    import cloudinary.uploader

    cloudinary.config(
        cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
        api_key=os.environ.get("CLOUDINARY_API_KEY"),
        api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
        secure=True,
    )

    result = cloudinary.uploader.upload(
        image_path,
        folder="picu-evidence-daily",
        resource_type="image",
    )
    url = result["secure_url"]
    print(f"[Cloudinary] Uploaded: {url}")
    return url


if __name__ == "__main__":
    # テスト: キャプション生成のみ
    test_summary = {
        "title_jp": "小児敗血症性ショックに対する早期バソプレシン投与の有効性",
        "journal": "NEJM",
        "year": "2025",
        "study_type": "RCT",
        "key_finding": "早期バソプレシン追加により28日死亡率が有意に低下（18.2% vs 26.7%）",
        "take_home": "小児敗血症性ショックにおいて早期バソプレシン追加は有効。NNT=12。",
        "citation": "Smith J, et al. NEJM. 2025.",
        "hashtags": ["PICU", "Sepsis", "Vasopressin", "小児敗血症", "RCT"],
    }
    print(generate_caption(test_summary))
