#!/usr/bin/env python3
"""PICU Evidence Daily — Infographic Generator v9 (Instagram-Native)"""

import html as _html
import re
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

W, H, N = 1080, 1350, 7

# (dark, mid, light) per study type
STUDY_ACCENT = {
    "RCT":               ("#1D4ED8", "#3B82F6", "#EFF6FF"),
    "Systematic Review": ("#5B21B6", "#7C3AED", "#F5F3FF"),
    "Meta-Analysis":     ("#5B21B6", "#7C3AED", "#F5F3FF"),
    "Cohort Study":      ("#065F46", "#059669", "#ECFDF5"),
    "Guideline":         ("#0C4A6E", "#0284C7", "#F0F9FF"),
    "Review":            ("#5B21B6", "#7C3AED", "#F5F3FF"),
    "Case Series":       ("#92400E", "#D97706", "#FFFBEB"),
}
def sa(st):
    return STUDY_ACCENT.get(st, ("#78350F", "#D97706", "#FEF3C7"))

H_ = _html.escape

BASE = """
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body {
    width: 1080px; height: 1350px; overflow: hidden;
    font-family: 'Hiragino Sans', 'Hiragino Kaku Gothic ProN',
                 'Noto Sans CJK JP', 'Noto Sans JP', 'Yu Gothic', 'Meiryo', sans-serif;
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
}
.slide { width:1080px; height:1350px; display:flex; flex-direction:column; overflow:hidden; }
.c2  { display:-webkit-box; -webkit-line-clamp:2;  -webkit-box-orient:vertical; overflow:hidden; }
.c3  { display:-webkit-box; -webkit-line-clamp:3;  -webkit-box-orient:vertical; overflow:hidden; }
.c4  { display:-webkit-box; -webkit-line-clamp:4;  -webkit-box-orient:vertical; overflow:hidden; }
.c5  { display:-webkit-box; -webkit-line-clamp:5;  -webkit-box-orient:vertical; overflow:hidden; }
.c6  { display:-webkit-box; -webkit-line-clamp:6;  -webkit-box-orient:vertical; overflow:hidden; }
.c8  { display:-webkit-box; -webkit-line-clamp:8;  -webkit-box-orient:vertical; overflow:hidden; }
.c10 { display:-webkit-box; -webkit-line-clamp:10; -webkit-box-orient:vertical; overflow:hidden; }
.clamp2 { display:-webkit-box; -webkit-line-clamp:2;  -webkit-box-orient:vertical; overflow:hidden; }
.clamp3 { display:-webkit-box; -webkit-line-clamp:3;  -webkit-box-orient:vertical; overflow:hidden; }
.clamp4 { display:-webkit-box; -webkit-line-clamp:4;  -webkit-box-orient:vertical; overflow:hidden; }
.clamp5 { display:-webkit-box; -webkit-line-clamp:5;  -webkit-box-orient:vertical; overflow:hidden; }
.clamp6 { display:-webkit-box; -webkit-line-clamp:6;  -webkit-box-orient:vertical; overflow:hidden; }
.clamp8 { display:-webkit-box; -webkit-line-clamp:8;  -webkit-box-orient:vertical; overflow:hidden; }
.clamp10{ display:-webkit-box; -webkit-line-clamp:10; -webkit-box-orient:vertical; overflow:hidden; }
.clamp12{ display:-webkit-box; -webkit-line-clamp:12; -webkit-box-orient:vertical; overflow:hidden; }
b { font-weight: 900; }
"""

def page(body, extra=""):
    return f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{BASE}{extra}</style></head><body>{body}</body></html>"

# ─── Text helpers ─────────────────────────────────────────────────────────────

def _md_bold(text):
    """**text** → <b>text</b> with safe HTML escaping"""
    result = ""
    for part in re.split(r'(\*\*.*?\*\*)', text):
        if part.startswith('**') and part.endswith('**'):
            result += f'<b>{H_(part[2:-2])}</b>'
        else:
            result += H_(part)
    return result

