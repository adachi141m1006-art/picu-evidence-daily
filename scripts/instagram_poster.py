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
import ssl
import time
from urllib.parse import urlencode
from urllib.request import urlopen, Request

import certifi

_SSL_CTX = ssl.create_default_context(cafile=certifi.where())

# 新Instagram Login APIはgraph.instagram.comを使用
GRAPH_API_BASE = "https://graph.instagram.com/v21.0"


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

    with urlopen(req, timeout=30, context=_SSL_CTX) as resp:
        result = json.loads(resp.read())

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

    with urlopen(req, timeout=30, context=_SSL_CTX) as resp:
        result = json.loads(resp.read())

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

    with urlopen(req, timeout=30, context=_SSL_CTX) as resp:
        result = json.loads(resp.read())

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

    with urlopen(req, timeout=30, context=_SSL_CTX) as resp:
        result = json.loads(resp.read())

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


def generate_caption(summary):
    """要約データからInstagramキャプションを生成"""
    hashtags = summary.get("hashtags", ["PICU", "小児集中治療", "エビデンス"])
    hashtag_str = " ".join(f"#{tag}" for tag in hashtags)

    journal    = summary.get('journal', '')
    year       = summary.get('year', '')
    study_type = summary.get('study_type', '')
    title_jp   = summary.get('title_jp', '')
    background = summary.get('background', '')
    key_finding = summary.get('key_finding', '')
    primary_result = summary.get('primary_result', '')
    take_home  = summary.get('take_home', '')
    citation   = summary.get('citation', '')

    # stats の上位3つ
    stats = summary.get('stats', [])[:3]
    stats_lines = '\n'.join(f"  ▸ {s}" for s in stats) if stats else ''

    caption = f"""🔬 {title_jp}
━━━━━━━━━━━━━━━━━━
📰 {journal} {year}  |  {study_type}

【なぜ重要？】
{background}

【Key Finding】
{key_finding}

【主要結果】
{primary_result}
{stats_lines}

【Take Home Message】
{take_home}

スライドを全部見ると理解が深まります📊
気に入ったら保存 & シェアしてください💾

📎 {citation}
━━━━━━━━━━━━━━━━━━
{hashtag_str}
#PICUEvidenceDaily #小児科 #集中治療室 #医学論文 #エビデンスベース医療 #研修医 #看護師 #小児集中治療"""
    return caption.strip()


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
