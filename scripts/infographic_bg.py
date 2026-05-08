#!/usr/bin/env python3
"""
PICU Evidence Daily — Background-image carousel generator
Uses Canva PNG backgrounds + HTML/CSS text overlay via Playwright
"""
import base64
import json
import os
import re
import tempfile
from pathlib import Path

BG_DIR = Path(__file__).parent.parent / "assets" / "backgrounds"

# フォント定義
F_HOOK = "'M PLUS Rounded 1c', sans-serif"                        # hook: 丸みあり・読める太さ
F_HEAD = "'Hiragino Kaku Gothic Pro', 'Noto Sans JP', sans-serif"  # 見出し: 落ち着いた角ゴ
F_BODY = "'Noto Sans JP', 'Hiragino Kaku Gothic Pro', sans-serif"  # 本文
W_BLACK = "900"
W_BOLD  = "700"
W_MED   = "500"


def _b64_bg(slide_num: int) -> str:
    path = BG_DIR / f"{slide_num}背景.png"
    if not path.exists():
        return ""
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


# ============================================================
# 日本語改行制御
# ============================================================
_NOWRAP_TERMS = sorted([
    # 文末語尾
    "にゃー",
    # 研究デザイン
    "多施設共同前向きコホート研究", "多施設前向きコホート研究", "多施設後ろ向きコホート研究",
    "単施設前向きコホート研究", "多施設前向きコホート", "前向きコホート研究",
    "後ろ向きコホート研究", "ランダム化比較試験", "無作為化比較試験",
    "システマティックレビュー", "システマティック・レビュー", "メタアナリシス", "メタ解析",
    "コホート研究", "観察研究", "横断研究", "症例対照研究",
    # ICU/PICU
    "ICU入室患者", "PICU入室患者",
    "ICU入室後", "PICU入室後", "PICU死亡率", "ICU死亡率",
    "PICU死亡", "ICU死亡", "ICU入室", "PICU入室",
    "PICU滞在日数", "ICU滞在日数",
    # 呼吸管理
    "人工呼吸器離脱率", "人工呼吸器",
    # 統計結果
    "有意差なし", "有意に低下", "有意に上昇", "有意に増加",
    # 栄養
    "早期経腸栄養", "経腸栄養開始", "経腸栄養中止", "経腸栄養継続",
    "経腸栄養禁忌", "経腸栄養量", "経腸栄養", "早期静脈栄養", "静脈栄養",
    # 抗菌薬・抗真菌薬・抗ウイルス薬（長い語を先に）
    "ピペラシリン/タゾバクタム", "ピペラシリン・タゾバクタム",
    "アンピシリン/スルバクタム", "アンピシリン・スルバクタム",
    "ピペラシリン", "タゾバクタム", "スルバクタム", "アンピシリン",
    "セフェピム", "セフォタキシム", "セフトリアキソン", "セフタジジム",
    "セファゾリン", "セファレキシン", "セフォキシチン",
    "メロペネム", "イミペネム", "ドリペネム", "エルタペネム",
    "バンコマイシン", "テイコプラニン", "リネゾリド", "ダプトマイシン",
    "クリンダマイシン", "アジスロマイシン", "クラリスロマイシン",
    "ゲンタマイシン", "アミカシン", "トブラマイシン",
    "シプロフロキサシン", "レボフロキサシン", "モキシフロキサシン",
    "フルコナゾール", "ミカファンギン", "アムホテリシン",
    "アシクロビル", "ガンシクロビル", "バラシクロビル",
    "リバビリン", "オセルタミビル", "パリビズマブ",
    # 医学用語・略語
    "施設プロトコール", "プロトコール", "ガイドライン", "エビデンス",
    "発熱性好中球減少症", "発熱性好中球減少", "好中球減少症", "好中球減少",
    "フェブリルニュートロペニア", "ニュートロペニア",
    "造血幹細胞移植", "同種移植", "自家移植", "免疫不全",
    "インフォームドコンセント",
], key=len, reverse=True)

_NOWRAP_PATTERNS = [
    # 統計値: HR 0.71, OR=1.35, NNT=12 など
    r'(?:HR|RR|OR|NNT|NNH|ARR|RD)\s*[=:]\s*[\d.,]+(?:\s*[\(（][^)）]{0,30}[\)）])?',
    # 95%CI
    r'95\s*%\s*CI\s*[\d.,]+\s*[–\-]\s*[\d.,]+',
    # p値
    r'p\s*[=<>≤≥]\s*0?\.?\d+',
    # N日死亡率/生存率（一般時間パターンより先に評価）
    r'\d+日(?:死亡|生存)率',
    # 数値比較: 7日→5日短縮、3時間→1時間 など
    r'\d+(?:[.,]\d+)?(?:時間|日|週|ヶ月|ヵ月|か月)→\d+(?:[.,]\d+)?(?:時間|日|週|ヶ月|ヵ月|か月)(?:短縮|増加|延長)?',
    # 数字＋日本語単位（時間/日/週 + 以内/以降/以上/未満/後）
    r'\d+(?:[.,]\d+)?(?:時間|日|週|ヶ月|ヵ月|か月)(?:以内|以降|以上|未満|後|前)?(?:開始)?',
    # 症例数
    r'\d+(?:[,，]\d+)*例',
    # パーセント
    r'\d+(?:\.\d+)?%',
    # 医薬品・医学英字略語（2〜6文字の大文字）
    r'\b(?:PTAZ|PIPC|CFPM|VCM|MEPM|DRPM|IPM|MDRP|MRSA|ESBL|PRSP|CRKP|CRAB'
    r'|FN|TDM|PK|PD|CRP|PCT|WBC|ANC|ALC|Hb|Plt|Cr|BUN|ALT|AST|LDH'
    r'|ECMO|CRRT|CHDF|ARDS|DIC|SIRS|MAP|CVP|PCWP'
    r'|RCT|SR|MA|CI|OR|HR|RR|NNT|NNH|ARR|RRR'
    r'|PICU|NICU|ICU|ER|DNAR|DNR)\b',
]