def _bullets(text, dot_color, size=38, weight="700"):
    """Split text on newline/・ and render as bullet list"""
    items = [
        s.strip().lstrip('・').lstrip('-').lstrip('▸').strip()
        for s in re.split(r'[\n・▸]+', text)
        if s.strip().lstrip('・').lstrip('-').lstrip('▸').strip()
    ]
    if len(items) <= 1:
        return (f'<div style="font-size:{size}px;font-weight:{weight};'
                f'color:#1E293B;line-height:1.55">{H_(text)}</div>')
    return ''.join(
        f'<div style="display:flex;align-items:flex-start;gap:14px;'
        f'margin-bottom:10px;flex-shrink:0">'
        f'<span style="color:{dot_color};font-size:{size}px;font-weight:900;'
        f'line-height:1.4;flex-shrink:0">・</span>'
        f'<span style="font-size:{size}px;color:#1E293B;line-height:1.4;'
        f'font-weight:{weight}">{H_(item)}</span></div>'
        for item in items[:6]
    )

def _pico_bullets(text, fg, size=30):
    """PICO item: split on comma/newline, render as ▸ list"""
    items = [
        s.strip().lstrip('・').lstrip('-').strip()
        for s in re.split(r'[\n、，・]+', text)
        if s.strip().lstrip('・').lstrip('-').strip()
    ]
    if len(items) <= 1:
        return f'<div style="font-size:{size}px;color:#1E293B;line-height:1.55">{H_(text)}</div>'
    return ''.join(
        f'<div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:8px">'
        f'<span style="color:{fg};font-size:{size}px;font-weight:900;flex-shrink:0;'
        f'line-height:1.4">▸</span>'
        f'<span style="font-size:{size}px;color:#1E293B;line-height:1.4">{H_(item)}</span>'
        f'</div>'
        for item in items[:4]
    )

# ─── Reusable header/footer ───────────────────────────────────────────────────

def _hdr_light(num, dark, mid):
    return f"""
<div style="height:14px;background:{mid};flex-shrink:0"></div>
<div style="display:flex;align-items:center;justify-content:space-between;
            padding:18px 52px;flex-shrink:0">
  <span style="font-size:21px;font-weight:900;color:{dark}">PICU Evidence Daily</span>
  <span style="font-size:18px;font-weight:700;color:#94A3B8">{num} / {N}</span>
</div>
<div style="height:1px;background:#E2E8F0;margin:0 52px;flex-shrink:0"></div>"""

def _hdr_dark(num):
    return f"""
<div style="display:flex;align-items:center;justify-content:space-between;
            padding:28px 52px 0;flex-shrink:0">
  <span style="font-size:22px;font-weight:900;color:#FFFFFF">PICU Evidence Daily</span>
  <span style="font-size:18px;font-weight:700;color:rgba(255,255,255,.45)">{num} / {N}</span>
</div>"""

def _ftr_light(d, dark, mid, light):
    j, y, s = H_(d.get('journal','')), H_(d.get('year','')), H_(d.get('study_type',''))
    return (f'<div style="background:{light};border-top:3px solid {mid};padding:14px 52px;'
            f'flex-shrink:0;text-align:center">'
            f'<span style="font-size:15px;color:{dark};font-weight:600">'
            f'📰 {j} &nbsp;·&nbsp; {y} &nbsp;·&nbsp; {s}</span></div>')

def _ftr_dark(d):
    j, y, s = H_(d.get('journal','')), H_(d.get('year','')), H_(d.get('study_type',''))
    return (f'<div style="background:rgba(0,0,0,.2);padding:14px 52px;flex-shrink:0;'
            f'text-align:center">'
            f'<span style="font-size:15px;color:rgba(255,255,255,.45)">'
            f'{j} &nbsp;·&nbsp; {y} &nbsp;·&nbsp; {s}</span></div>')

def _badge(text, bg, fg="#FFF"):
    return (f'<span style="background:{bg};color:{fg};font-size:16px;font-weight:900;'
            f'padding:6px 18px;border-radius:8px;letter-spacing:.04em">{H_(text)}</span>')

