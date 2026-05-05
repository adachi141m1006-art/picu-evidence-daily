#!/usr/bin/env python3
"""
Claude API を使って論文のAbstractから構造化された要約を生成する。
生成された要約は infographic.py で使えるJSON形式で出力。
"""

import json
import os
import re
from pathlib import Path

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    print("[Warning] anthropic package not installed. Using mock mode.")


SYSTEM_PROMPT = """\
あなたは小児集中治療の専門医です。
PubMedから取得した論文情報を、Instagram投稿用インフォグラフィック（7スライドカルーセル）のデータに変換してください。

対象読者: 医療者（医師・看護師・臨床工学技士）
言語: 日本語（専門用語は適宜英語を含めてよい）

【マーカー記法】
  **テキスト**   → 赤強調（太字・やや大きめ。重要な臨床語句・統計値・結論語句）
  ***テキスト*** → 赤強調（さらに大きめ。主要アウトカム数値など最重要値）
  *テキスト*     → 赤強調（やや小さめ。補足的強調）
  ||テキスト||   → 黄色大数字表示（key_findingフィールド専用。HR/OR/NNT/死亡率など主要数値・群名）
  \\n            → 行区切り（同段落内の改行）
  \\n\\n         → 段落区切り（視覚的に行間が広くなる）

  注意: 赤強調（**・***・*）は各フィールドで最大3箇所。多すぎると視認性が落ちる。
       改行位置は「意味の区切り」に入れる。助詞・接続詞が行末・行頭に残らないよう工夫する。

以下のJSON形式で出力してください（説明文不要、JSONのみ）:
{
  "title_jp": "論文タイトルの日本語訳（25文字以内、簡潔でインパクトがあるもの）",

  "hook": "スライド1の問いかけ文。「〜はどうなるか？」「〜は改善するか？」など疑問形。12〜18文字。マーカー不要",

  "key_finding": "||...|| で主要数値・単位・群名・アウトカム名を強調。\\n で明示改行し4〜8行に分割。例（\\nは実際の改行として出力すること）:\\nICU入室後\\n||24時間以内||の\\n||経腸栄養開始||は\\n||60日死亡率||を\\n||有意に低下||させた\\n（||HR 0.71||）",

  "impact_comment": "ネコキャラが語る結果のインパクト。**...** で重要語を赤強調（最大3箇所）。\\n\\n で2段落に分割。末尾は「〜にゃー。」で終わる。各行15文字以内。【重要】「にゃー」はこのフィールドと cat_comment にのみ使用すること",

  "background": "研究背景を2段落（\\n\\n 区切り）。各段落2〜3行（\\n 区切り）。重要語に **...** を最大3箇所。合計5〜6行。【重要】「にゃー」は使わない",

  "population": "対象患者を段落構成で出力。第1段落: 年齢・診断・例数など主要条件を \\n で区切り。第2段落: 「除外：\\n〜」形式で除外基準。**...**・***n例*** で重要部分を強調",

  "pico_p": "P（患者）を1〜2行に凝縮。**...**・***n例*** で強調。例: **18歳未満**のICU入室患者（n=***1,247例***）",

  "intervention": "I（介入）を1行（30文字以内厳守。超える場合は省略・言い換え）。**...** で介入の核心を強調",

  "comparison": "C（比較）を1行（20文字以内）",

  "outcome": "O（主要アウトカム）を1行（30文字以内）。**...** で強調",

  "design": "研究デザイン・期間・施設数を2行以内。例: 多施設前向きコホート研究\\n2020〜2023年、15施設参加",

  "primary_result": "主要結果を3〜5行（\\n 区切り）。統計値（HR/OR/p値/CI）を **...** で強調",

  "secondary_results": "副次結果を1〜2段落（\\n\\n 区切り）。各段落2〜3行（\\n 区切り）。統計値を **...** で強調",

  "limitations": "Limitationsを3項目。各項目は【必ず】「主見出し行\\n補足1行」の計2行のみ。3行以上にしない（3行目以降は表示されない）。項目間は \\n\\n で区切る。主見出しの核心語（1〜2語）のみを **...** で強調。例:\\n観察研究のため**交絡因子**が残る\\n因果関係の断定は慎重に\\n\\n施設間で**プロトコール差**あり\\n開始基準・実施方法にばらつき\\n\\n**栄養・カロリー達成率**は不明\\n「開始した」以外の質は読み取りにくい",

  "cat_comment": "批判的吟味のネコ吹き出し。\\n で区切った行を【5行以内厳守】（6行以上にすると表示が崩れる）。主要結果の注意点・読み方に絞る。**...** で重要語を強調（最大3箇所）。末尾は「〜にゃー。」で終わる。1段落（\\n\\n 不使用）。1行15文字以内",

  "take_home": "臨床メッセージを2段落（\\n\\n 区切り）。第1段落: この研究が示した臨床的事実（2〜3行）。第2段落: 実際のアクション推奨（禁忌・条件付き）（1〜2行）。重要語を **...** で強調（最大3箇所）",

  "take_home_note": "take_homeに続く短い補足注意事項（任意）。1行・30文字以内。不要なら空文字",

  "hashtags": ["関連ハッシュタグ5〜7個（#不要、日本語英語混在可）"]
}

共通ルール:
- 数値・統計値は原文から正確に引用する
- 観察研究・レビューなどPICOに当てはまらない場合は intervention/comparison を空文字にする
- Limitationsは著者が明示しているものを優先（3項目必須）
- take_home の第2段落は「禁忌や〜がなければ」「〜が安定していれば」など条件付き推奨を心がける
- cat_comment は limitations と重複しすぎないよう、「読み方・解釈の注意」に絞る
"""