_NOWRAP_RE = re.compile(
    '|'.join(f'(?:{re.escape(t)})' for t in _NOWRAP_TERMS) +
    '|' +
    '|'.join(f'(?:{p})' for p in _NOWRAP_PATTERNS)
)


def _nowrap_jp(text: str) -> str:
    if not text:
        return text
    return _NOWRAP_RE.sub(lambda m: f'<span class="nowrap">{m.group(0)}</span>', text)


_BREAK_BIGRAMS = frozenset({
    'して', 'いて', 'られ', 'せた', 'れた', 'った', 'から', 'まで',
    'より', 'など', 'おり', 'あり', 'ため', 'にて', 'いう', 'なる', 'なく',
    'おける', 'おいて', 'ついて', 'として', 'により', 'によっ', 'に対し',
})


def _fmt(text: str, max_chars: int) -> str:
    """日本語テキストに自然な <br> を挿入し nowrap語句を span で保護する"""
    if not text:
        return text
    if len(text) <= max_chars:
        return _NOWRAP_RE.sub(lambda m: f'<span class="nowrap">{m.group(0)}</span>', text)

    protected = [(m.start(), m.end()) for m in _NOWRAP_RE.finditer(text)]

    def in_prot(pos: int) -> bool:
        return any(s < pos < e for s, e in protected)

    def brk(pos: int) -> int:
        if in_prot(pos) or pos <= 0 or pos > len(text):
            return 0
        ch = text[pos - 1]
        if ch in '。、！？…：':
            return 10
        for n in (3, 2):
            if pos >= n and text[pos - n:pos] in _BREAK_BIGRAMS:
                return 7
        if ch in 'はがをでやもか':
            return 5
        if ch == ' ':
            return 3
        return 0

    lines, start = [], 0
    while start < len(text):
        if len(text) - start <= max_chars:
            lines.append(text[start:])
            break
        best, best_s = -1, 0
        for i in range(start + 1, min(start + max_chars + 1, len(text) + 1)):
            s = brk(i)
            if s > best_s:
                best, best_s = i, s
        if best > start:
            lines.append(text[start:best])
            start = best
        else:
            force = start + max_chars
            while force > start + 1 and in_prot(force):
                force -= 1
            lines.append(text[start:force])
            start = force

    return "<br>".join(
        _NOWRAP_RE.sub(lambda m: f'<span class="nowrap">{m.group(0)}</span>', ln)
        for ln in lines
    )


def _emph_spans(text: str, base_px: int, emph_px: int) -> str:
    """||強調テキスト|| → 大きなspanに変換（ベースライン揃え・上方向に大きく）"""
    def replace(m):
        return (f'<span style="font-size:{emph_px}px;font-weight:900;color:#000000;'
                f'vertical-align:baseline;position:relative;top:-0.08em;">'
                f'{m.group(1)}</span>')
    return re.sub(r'\|\|(.+?)\|\|', replace, text)


def _red_emph(text: str, emph_px: int = 0) -> str:
    """赤強調: .emphasis-red クラスに統一。
    サイズは _html_page(emph_red_px=N) のCSS定義で決まる。
    ***...*** / **...** / *...* → すべて .emphasis-red（赤同士はスライド内で同サイズ）
    emph_px: 後方互換のため残存、使用しない
    """
    text = re.sub(r'\*{3}(.+?)\*{3}',
                  lambda m: f'<span class="emphasis-red">{m.group(1)}</span>', text)
    text = re.sub(r'\*{2}(.+?)\*{2}',
                  lambda m: f'<span class="emphasis-red">{m.group(1)}</span>', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)',
                  lambda m: f'<span class="emphasis-red">{m.group(1)}</span>', text)
    return text