def _stat_pills(stats, dark, mid, light, dark_theme=False):
    if not stats:
        return ""
    bg = "rgba(255,255,255,.15)" if dark_theme else light
    fg = "#FFFFFF" if dark_theme else dark
    items = ''.join(
        f'<div style="flex:1;background:{bg};border-radius:12px;padding:12px 8px;'
        f'text-align:center;font-size:19px;font-weight:700;color:{fg};line-height:1.3">'
        f'{H_(s)}</div>' for s in stats[:3])
    return f'<div style="display:flex;gap:8px;flex-shrink:0">{items}</div>'


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 1: COVER — 論文タイトルヒーロー、Key Finding補助、CTA
# ─────────────────────────────────────────────────────────────────────────────
def s1_hook(d):
    st      = d.get('study_type', 'RCT')
    dark, mid, light = sa(st)
    title   = H_(d.get('title_jp', ''))
    kf      = H_(d.get('key_finding', ''))
    cit     = H_(d.get('citation', ''))
    j       = H_(d.get('journal', ''))
    y       = H_(d.get('year', ''))

    body = f"""
<div class="slide" style="background:linear-gradient(155deg,{dark} 0%,{mid} 100%)">
  {_hdr_dark(1)}
  <div style="height:2px;background:rgba(255,255,255,.25);margin:14px 52px;flex-shrink:0"></div>

  <!-- Badge row -->
  <div style="display:flex;align-items:center;gap:12px;flex-shrink:0;
              padding:0 52px;margin-bottom:16px">
    {_badge(st, "rgba(255,255,255,.25)")}
    <span style="font-size:17px;color:rgba(255,255,255,.65)">{j} &nbsp;·&nbsp; {y}</span>
  </div>

  <!-- Title hero -->
  <div style="flex:1;min-height:0;display:flex;flex-direction:column;
              justify-content:center;padding:0 52px;gap:24px">
    <div style="font-size:62px;font-weight:900;color:#FFFFFF;line-height:1.4;
                overflow:hidden" class="c4">{title}</div>

    <!-- Key Finding box -->
    <div style="background:rgba(255,255,255,.15);border-radius:16px;
                padding:18px 24px;flex-shrink:0">
      <div style="font-size:11px;font-weight:800;color:rgba(255,255,255,.5);
                  letter-spacing:.2em;margin-bottom:8px">K E Y &nbsp; F I N D I N G</div>
      <div style="font-size:32px;font-weight:700;color:#FFFFFF;line-height:1.45;
                  overflow:hidden" class="c3">{kf}</div>
    </div>
  </div>

  <!-- CTA + citation -->
  <div style="padding:16px 52px 12px;flex-shrink:0">
    <div style="font-size:17px;font-weight:700;color:rgba(255,255,255,.55);
                margin-bottom:10px">スライドをスワイプして詳細を見る &nbsp;▶</div>
    {f'<div style="font-size:13px;color:rgba(255,255,255,.3);line-height:1.4">{cit}</div>' if cit else ''}
  </div>

  {_ftr_dark(d)}
</div>"""
    return page(body)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 2: KEY FINDING — 白上部 (KF+驚き+キャラ) / 色下部 (stats)
