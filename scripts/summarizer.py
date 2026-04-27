#!/usr/bin/env python3
"""
Claude API を使って論文のAbstractから構造化された要約を生成する。
生成された要約は infographic.py で使えるJSON形式で出力。
"""

import json
import os
from pathlib import Path

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    print("[Warning] anthropic package not installed. Using mock mode.")


SYSTEM_PROMPT = """\
あなたは小児集中治療の専門医です。
PubMedから取得した論文情報を、Instagram投稿用のインフォグラフィックに使える構造化データに変換してください。

対象読者: 医療者全般（医師、看護師、臨床工学技士など）
言語: 日本語（専門用語は適宜英語を併記）

【重要】各フィールドの文字数は厳守してください。インフォグラフィックの枠に収める必要があります。

以下のJSON形式で出力してください（説明テキストは不要、JSONのみ）:
{
  "title_jp": "日本語タイトル（25文字以内、簡潔でインパクトがあるもの）",
  "key_finding": "最重要な結果を1文で（60文字以内、数値を含めて具体的に）",
  "background": "背景・臨床的疑問を2文以内（100文字以内）",
  "population": "対象患者（年齢・疾患・n数・施設数を箇条書き、各項目20文字以内）",
  "intervention": "介入内容（薬剤量・方法を含む、30文字以内）",
  "comparison": "比較対照（20文字以内）",
  "outcome": "主要アウトカムのみ（30文字以内）",
  "design": "研究デザイン（英語で10語以内）",
  "primary_result": "主要結果（統計値含む、80文字以内）",
  "stats": ["統計値を3つ以内でリスト（HR/OR/NNT/p値、各15文字以内）"],
  "secondary_results": "副次結果を1-2文（80文字以内）",
  "take_home": "臨床へのメッセージを2文以内（100文字以内、具体的なアクションを含む）",
  "limitations": "主要Limitationsを2-3項目（- で開始、各項目30文字以内）",
  "hashtags": ["関連ハッシュタグ5-7個（#不要、日本語英語混在可）"],
  "stat_a": "介入群の主要アウトカム数値（例: 18.2%）。RCT以外や数値がない場合は空文字",
  "stat_a_label": "介入群の短い説明（例: バソプレシン群、10文字以内）",
  "stat_b": "対照群の主要アウトカム数値（例: 26.7%）。RCT以外や数値がない場合は空文字",
  "stat_b_label": "対照群の短い説明（例: プラセボ群、10文字以内）",
  "stat_context": "stat_a/bが何を表すか（例: 28日死亡率、15文字以内）"
}

注意:
- 数値・統計値は原文から正確に引用すること
- 観察研究やレビューなど、PICOに当てはまらない場合は該当フィールドを空文字にする
- Limitationsは著者が述べているものを優先
- take_homeは「臨床現場でどう使うか」を一言で伝えること
- 文字数超過は厳禁。超えそうな場合は省略・言い換えること
"""


def summarize_with_claude(article, api_key=None):
    """Claude APIを使って論文を構造化要約"""
    if not HAS_ANTHROPIC:
        return mock_summarize(article)

    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[Summarizer] No API key found. Using mock mode.")
        return mock_summarize(article)

    client = anthropic.Anthropic(api_key=api_key)

    user_prompt = f"""以下の論文を構造化要約してください。

PMID: {article['pmid']}
Title: {article['title_en']}
Journal: {article['journal']}
Year: {article['year']}
Study Type: {article['study_type']}
Authors: {', '.join(article['authors'][:5])}{'...' if len(article['authors']) > 5 else ''}
DOI: {article.get('doi', 'N/A')}

Abstract:
{article['abstract']}
"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    response_text = message.content[0].text

    # JSONを抽出（コードブロックで囲まれている場合も対応）
    json_text = response_text
    if "```json" in json_text:
        json_text = json_text.split("```json")[1].split("```")[0]
    elif "```" in json_text:
        json_text = json_text.split("```")[1].split("```")[0]

    summary = json.loads(json_text.strip())

    # 元データからのフィールドを追加
    summary["pmid"] = article["pmid"]
    summary["title_en"] = article["title_en"]
    summary["journal"] = article["journal"]
    summary["year"] = article["year"]
    summary["study_type"] = article["study_type"]
    summary["doi"] = article.get("doi", "")
    summary["authors"] = article["authors"]

    # citation生成
    authors_str = article["authors"][0] if article["authors"] else "Unknown"
    if len(article["authors"]) > 1:
        authors_str += ", et al"
    summary["citation"] = (
        f"{authors_str}. {article['title_en']} "
        f"{article['journal']}. {article['year']}. "
        f"doi:{article.get('doi', 'N/A')}"
    )

    return summary


def mock_summarize(article):
    """API未設定時のモック要約（テスト用）"""
    return {
        "pmid": article["pmid"],
        "study_type": article["study_type"],
        "journal": article["journal"],
        "year": article["year"],
        "title_jp": f"[要約未生成] {article['title_en'][:50]}...",
        "title_en": article["title_en"],
        "key_finding": "Claude APIキーを設定すると自動要約が生成されます",
        "background": article["abstract"][:200] if article.get("abstract") else "Abstract not available",
        "population": "",
        "intervention": "",
        "comparison": "",
        "outcome": "",
        "design": article["study_type"],
        "primary_result": "Claude APIキーを設定してください",
        "stats": [],
        "secondary_results": "",
        "take_home": "ANTHROPIC_API_KEY 環境変数を設定して再実行してください",
        "limitations": "",
        "citation": f"{article['authors'][0] if article['authors'] else 'Unknown'}, et al. {article['journal']}. {article['year']}.",
        "hashtags": ["PICU", "小児集中治療", "エビデンス"],
        "doi": article.get("doi", ""),
        "authors": article["authors"],
    }


def summarize_batch(articles, api_key=None, output_dir="data"):
    """複数論文を一括要約"""
    summaries = []
    for i, article in enumerate(articles):
        print(f"[Summarizer] Processing {i+1}/{len(articles)}: PMID {article['pmid']}")
        try:
            summary = summarize_with_claude(article, api_key)
            summaries.append(summary)
        except Exception as e:
            print(f"[Summarizer] Error processing PMID {article['pmid']}: {e}")

    # 保存
    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        from datetime import datetime
        date_str = datetime.now().strftime("%Y%m%d")
        filepath = out / f"summaries_{date_str}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(summaries, f, ensure_ascii=False, indent=2)
        print(f"[Summarizer] Saved {len(summaries)} summaries to {filepath}")

    return summaries


if __name__ == "__main__":
    # テスト用のモックデータ
    test_article = {
        "pmid": "12345678",
        "title_en": "Test Article Title",
        "abstract": "This is a test abstract.",
        "journal": "Test Journal",
        "year": "2025",
        "study_type": "RCT",
        "authors": ["Smith J", "Doe A"],
        "doi": "10.1234/test",
    }
    result = summarize_with_claude(test_article)
    print(json.dumps(result, ensure_ascii=False, indent=2))