def _strip_markup(text: str) -> str:
    """||...||, ***...***,  **...**, *...* マーカーを除去してプレーンテキストに戻す"""
    text = re.sub(r'\*{3}(.+?)\*{3}', r'\1', text)
    text = re.sub(r'\*{2}(.+?)\*{2}', r'\1', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', text)
    text = re.sub(r'\|\|(.+?)\|\|', r'\1', text)
    return text


def _fit(text: str, base: int, min_size: int, chars_per_line: int) -> int:
    estimated_lines = max(1, len(text) / chars_per_line)
    if estimated_lines <= 2:
        return base
    if estimated_lines <= 3:
        return max(min_size, int(base * 0.85))
    return max(min_size, int(base * 0.72))


def _html_page(slide_div: str,
               emph_red_px: int = 58,
               emph_yellow_px: int = 58) -> str:
    """スライドHTML生成。
    emph_red_px    : そのスライド全体の赤強調サイズ（黒本文より大きく、赤同士は統一）
    emph_yellow_px : Slide7黄強調サイズ
    """
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=M+PLUS+Rounded+1c:wght@800&family=Noto+Sans+JP:wght@500;700;900&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1080px; height:1350px; overflow:hidden; background:#000; }}
.text-block {{ word-break:normal; overflow-wrap:normal; line-break:strict; white-space:normal; }}
.nowrap {{ white-space:nowrap; }}

/* 赤強調: スライド全体で同一サイズ。黒より大きく、赤同士は統一 */
.emphasis-red {{
  color: #E15258;
  font-size: {emph_red_px}px;
  font-weight: 900;
  line-height: 1;
  vertical-align: baseline;
  position: relative;
  top: -0.02em;
}}
/* 黄強調 (Slide7 紺背景用) */
.emphasis-yellow {{
  color: #FFD54F;
  font-size: {emph_yellow_px}px;
  font-weight: 900;
  line-height: 1;
  vertical-align: baseline;
  position: relative;
  top: -0.02em;
}}
</style>
</head>
<body>
{slide_div}
</body>
</html>"""


def s1_hook(summary: dict, font_scale: float = 1.0) -> str:
    sz = lambda n, mn=14: max(mn, round(n * font_scale))

    hook        = summary.get("hook", "")
    title_raw   = summary.get("title_jp", "")
    kf_raw      = summary.get("key_finding", "")
    citation    = summary.get("citation", "")
    study_type  = summary.get("study_type", "")
    year        = summary.get("year", "")
    journal     = summary.get("journal", "")

    kf_plain    = _strip_markup(kf_raw)
    title_plain = _strip_markup(title_raw)

    hook_fmt    = _fmt(hook, 16)
    title       = _fmt(title_plain, 22)
    key_finding = _fmt(kf_plain, 26)
    citation    = _nowrap_jp(citation)

    hook_size    = _fit(hook,        base=sz(66), min_size=sz(58), chars_per_line=12) if hook else 0
    title_size   = _fit(title_plain, base=sz(46), min_size=sz(38), chars_per_line=18)
    finding_size = _fit(kf_plain,    base=sz(40), min_size=sz(33), chars_per_line=20)

    bg = _b64_bg(1)
    bg_style = f"background-image:url('{bg}');background-size:cover;background-position:center top;" if bg else "background:#0a1a5c;"

    tag_items = [t for t in [study_type, f"{journal} {year}".strip()] if t]
    tag_html = ""
    if tag_items:
        spans = "".join(
            f'<span style="border:1px solid rgba(255,255,255,0.40);border-radius:20px;'
            f'padding:3px 14px;font-size:{sz(21)}px;font-weight:700;color:#ffffff;'
            f'font-family:{F_HEAD};white-space:nowrap;">{t}</span>'
            for t in tag_items
        )
        tag_html = f'<div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:12px;">{spans}</div>'

    finding_block = f"""
    <div style="display:flex;align-items:stretch;gap:18px;padding-right:148px;">
      <div style="width:5px;background:#e53935;border-radius:3px;flex-shrink:0;"></div>
      <div class="text-block" style="font-family:{F_HEAD};font-size:{finding_size}px;font-weight:800;
                  color:#ffffff;line-height:1.4;">{key_finding}</div>
    </div>"""

    # hook: max-height を 290px（タイトルブロック top=595 まで余裕を持たせる）
    # overflow:hidden で QA の container_clipping 検出が機能する
    hook_html = f"""
  <div style="position:absolute;top:248px;left:64px;">
    <span style="background:#e53935;color:#ffffff;font-family:{F_BODY};font-size:{sz(22)}px;
                 font-weight:{W_BLACK};padding:4px 16px;border-radius:4px;
                 letter-spacing:0.08em;">注目論文</span>
  </div>
  <div class="text-block" style="position:absolute;top:292px;left:64px;right:240px;
              font-family:{F_HOOK};font-size:{hook_size}px;font-weight:800;
              color:#ffffff;line-height:1.18;max-height:290px;overflow:hidden;">
    {hook_fmt}
  </div>""" if hook else ""

    div = f"""<div style="width:1080px;height:1350px;position:relative;overflow:hidden;{bg_style}">
{hook_html}

  <!-- Title + Tag + Key Finding -->
  <div style="position:absolute;top:595px;left:64px;right:72px;
              display:flex;flex-direction:column;gap:36px;
              max-height:570px;overflow:hidden;">

    <div>
      <div class="text-block" style="font-family:{F_HEAD};font-size:{title_size}px;font-weight:800;
                  color:#ffffff;line-height:1.32;">{title}</div>
      {tag_html}
    </div>

    {finding_block}

  </div>

  <!-- Citation -->
  <div style="position:absolute;top:1178px;left:64px;right:230px;
              font-family:{F_BODY};font-size:{sz(21)}px;font-weight:{W_MED};
              color:rgba(255,255,255,0.58);line-height:1.5;">{citation}</div>

</div>"""
    return _html_page(div, emph_red_px=sz(58))


def s2_keyfinding(summary: dict, font_scale: float = 1.0) -> str:
    """Slide 2: 上半分にKey Finding大表示 + 吹き出し内にネココメント"""
    sz = lambda n, mn=14: max(mn, round(n * font_scale))
    key_finding_raw = summary.get("key_finding", "")
    impact_raw      = summary.get("impact_comment", "")

    kf_base = sz(44)
    kf_emph = sz(62)
    ic_base = sz(38)
    ic_emph = sz(46)

    # key_finding: \n で明示改行、||...|| で強調
    kf_lines = [ln.strip() for ln in key_finding_raw.split('\n') if ln.strip()]
    if not kf_lines:
        kf_lines = [key_finding_raw]
    kf_html = '<br>'.join(_emph_spans(ln, kf_base, kf_emph) for ln in kf_lines)

    # impact_comment: \n\n で段落分割、\n で改行、**...** で赤強調
    ic_paras = [p.strip() for p in impact_raw.split('\n\n') if p.strip()]
    if not ic_paras:
        ic_paras = [impact_raw.strip()]

    ic_divs = []
    for i, para in enumerate(ic_paras):
        lines_html = '<br>'.join(
            _red_emph(_nowrap_jp(ln.strip()), ic_emph) for ln in para.split('\n') if ln.strip()
        )
        mb = 'margin-bottom:22px;' if i < len(ic_paras) - 1 else ''
        ic_divs.append(f'<div style="{mb}">{lines_html}</div>')
    ic_html = ''.join(ic_divs)

    bg = _b64_bg(2)
    bg_style = f"background-image:url('{bg}');background-size:cover;background-position:center top;" if bg else "background:#ffffff;"

    div = f"""<div style="width:1080px;height:1350px;position:relative;overflow:hidden;{bg_style}">

  <!-- Key Finding: 上半分・縦横中央 -->
  <div style="position:absolute;top:60px;left:64px;right:64px;height:570px;
              display:flex;flex-direction:column;align-items:center;justify-content:center;">
    <div class="text-block" style="font-family:{F_HEAD};font-size:{kf_base}px;font-weight:800;
                color:#000000;line-height:1.18;text-align:center;">
      {kf_html}
    </div>
  </div>

  <!-- Impact Comment: 吹き出し内 (x=285~985px, y=735~1050px) -->
  <div style="position:absolute;left:285px;right:95px;top:750px;height:300px;
              display:flex;flex-direction:column;align-items:center;justify-content:center;">
    <div class="text-block" style="font-family:{F_HOOK};font-size:{ic_base}px;font-weight:500;
                color:#000000;line-height:1.45;text-align:center;">
      {ic_html}
    </div>
  </div>

</div>"""
    return _html_page(div, emph_red_px=sz(50))


def _build_section(text: str, emph_px: int, para_gap: int = 20,
                   emph_fn=None) -> str:
    """\n\n で段落分割、\n で改行、**...** で強調。空なら空文字を返す。"""
    if not text:
        return ""
    if emph_fn is None:
        emph_fn = _red_emph
    paras = [p.strip() for p in text.split('\n\n') if p.strip()]
    if not paras:
        paras = [text.strip()]
    divs = []
    for i, para in enumerate(paras):
        lines = '<br>'.join(
            emph_fn(_nowrap_jp(ln.strip()), emph_px)
            for ln in para.split('\n') if ln.strip()
        )
        mb = f'margin-bottom:{para_gap}px;' if i < len(paras) - 1 else ''
        divs.append(f'<div style="{mb}">{lines}</div>')
    return ''.join(divs)


def _yellow_emph(text: str, emph_px: int = 0) -> str:
    """黄強調 (Slide7 紺背景用): CSSクラスでsize inherit。色+太字のみ。
    emph_px: 後方互換のため残存、使用しない
    """
    text = re.sub(r'\*{3}(.+?)\*{3}',
                  lambda m: f'<span class="emphasis-yellow">{m.group(1)}</span>', text)
    text = re.sub(r'\*{2}(.+?)\*{2}',
                  lambda m: f'<span class="emphasis-yellow">{m.group(1)}</span>', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)',
                  lambda m: f'<span class="emphasis-yellow">{m.group(1)}</span>', text)
    return text


def s3_background(summary: dict, font_scale: float = 1.0) -> str:
    """Slide 3: 背景・対象（見出しは背景画像に既出、本文テキストをオーバーレイ）"""
    sz = lambda n, mn=14: max(mn, round(n * font_scale))
    bg_raw  = summary.get("background", "")
    pop_raw = summary.get("population", "")

    bg_base  = sz(38)
    bg_emph  = sz(48)
    pop_base = sz(38)
    pop_emph = sz(48)

    bg_html  = _build_section(bg_raw,  bg_emph,  para_gap=24)
    pop_html = _build_section(pop_raw, pop_emph, para_gap=16)

    bg = _b64_bg(3)
    bg_style = f"background-image:url('{bg}');background-size:cover;background-position:center top;" if bg else "background:#FAFAF8;"

    div = f"""<div style="width:1080px;height:1350px;position:relative;overflow:hidden;{bg_style}">

  <!-- 背景テキスト (y=160~: 見出し「背景」下40px余白) -->
  <div class="text-block" style="position:absolute;top:160px;left:64px;right:72px;
              font-family:{F_BODY};font-size:{bg_base}px;font-weight:700;
              color:#111111;line-height:1.5;">
    {bg_html}
  </div>

  <!-- 対象テキスト (y=760~: 見出し「対象」下40px余白、右幅を820pxに制限) -->
  <div class="text-block" style="position:absolute;top:760px;left:84px;right:236px;
              font-family:{F_BODY};font-size:{pop_base}px;font-weight:700;
              color:#111111;line-height:1.52;">
    {pop_html}
  </div>

</div>"""
    return _html_page(div, emph_red_px=sz(50))


def s4_pico(summary: dict, font_scale: float = 1.0) -> str:
    """Slide 4: PICO + 方法（見出しは背景画像に既出）"""
    sz = lambda n, mn=14: max(mn, round(n * font_scale))
    pico_p = summary.get("pico_p", "")
    pico_i = summary.get("intervention", "")
    pico_c = summary.get("comparison", "")
    pico_o = summary.get("outcome", "")
    design = summary.get("design", "")

    body_base = sz(40)
    body_emph = sz(54)
    des_base  = sz(42)
    des_emph  = sz(52)

    # PICO各行: 絶対配置（見出し下135px〜、120px間隔）
    # overflow:hidden 禁止。2行以内に収まる文字量はsummarizerで制御
    ROW_TOPS = [135, 255, 375, 495]

    def _pico_row(label, text, top_px):
        if not text:
            return ""
        paras = [p.strip() for p in text.split('\n\n') if p.strip()] or [text.strip()]
        parts = []
        for i, para in enumerate(paras):
            lines = '<br>'.join(
                _red_emph(_nowrap_jp(ln.strip()), body_emph)
                for ln in para.split('\n') if ln.strip()
            )
            mb = 'margin-bottom:10px;' if i < len(paras) - 1 else ''
            parts.append(f'<div style="{mb}">{lines}</div>')
        text_html = ''.join(parts)
        return (
            f'<div style="position:absolute;top:{top_px}px;left:64px;right:80px;'
            f'display:flex;align-items:flex-start;gap:22px;">'
            f'<div style="flex-shrink:0;display:flex;align-items:center;justify-content:center;'
            f'background:#1C2C73;color:#ffffff;font-family:{F_HEAD};'
            f'font-size:26px;font-weight:900;width:48px;height:48px;'
            f'border-radius:8px;margin-top:2px;">{label}</div>'
            f'<div class="text-block" style="font-family:{F_BODY};font-size:{body_base}px;'
            f'font-weight:800;color:#111111;line-height:1.42;">{text_html}</div>'
            f'</div>'
        )

    pico_rows = "".join([
        _pico_row("P", pico_p, ROW_TOPS[0]),
        _pico_row("I", pico_i, ROW_TOPS[1]),
        _pico_row("C", pico_c, ROW_TOPS[2]),
        _pico_row("O", pico_o, ROW_TOPS[3]),
    ])
    design_html = _build_section(design, des_emph, para_gap=18)

    bg = _b64_bg(4)
    bg_style = f"background-image:url('{bg}');background-size:cover;background-position:center top;" if bg else "background:#FAFAF8;"

    div = f"""<div style="width:1080px;height:1350px;position:relative;overflow:hidden;{bg_style}">

  {pico_rows}

  <!-- 方法本文: y=845~ (見出し「方法」y≈730px 下約115px、左波を避けleft=190px) -->
  <div class="text-block" style="position:absolute;top:845px;left:190px;right:80px;
              font-family:{F_BODY};font-size:{des_base}px;font-weight:800;
              color:#111111;line-height:1.45;">
    {design_html}
  </div>

</div>"""
    return _html_page(div, emph_red_px=sz(52))


def s5_results(summary: dict, font_scale: float = 1.0) -> str:
    """Slide 5: 結果 + 二次結果"""
    sz = lambda n, mn=14: max(mn, round(n * font_scale))
    primary   = summary.get("primary_result", "")
    secondary = summary.get("secondary_results", "")

    pri_base = sz(44)
    pri_emph = sz(60)
    sec_base = sz(40)
    sec_emph = sz(52)

    pri_html = _build_section(primary,   pri_emph, para_gap=22)
    sec_html = _build_section(secondary, sec_emph, para_gap=16)

    bg = _b64_bg(5)
    bg_style = f"background-image:url('{bg}');background-size:cover;background-position:center top;" if bg else "background:#FAFAF8;"

    div = f"""<div style="width:1080px;height:1350px;position:relative;overflow:hidden;{bg_style}">

  <!-- 主要結果本文: y=155~ (「結果」見出しy≈40-90px の下) -->
  <div class="text-block" style="position:absolute;top:155px;left:64px;right:80px;
              font-family:{F_BODY};font-size:{pri_base}px;font-weight:800;
              color:#111111;line-height:1.35;">
    {pri_html}
  </div>

  <!-- 二次結果本文: y=755~ (「二次結果」見出しy≈620-720px の下35px) -->
  <!-- line-height:1.55 → 40×1.55=62px > emph_red_px=58px で行間崩れ防止 -->
  <div class="text-block" style="position:absolute;top:755px;left:64px;right:80px;
              font-family:{F_BODY};font-size:{sec_base}px;font-weight:800;
              color:#111111;line-height:1.55;">
    {sec_html}
  </div>

</div>"""
    return _html_page(div, emph_red_px=sz(58))


def s6_critical(summary: dict, font_scale: float = 1.0) -> str:
    """Slide 6: 批判的吟味（上部3項目）+ ネコ吹き出し（下部）"""
    sz = lambda n, mn=14: max(mn, round(n * font_scale))
    limitations = summary.get("limitations", "")
    cat_comment  = summary.get("cat_comment", "")

    lim_base = sz(33)
    lim_sub  = sz(28)

    # 吹き出し内テキスト量に応じて動的にフォントサイズを設定
    # 吹き出し有効高さ: 340px - 20px padding - 35px header = 285px
    # cat_base × 1.55 × 行数 ≤ 285px
    cat_text_len = len(_strip_markup(cat_comment))
    if cat_text_len <= 35:
        cat_base = sz(36)
    elif cat_text_len <= 55:
        cat_base = sz(32)
    else:
        cat_base = sz(28)

    items = [p.strip() for p in limitations.split('\n\n') if p.strip()][:3]

    ITEM_TOPS = [145, 330, 515]

    def _lim_item(num, text, top_px):
        if not text:
            return ""
        lines = [ln.strip() for ln in text.split('\n') if ln.strip()]
        main_html = _red_emph(_nowrap_jp(lines[0])) if lines else ""
        sub_html  = _red_emph(_nowrap_jp(lines[1])) if len(lines) > 1 else ""

        sub_div = (
            f'<div style="font-family:{F_BODY};font-size:{lim_sub}px;font-weight:600;'
            f'color:#444444;margin-top:6px;line-height:1.60;">{sub_html}</div>'
        ) if sub_html else ""

        return (
            f'<div style="position:absolute;top:{top_px}px;left:55px;right:380px;">'
            f'<div style="display:flex;align-items:flex-start;gap:16px;">'
            f'<div style="flex-shrink:0;font-family:{F_HEAD};font-size:{sz(42)}px;'
            f'font-weight:900;color:#1C2C73;line-height:1.40;white-space:nowrap;">{num}.</div>'
            f'<div class="text-block">'
            f'<div style="font-family:{F_BODY};font-size:{lim_base}px;font-weight:800;'
            f'color:#111111;line-height:1.40;">{main_html}</div>'
            f'{sub_div}'
            f'</div>'
            f'</div>'
            f'</div>'
        )

    lim_rows = "".join(
        _lim_item(i + 1, items[i], ITEM_TOPS[i])
        for i in range(len(items))
    )

    cat_paras = [p.strip() for p in cat_comment.split('\n\n') if p.strip()]
    cat_parts = []
    for i, para in enumerate(cat_paras):
        lines_html = '<br>'.join(
            _red_emph(_nowrap_jp(ln.strip()))
            for ln in para.split('\n') if ln.strip()
        )
        mb = 'margin-bottom:10px;' if i < len(cat_paras) - 1 else ''
        cat_parts.append(f'<div style="{mb}">{lines_html}</div>')
    cat_html = ''.join(cat_parts)

    bg = _b64_bg(6)
    bg_style = (
        f"background-image:url('{bg}');background-size:cover;background-position:center top;"
        if bg else "background:#FAFAF8;"
    )

    div = f"""<div style="width:1080px;height:1350px;position:relative;overflow:hidden;{bg_style}">

  {lim_rows}

  <!-- 吹き出し: overflow:hidden で QA の container_clipping 検出が機能する -->
  <div style="position:absolute;top:740px;left:130px;right:470px;height:340px;
              overflow:hidden;
              display:flex;flex-direction:column;justify-content:flex-start;padding-top:20px;">
    <div style="font-family:{F_HEAD};font-size:{sz(23)}px;font-weight:900;
                color:#1C2C73;margin-bottom:10px;letter-spacing:0.04em;">結果の読み方</div>
    <div class="text-block" style="font-family:{F_HOOK};font-size:{cat_base}px;font-weight:700;
                color:#111111;line-height:1.55;">
      {cat_html}
    </div>
  </div>

</div>"""
    return _html_page(div, emph_red_px=sz(42))


def s7_takehome(summary: dict, font_scale: float = 1.0) -> str:
    """Slide 7: Take Home Message（紺背景・白文字・黄色強調）"""
    sz = lambda n, mn=14: max(mn, round(n * font_scale))
    take_home      = summary.get("take_home", "")
    citation       = summary.get("citation", "")
    take_home_note = summary.get("take_home_note", "")

    base = sz(46)
    emph = sz(54)

    content_html = _build_section(
        take_home, emph, para_gap=36, emph_fn=_yellow_emph
    )

    bg = _b64_bg(7)
    bg_style = (
        f"background-image:url('{bg}');background-size:cover;background-position:center top;"
        if bg else "background:#1C2C73;"
    )

    # right=300px: 幅=1080-120-300=660px、右下ネコ x≈780px の手前に収まる
    # take_home_note は _fmt で自然な改行を挿入してから nowrap 保護
    note_size = sz(22)
    cite_size = sz(20)
    bottom_html = ""
    if take_home_note and citation:
        note_fmt = _fmt(take_home_note, 22)
        bottom_html = (
            f'<div class="text-block" style="position:absolute;top:1075px;left:120px;right:300px;'
            f'font-family:{F_BODY};font-size:{note_size}px;font-weight:500;'
            f'color:rgba(255,255,255,0.65);line-height:1.5;">'
            f'{note_fmt}</div>'
            f'<div style="position:absolute;top:1130px;left:120px;right:300px;'
            f'font-family:{F_BODY};font-size:{cite_size}px;font-weight:500;'
            f'color:rgba(255,255,255,0.50);line-height:1.5;">'
            f'{_nowrap_jp(citation)}</div>'
        )
    elif citation:
        bottom_html = (
            f'<div style="position:absolute;top:1090px;left:120px;right:300px;'
            f'font-family:{F_BODY};font-size:{cite_size}px;font-weight:500;'
            f'color:rgba(255,255,255,0.50);line-height:1.5;">'
            f'{_nowrap_jp(citation)}</div>'
        )
    elif take_home_note:
        note_fmt = _fmt(take_home_note, 22)
        bottom_html = (
            f'<div class="text-block" style="position:absolute;top:1110px;left:120px;right:300px;'
            f'font-family:{F_BODY};font-size:{note_size}px;font-weight:500;'
            f'color:rgba(255,255,255,0.65);line-height:1.5;">'
            f'{note_fmt}</div>'
        )

    div = f"""<div style="width:1080px;height:1350px;position:relative;overflow:hidden;{bg_style}">

  <!-- 本文: left=120px, right=240px（幅720px）/ flex縦中央 / overflow:hidden でQA検出 -->
  <div style="position:absolute;top:240px;left:120px;right:240px;height:550px;
              overflow:hidden;
              display:flex;flex-direction:column;justify-content:center;">
    <div class="text-block" style="font-family:{F_HEAD};font-size:{base}px;font-weight:900;
                color:#ffffff;line-height:1.38;text-align:left;">
      {content_html}
    </div>
  </div>

  {bottom_html}

</div>"""
    return _html_page(div, emph_yellow_px=emph)


SLIDE_GENERATORS = {
    1: s1_hook,
    2: s2_keyfinding,
    3: s3_background,
    4: s4_pico,
    5: s5_results,
    6: s6_critical,
    7: s7_takehome,
}


def _render_html_to_png(html: str, output_path: str, slide_num: int = 0) -> list:
    """HTML を PNG にレンダリングし、QA 問題リストを返す（空 = 合格）。"""
    from playwright.sync_api import sync_playwright

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as f:
        f.write(html)
        tmp = f.name

    issues = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1080, "height": 1350})
            page.goto(f"file://{tmp}")
            page.wait_for_load_state("networkidle")

            issues = page.evaluate("""() => {
                const PAGE_H = 1350;
                const issues = [];

                // 1. canvas overflow: .text-block が 1350px を超えていないか
                for (const el of document.querySelectorAll('.text-block')) {
                    const r = el.getBoundingClientRect();
                    if (r.bottom > PAGE_H + 2 && r.width > 0) {
                        issues.push({
                            type: 'canvas_overflow',
                            text: el.textContent.trim().slice(0, 50),
                            bottom: Math.round(r.bottom)
                        });
                    }
                }

                // 2. container_clipping: max-height 指定の overflow:hidden コンテナ
                // (外側の position:relative ラッパーは max-height を持たないので除外される)
                for (const el of document.querySelectorAll('div[style]')) {
                    const inlineStyle = el.getAttribute('style') || '';
                    if (!inlineStyle.includes('max-height')) continue;
                    const computed = window.getComputedStyle(el);
                    if (computed.overflow !== 'hidden') continue;
                    if (el.clientHeight === 0) continue;
                    // 10px 以上の差がある場合のみ問題とする（端数誤差を除外）
                    if (el.scrollHeight > el.clientHeight + 10) {
                        issues.push({
                            type: 'container_clipping',
                            text: el.textContent.trim().slice(0, 50),
                            scrollH: el.scrollHeight,
                            clientH: el.clientHeight,
                            clipped: el.scrollHeight - el.clientHeight
                        });
                    }
                }

                return issues;
            }""")

            page.screenshot(path=output_path, clip={"x": 0, "y": 0, "width": 1080, "height": 1350})
            browser.close()
    finally:
        os.unlink(tmp)

    for issue in issues:
        if issue["type"] == "canvas_overflow":
            print(f"\n  [QA] canvas_overflow: '{issue['text']}' bottom={issue['bottom']}px")
        elif issue["type"] == "container_clipping":
            print(f"\n  [QA] container_clipping: '{issue['text'][:30]}' clipped={issue['clipped']}px")

    return issues


_FONT_SCALES = [1.0, 0.88, 0.78, 0.70]


def generate_carousel(summary: dict, output_dir: str = ".") -> list:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    pmid = summary.get("pmid", "unknown")

    qa_log = []
    paths = []

    for slide_num, generator in sorted(SLIDE_GENERATORS.items()):
        path = str(out / f"pmid_{pmid}_slide{slide_num}.png")
        slide_qa = {
            "slide": slide_num,
            "passed": False,
            "issues": [],
            "action": "none",
            "retries": 0,
        }

        print(f"[BG] Rendering slide {slide_num}...", end=" ", flush=True)

        for attempt, scale in enumerate(_FONT_SCALES):
            html = generator(summary, font_scale=scale)
            issues = _render_html_to_png(html, path, slide_num=slide_num)

            if not issues:
                slide_qa["passed"] = True
                slide_qa["retries"] = attempt
                slide_qa["action"] = "none" if scale == 1.0 else f"font_scale_{scale:.2f}"
                suffix = f" (scale={scale:.2f})" if scale < 1.0 else ""
                print(f"done{suffix}")
                break

            slide_qa["issues"] = [
                f"{i['type']}:{i.get('text','')[:30]}" for i in issues
            ]
            slide_qa["retries"] = attempt + 1

            if attempt < len(_FONT_SCALES) - 1:
                next_scale = _FONT_SCALES[attempt + 1]
                print(f"[QA retry→{next_scale:.2f}]", end=" ", flush=True)
            else:
                print(f"FAILED")

        qa_log.append(slide_qa)
        paths.append(path)

    # QA ログ保存
    qa_path = str(out / f"pmid_{pmid}_qa.json")
    with open(qa_path, "w", encoding="utf-8") as f:
        json.dump(qa_log, f, ensure_ascii=False, indent=2)
    print(f"[QA] ログ保存: {qa_path}")

    # QA 失敗時は投稿をブロック
    failed = [q for q in qa_log if not q["passed"]]
    if failed:
        details = "; ".join(
            f"Slide{q['slide']}: {q['issues']}" for q in failed
        )
        raise RuntimeError(
            f"[Layout QA失敗] スライド{[q['slide'] for q in failed]}で"
            f"3回リトライ後もQA不合格。投稿をブロックします。\n詳細: {details}"
        )

    return paths


if __name__ == "__main__":
    SAMPLE = Path(__file__).parent.parent / "data" / "sample_summary.json"
    if SAMPLE.exists():
        with open(SAMPLE, encoding="utf-8") as f:
            summary = json.load(f)
    else:
        summary = {
            "pmid": "test001",
            "hook": "早期経腸栄養でPICU死亡率は下がるか？",
            "title_jp": "ICU入室小児における早期経腸栄養と転帰の関連",
            "result_line1": "||24時間以内||開始",
            "result_line2": "||60日||死亡率が低下",
            "study_type": "多施設前向きコホート",
            "year": "2024",
            "journal": "JAMA Pediatr",
            "key_finding": "ICU入室後\n||24時間以内||の\n||経腸栄養開始||は、\n||60日死亡率||を\n||有意に低下||させた\n（||HR 0.71||）",
            "impact_comment": "「**いつ栄養を始めるか**」が\n**予後に直結しうる**と\n示した研究にゃー。\n\n**早期経腸栄養**を\n後回しにしない理由が、\n**かなり強くなった**にゃー。",
            "citation": "Smith J, et al. JAMA Pediatr. 2024;178(3):234-242.",
            "background": "小児ICUでは**栄養不良**が高頻度であり、\n適切な栄養管理が\n転帰改善に重要とされている。\n\nしかし、**最適な開始タイミング**については\nエビデンスが乏しかった。",
            "population": "**18歳未満**のICU入室患者\n***1,247例***（中央値3.2歳）\n\n除外：\n*経腸栄養禁忌*、\n48時間未満のICU滞在予定",
            "pico_p":            "**18歳未満**のICU入室患者（n=***1,247例***）",
            "intervention":      "ICU入室後**24時間以内**の経腸栄養開始",
            "comparison":        "ICU入室後**24時間以降**に経腸栄養開始",
            "outcome":           "**60日死亡率**（主要アウトカム）",
            "design":            "多施設前向きコホート研究\n2020〜2023年、15施設参加",
            "primary_result":    "24時間以内開始群は\n**60日死亡率**が**有意に低下**\n（**HR 0.71**、95%CI 0.54–0.93）\n**p=0.013**",
            "secondary_results": "PICU滞在日数：\n**7日→5日短縮**（**p=0.04**）\n\n人工呼吸器離脱率・感染率：\n有意差なし",
            "limitations":       "観察研究のため**交絡因子**が残る\n因果関係の断定は慎重に\n\n施設間で**プロトコール差**あり\n開始基準・実施方法にばらつき\n\n**栄養・カロリー達成率**は不明\n「開始した」以外の質は読み取りにくい",
            "cat_comment":       "**60日死亡率**は低下したが\nただし**因果関係**までは\n**断定しない**\n観察研究として\n慎重に読むにゃー。",
            "take_home":         "小児ICUでは\n**24時間以内の経腸栄養開始**\nが、**60日死亡率**を\n**改善する可能性**がある。\n\n禁忌や循環不安定がなければ、\n**早期開始を検討**する。",
        }

    out_dir = Path(__file__).parent.parent / "output_bg_test"
    paths = generate_carousel(summary, str(out_dir))
    print(f"\n完了: {len(paths)} 枚 → {out_dir}/")