# ─────────────────────────────────────────────────────────────────────────────
def s2_keyfinding(d):
    st = d.get('study_type', 'RCT')
    dark, mid, light = sa(st)
    kf      = H_(d.get('key_finding', ''))
    impact  = H_(d.get('impact_comment', ''))
    title   = H_(d.get('title_jp', ''))
    sa_     = d.get('stat_a', '')
    sb_     = d.get('stat_b', '')
    sal     = d.get('stat_a_label', '介入群')
    sbl     = d.get('stat_b_label', '対照群')
    ctx     = d.get('stat_context', '')
    stats   = d.get('stats', [])
    design  = H_(d.get('design', ''))

    # Bottom panel: compare + pills on brand color
    has_stats = bool((sa_ and sb_) or stats)
    compare_html = ""
    if sa_ and sb_:
        compare_html = f"""
<div style="background:rgba(255,255,255,.12);border-radius:18px;padding:18px 20px;flex-shrink:0">
  <div style="font-size:13px;font-weight:700;color:rgba(255,255,255,.55);text-align:center;
              margin-bottom:12px">{H_(ctx)}</div>
  <div style="display:flex;align-items:stretch">
    <div style="flex:1;text-align:center;padding:12px 8px;
                border-right:2px solid rgba(255,255,255,.2)">
      <div style="font-size:86px;font-weight:900;color:#FFFFFF;line-height:1">{H_(sa_)}</div>
      <div style="font-size:16px;font-weight:700;color:rgba(255,255,255,.75);margin-top:6px">{H_(sal)}</div>
    </div>
    <div style="width:60px;display:flex;align-items:center;justify-content:center;
                font-size:20px;font-weight:900;color:rgba(255,255,255,.35)">vs</div>
    <div style="flex:1;text-align:center;padding:12px 8px;
                border-left:2px solid rgba(255,255,255,.2)">
      <div style="font-size:86px;font-weight:900;color:rgba(255,255,255,.5);line-height:1">{H_(sb_)}</div>
      <div style="font-size:16px;font-weight:700;color:rgba(255,255,255,.45);margin-top:6px">{H_(sbl)}</div>
    </div>
  </div>
</div>"""

    pills = _stat_pills(stats, dark, mid, light, dark_theme=True)

    bottom = ""
    if has_stats:
        bottom = f"""
<div style="flex:1;min-height:0;background:{dark};display:flex;flex-direction:column;
            justify-content:center;padding:24px 52px;gap:12px">
  {compare_html}
  {pills}
</div>"""

    # Impact comment block (口語的)
    impact_block = ""
    if impact:
        impact_block = f"""
<div style="background:{light};border-radius:14px;padding:14px 20px;
            border-left:5px solid {mid};flex-shrink:0;margin-top:12px">
  <span style="font-size:28px">💬</span>
  <span style="font-size:26px;font-weight:700;color:{dark};margin-left:10px">{impact}</span>
</div>"""

    body = f"""
<div class="slide" style="background:#FFFFFF">
  {_hdr_light(2, dark, mid)}

  <!-- Top: white — KF + impact -->
  <div style="{'flex:1' if not has_stats else ''};min-height:0;display:flex;
              flex-direction:column;justify-content:center;padding:22px 52px;overflow:hidden">
    <div style="display:flex;align-items:center;gap:10px;flex-shrink:0;margin-bottom:14px">
      {_badge(st, dark)}
      <span style="font-size:14px;color:#64748B">
        {H_(d.get('journal',''))} &nbsp;·&nbsp; {H_(d.get('year',''))}
        {f' &nbsp;·&nbsp; {design}' if design else ''}
      </span>
    </div>
    <div style="font-size:11px;font-weight:800;color:{mid};letter-spacing:.2em;
                flex-shrink:0;margin-bottom:10px">K E Y &nbsp; F I N D I N G</div>
    <div style="font-size:60px;font-weight:900;color:#0F172A;line-height:1.4;
                overflow:hidden" class="c4">{kf}</div>
    {impact_block}
    <div style="margin-top:14px;font-size:18px;font-weight:700;color:#64748B;
                overflow:hidden;flex-shrink:0" class="c2">{title}</div>
  </div>

  {bottom}

  {_ftr_light(d, dark, mid, light)}
</div>"""
    return page(body)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 3: BACKGROUND — 太字サポート、箇条書き対象患者
# ─────────────────────────────────────────────────────────────────────────────
def s3_background(d):
    st = d.get('study_type', 'RCT')
    dark, mid, light = sa(st)
    bg_text = d.get('background', '')
    pop     = d.get('population', '')

    chip = (f'<span style="display:inline-block;background:{dark};color:#FFF;font-size:13px;'
            f'font-weight:800;padding:5px 16px;border-radius:6px;letter-spacing:.08em;'
            f'margin-bottom:14px;flex-shrink:0">')

    pop_block = ""
    if pop:
        pop_block = f"""
<div style="flex-shrink:0;border-top:3px solid {mid};padding-top:20px;margin-top:8px">
  {chip}対象患者 / POPULATION</span>
  {_bullets(pop, mid, size=40, weight='700')}
</div>"""

    body = f"""
<div class="slide" style="background:#FFFFFF">
  {_hdr_light(3, dark, mid)}

  <div style="padding:16px 52px 0;flex-shrink:0">
    <div style="font-size:50px;font-weight:900;color:{dark}">なぜこの研究？</div>
  </div>

  <div style="flex:1;min-height:0;padding:20px 52px 20px;overflow:hidden;
              display:flex;flex-direction:column">
    {chip}BACKGROUND</span>
    <div style="font-size:40px;color:#1E293B;line-height:1.6;overflow:hidden;flex-shrink:0"
         class="c6">{_md_bold(bg_text)}</div>
    {pop_block}
  </div>

  {_ftr_light(d, dark, mid, light)}
</div>"""
    return page(body)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 4: PICO — 箇条書き、文字大きく