def _sanitize_summary(s: dict) -> dict:
    """Claude出力のレイアウト制約違反をコード側で保証する。"""
    # cat_comment: 5行以内（6行目以降はバブルからはみ出す）
    if s.get("cat_comment"):
        lines = [l for l in s["cat_comment"].split("\n") if l.strip()]
        if len(lines) > 5:
            s["cat_comment"] = "\n".join(lines[:5])

    # limitations: 各項目2行のみ（3行目以降は _lim_item で無音ドロップされるため先に切る）
    if s.get("limitations"):
        items = [item.strip() for item in s["limitations"].split("\n\n") if item.strip()]
        sanitized = []
        for item in items[:3]:
            item_lines = [l for l in item.split("\n") if l.strip()]
            sanitized.append("\n".join(item_lines[:2]))
        s["limitations"] = "\n\n".join(sanitized)

    return s


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

    # JSON抽出: コードブロック → 最初の{...}ブロック の順で試みる
    json_text = response_text
    if "```json" in json_text:
        json_text = json_text.split("```json")[1].split("```")[0]
    elif "```" in json_text:
        json_text = json_text.split("```")[1].split("```")[0]
    else:
        # コードブロックなし: 最初の { から最後の } を抽出
        m = re.search(r'\{.*\}', json_text, re.DOTALL)
        if m:
            json_text = m.group(0)

    summary = json.loads(json_text.strip())
    summary = _sanitize_summary(summary)

    # 元データからのフィールドを追加
    summary["pmid"] = article["pmid"]
    summary["title_en"] = article["title_en"]
    summary["journal"] = article["journal"]
    summary["year"] = article["year"]
    summary["study_type"] = article["study_type"]
    summary["doi"] = article.get("doi", "")
    summary["authors"] = article["authors"]

    # citation生成: タイトルは60文字に切り詰め（Slide 7 下部がフッターに被るのを防ぐ）
    authors_str = article["authors"][0] if article["authors"] else "Unknown"
    if len(article["authors"]) > 1:
        authors_str += ", et al"
    title_abbr = article["title_en"]
    if len(title_abbr) > 60:
        title_abbr = title_abbr[:57] + "..."
    summary["citation"] = (
        f"{authors_str}. {title_abbr} "
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
        "title_jp": f"[要約未生成] {article['title_en'][:25]}",
        "title_en": article["title_en"],
        "hook": "APIキーを設定すると自動生成されます",
        "key_finding": "||Claude APIキー||を\n||設定||すると\n||自動要約||が生成されます",
        "impact_comment": "**APIキー**を設定して\n再実行してください\nにゃー。",
        "background": article["abstract"][:200] if article.get("abstract") else "Abstract not available",
        "population": "",
        "pico_p": "",
        "intervention": "",
        "comparison": "",
        "outcome": "",
        "design": article["study_type"],
        "primary_result": "Claude APIキーを設定してください",
        "secondary_results": "",
        "take_home": "ANTHROPIC_API_KEY 環境変数を設定して\n再実行してください。\n\n詳細は README を参照してください。",
        "take_home_note": "",
        "limitations": "APIキーが未設定\n要約は生成されていません\n\nANTHROPIC_API_KEY を設定\n再実行してください\n\n詳細は README を参照\n設定方法を確認してください",
        "cat_comment": "**APIキー**が未設定なので\n**要約**が生成されていないにゃー。\n設定して再実行にゃー。",
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