# ─────────────────────────────────────────────────────────────────────────────
def s4_pico(d):
    st = d.get('study_type', 'RCT')
    dark, mid, light = sa(st)
    design = d.get('design', '')

    pico = [
        ("P", "Population",   d.get('population',''),   "#1D4ED8", "#DBEAFE"),
        ("I", "Intervention", d.get('intervention',''), "#B91C1C", "#FEE2E2"),
        ("C", "Comparison",   d.get('comparison',''),   "#B45309", "#FEF3C7"),
        ("O", "Outcome",      d.get('outcome',''),      "#065F46", "#D1FAE5"),
    ]
    items = [(l, lb, v, fg, bg) for (l, lb, v, fg, bg) in pico if v]
    n = len(items) or 1
    font = 30 if n >= 4 else 34

    rows = ""
    for letter, label, value, fg, bg in items:
        rows += f"""
<div style="flex:1;min-height:0;display:flex;overflow:hidden">
  <div style="width:90px;background:{fg};flex-shrink:0;display:flex;flex-direction:column;
              align-items:center;justify-content:center;gap:4px">
    <span style="font-size:44px;font-weight:900;color:#FFF">{letter}</span>
    <span style="font-size:11px;font-weight:700;color:rgba(255,255,255,.7);
                 writing-mode:vertical-lr;transform:rotate(180deg);letter-spacing:.08em">{label}</span>
  </div>
  <div style="flex:1;background:{bg};padding:16px 26px;overflow:hidden;display:flex;flex-direction:column;justify-content:center">
    {_pico_bullets(value, fg, size=font)}
  </div>
</div>"""

    dbadge = (f'<span style="background:{dark};color:#FFF;font-size:14px;font-weight:800;'
              f'padding:5px 16px;border-radius:8px">{H_(design)}</span>') if design else ''

    body = f"""
<div class="slide" style="background:#FFFFFF">
  {_hdr_light(4, dark, mid)}
  <div style="flex-shrink:0;padding:12px 52px 10px;display:flex;align-items:center;gap:12px">
    <span style="font-size:38px;font-weight:900;color:{dark}">PICO &nbsp;/&nbsp; Methods</span>
    {dbadge}
  </div>
  <div style="flex:1;display:flex;flex-direction:column;gap:3px;overflow:hidden;min-height:0">
    {rows}
  </div>
  {_ftr_light(d, dark, mid, light)}
</div>"""
    return page(body)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 5: RESULTS — 比較図大きく、副次アウトカム込み
# ─────────────────────────────────────────────────────────────────────────────
def s5_results(d):
    st = d.get('study_type', 'RCT')
    dark, mid, light = sa(st)
    sa_       = d.get('stat_a', '')
    sb_       = d.get('stat_b', '')
    sal       = d.get('stat_a_label', '介入群')
    sbl       = d.get('stat_b_label', '対照群')
    ctx       = d.get('stat_context', '')
    stats     = d.get('stats', [])
    secondary = d.get('secondary_results', '')

    # Large visual comparison
    compare_block = ""
    if sa_ and sb_:
        compare_block = f"""
<div style="background:#F8FAFC;border-radius:20px;padding:24px 32px;flex-shrink:0">
  <div style="font-size:14px;font-weight:700;color:#64748B;text-align:center;
              margin-bottom:18px;letter-spacing:.06em">{H_(ctx)}</div>
  <div style="display:flex;align-items:stretch;gap:0">
    <div style="flex:1;text-align:center;background:{light};border-radius:16px 0 0 16px;
                padding:20px 12px;border-right:2px solid #E2E8F0">
      <div style="font-size:100px;font-weight:900;color:{dark};line-height:1">{H_(sa_)}</div>
      <div style="font-size:18px;font-weight:700;color:{mid};margin-top:10px">{H_(sal)}</div>
    </div>
    <div style="width:70px;display:flex;align-items:center;justify-content:center;
                font-size:22px;font-weight:900;color:#94A3B8">vs</div>
    <div style="flex:1;text-align:center;background:#F1F5F9;border-radius:0 16px 16px 0;
                padding:20px 12px;border-left:2px solid #E2E8F0">
      <div style="font-size:100px;font-weight:900;color:#475569;line-height:1">{H_(sb_)}</div>
      <div style="font-size:18px;font-weight:700;color:#64748B;margin-top:10px">{H_(sbl)}</div>
    </div>
  </div>
</div>"""
    elif sa_ or sb_:
        # Only one stat — show as single big number
        val = sa_ or sb_
        lbl = sal if sa_ else sbl
        compare_block = f"""
<div style="background:{light};border-radius:20px;padding:24px 32px;
            text-align:center;flex-shrink:0">
  <div style="font-size:100px;font-weight:900;color:{dark};line-height:1">{H_(val)}</div>
  <div style="font-size:20px;font-weight:700;color:{mid};margin-top:10px">{H_(lbl)}</div>
</div>"""

    pills = _stat_pills(stats, dark, mid, light)

    sec_block = ""
    if secondary:
        sec_block = f"""
<div style="flex-shrink:0;background:{light};border-radius:12px;border-left:5px solid {mid};
            padding:14px 20px">
  <div style="font-size:12px;font-weight:800;color:{mid};letter-spacing:.1em;margin-bottom:8px">
    SECONDARY OUTCOMES
  </div>
  <div style="font-size:28px;color:#1E293B;line-height:1.5;overflow:hidden" class="c3">
    {H_(secondary)}
  </div>
</div>"""

    body = f"""
<div class="slide" style="background:#FFFFFF">
  {_hdr_light(5, dark, mid)}

  <div style="flex:1;display:flex;flex-direction:column;padding:18px 52px 16px;
              gap:14px;overflow:hidden;min-height:0">
    <div style="font-size:36px;font-weight:900;color:{dark};flex-shrink:0">
      📊 &nbsp;Results
    </div>
    {compare_block}
    {pills}
    {sec_block}
  </div>

  {_ftr_light(d, dark, mid, light)}
</div>"""
    return page(body)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 6: STATISTICS DETAIL — S5スタイルで統計詳細
# ─────────────────────────────────────────────────────────────────────────────
def s6_stats(d):
    st = d.get('study_type', 'RCT')
    dark, mid, light = sa(st)
    stats     = d.get('stats', [])
    secondary = d.get('secondary_results', '')
    primary   = d.get('primary_result', '')

    card_colors = [
        (dark, light),
        ("#B91C1C", "#FEE2E2"),
        ("#065F46", "#D1FAE5"),
        ("#B45309", "#FEF3C7"),
        ("#0C4A6E", "#F0F9FF"),
    ]
    n = len(stats[:5])
    font = 64 if n <= 2 else (54 if n == 3 else (44 if n <= 4 else 36))

    stat_cards = ""
    for i, s in enumerate(stats[:5]):
        fg, bg = card_colors[i % len(card_colors)]
        stat_cards += f"""
<div style="flex:1;min-height:0;background:{bg};border-radius:14px;
            border-left:6px solid {fg};padding:18px 24px;overflow:hidden;
            display:flex;align-items:center">
  <div style="font-size:{font}px;font-weight:900;color:{fg};line-height:1.3;
              overflow:hidden" class="c2">{H_(s)}</div>
</div>"""

    # Primary result as context
    primary_block = ""
    if primary:
        primary_block = f"""
<div style="flex-shrink:0;background:{light};border-radius:12px;border-left:5px solid {mid};
            padding:14px 20px">
  <div style="font-size:12px;font-weight:800;color:{mid};letter-spacing:.1em;margin-bottom:8px">
    PRIMARY RESULT
  </div>
  <div style="font-size:26px;color:#1E293B;line-height:1.5;overflow:hidden" class="c3">
    {H_(primary)}
  </div>
</div>"""

    body = f"""
<div class="slide" style="background:#FFFFFF">
  {_hdr_light(6, dark, mid)}
  <div style="flex:1;display:flex;flex-direction:column;padding:18px 52px 16px;
              gap:12px;overflow:hidden;min-height:0">
    <div style="font-size:36px;font-weight:900;color:{dark};flex-shrink:0">
      📈 &nbsp;Statistics
    </div>
    <div style="flex:1;min-height:0;display:flex;flex-direction:column;gap:10px">
      {stat_cards}
    </div>
    {primary_block}
  </div>
  {_ftr_light(d, dark, mid, light)}
</div>"""
    return page(body)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 7: TAKE HOME — 明るい背景、ピクトグラム、わかりやすく
# ─────────────────────────────────────────────────────────────────────────────
def s7_takehome(d):
    st = d.get('study_type', 'RCT')
    dark, mid, light = sa(st)
    take    = H_(d.get('take_home', ''))
    lim_raw = d.get('limitations', '')
    lim_lines = [l.strip().lstrip('-').strip() for l in lim_raw.split('\n') if l.strip()]
    cit     = H_(d.get('citation', ''))

    lim_block = ""
    if lim_lines:
        lim_items = ''.join(
            f'<div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:8px">'
            f'<span style="color:{mid};font-size:22px;flex-shrink:0;font-weight:900">⚠</span>'
            f'<span style="font-size:22px;color:#475569;line-height:1.4">{H_(l)}</span></div>'
            for l in lim_lines[:3])
        lim_block = f"""
<div style="flex-shrink:0;background:#F8FAFC;border-radius:12px;border:1px solid #E2E8F0;
            padding:16px 20px">
  <div style="font-size:12px;font-weight:800;color:#94A3B8;letter-spacing:.12em;
              margin-bottom:10px">LIMITATIONS</div>
  {lim_items}
</div>"""

    body = f"""
<div class="slide" style="background:{light}">
  {_hdr_light(7, dark, mid)}

  <!-- Character + heading -->
  <div style="display:flex;align-items:center;gap:20px;padding:16px 52px 0;flex-shrink:0">
    <span style="font-size:80px;line-height:1">🩺</span>
    <div>
      <div style="font-size:36px;font-weight:900;color:{dark}">Take Home Message</div>
      <div style="height:3px;background:{mid};border-radius:3px;margin-top:8px;width:200px"></div>
    </div>
  </div>

  <!-- Main message -->
  <div style="flex:1;min-height:0;display:flex;flex-direction:column;
              padding:18px 52px 0;gap:14px;overflow:hidden">
    <div style="font-size:12px;font-weight:800;color:{mid};letter-spacing:.15em;flex-shrink:0">
      CLINICAL IMPLICATION
    </div>
    <div style="font-size:46px;font-weight:900;color:#0F172A;line-height:1.45;
                overflow:hidden" class="c6">{take}</div>
  </div>

  <!-- Limitations + citation -->
  <div style="padding:12px 52px 12px;display:flex;flex-direction:column;gap:10px;flex-shrink:0">
    {lim_block}
    {f'<div style="font-size:13px;color:#94A3B8;line-height:1.4">{cit}</div>' if cit else ''}
  </div>

  <!-- CTA bar -->
  <div style="background:{mid};padding:14px 52px;flex-shrink:0;text-align:center">
    <span style="font-size:17px;font-weight:800;color:#FFF">
      💾 保存して後で読み返そう &nbsp;·&nbsp; フォローで最新エビデンスを 🔔
    </span>
  </div>
</div>"""
    return page(body)


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────
def _norm(data):
    d = dict(data)
    for f in ["population","limitations","background","intervention","comparison",
              "outcome","primary_result","secondary_results","take_home",
              "key_finding","title_jp","title_en","impact_comment"]:
        v = d.get(f, "")
        if isinstance(v, list): d[f] = "\n".join(str(x) for x in v)
        elif not isinstance(v, str): d[f] = str(v) if v else ""
    return d

def screenshot(html_str, path):
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox','--disable-dev-shm-usage'])
        pg      = browser.new_page(viewport={"width": W, "height": H})
        pg.set_content(html_str, wait_until="domcontentloaded")
        pg.wait_for_timeout(400)
        pg.screenshot(path=str(path), clip={"x":0,"y":0,"width":W,"height":H})
        browser.close()

def generate_carousel(data, output_dir="output"):
    if not HAS_PLAYWRIGHT:
        raise RuntimeError("pip install playwright && playwright install chromium")
    data = _norm(data)
    out  = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    pmid = data.get("pmid", "unknown")
    builders = [s1_hook, s2_keyfinding, s3_background, s4_pico,
                s5_results, s6_stats, s7_takehome]
    paths = []
    for i, fn in enumerate(builders, 1):
        path = out / f"pmid_{pmid}_slide{i}.png"
        print(f"  Rendering slide {i}/{N}...", end=" ", flush=True)
        screenshot(fn(data), str(path))
        print("done")
        paths.append(path)
    print(f"Generated {len(paths)} slides -> {out}/")
    return paths


if __name__ == "__main__":
    import sys
    sample = {
        "pmid":"v9test","study_type":"RCT","journal":"NEJM","year":"2025",
        "title_jp":"小児敗血症性ショックに対する早期バソプレシン投与の有効性",
        "title_en":"Early Vasopressin in Pediatric Septic Shock: A Randomized Controlled Trial",
        "key_finding":"早期バソプレシン追加により28日死亡率が有意に低下した（18.2% vs 26.7%, p=0.002）",
        "impact_comment":"小児でもバソプレシンが効く！NNT=12——12人に1人の命に直結する結果",
        "background":"小児敗血症性ショックでは、**ノルアドレナリン不応性**の血管拡張が予後不良因子となる。成人領域ではバソプレシンの早期併用が推奨されているが、小児での**大規模RCT**は存在しなかった。",
        "population":"・生後1ヶ月-17歳\n・敗血症性ショック患児\n・n=1,200\n・28施設の小児ICU",
        "intervention":"ノルアドレナリン開始後6時間以内にバソプレシン 0.0003-0.002 U/kg/min を追加",
        "comparison":"生理食塩水（プラセボ）を追加",
        "outcome":"28日全死亡率（主要）、臓器障害日数、カテコラミン使用期間（副次）",
        "design":"Multicenter double-blind placebo-controlled RCT",
        "primary_result":"28日死亡率はバソプレシン群18.2% vs プラセボ群26.7%、絶対リスク差 -8.5% (95%CI: -13.1〜-3.9%, p=0.002)。NNT=12。",
        "stat_a":"18.2%","stat_a_label":"バソプレシン群",
        "stat_b":"26.7%","stat_b_label":"プラセボ群","stat_context":"28日死亡率",
        "stats":["HR 0.68 (95%CI 0.52-0.89)","p = 0.002","NNT = 12"],
        "secondary_results":"ICU滞在期間中央値はバソプレシン群8日 vs プラセボ群11日（p=0.03）。カテコラミン使用期間も有意に短縮。",
        "take_home":"敗血症性ショックの小児にノルアドレナリンを開始したら、早期（6時間以内）にバソプレシンの追加を検討しよう。NNT=12——手術で言えば12件に1件助かる計算。",
        "limitations":"- 単一民族（欧州）での試験で一般化可能性に限界\n- バソプレシン投与タイミングの個別最適化は未解明\n- 開放ラベル延長試験なし",
        "citation":"Smith J, et al. Early Vasopressin in Pediatric Septic Shock. NEJM. 2025. doi:10.1056/test",
        "hashtags":["PICU","Sepsis","Vasopressin","小児敗血症","RCT"],
        "authors":["Smith J","Doe A"],"doi":"10.1056/test",
    }
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "output"
    generate_carousel(sample, out_dir)
