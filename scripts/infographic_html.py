#!/usr/bin/env python3
"""PICU Evidence Daily — Infographic Generator v16 (高密度 Visual Abstract)"""

import html as _html
import re
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

W, H, N = 1080, 1350, 7

C = {
    'primary':   '#2563EB',
    'navy':      '#0F172A',
    'navy_med':  '#1E3A8A',
    'sky':       '#EFF6FF',
    'ice':       '#DBEAFE',
    'white':     '#FFFFFF',
    'slate':     '#334155',
    'muted':     '#64748B',
    'amber':     '#D97706',
    'teal':      '#0F766E',
    'gray':      '#F8FAFC',
    'border':    '#E2E8F0',
    'border_md': '#CBD5E1',
}

STUDY_ACCENT = {
    'RCT':               C['primary'],
    'Systematic Review': C['navy_med'],
    'Meta-Analysis':     C['navy_med'],
    'Cohort Study':      C['teal'],
    'Guideline':         C['navy'],
    'Review':            C['navy_med'],
    'Case Series':       C['muted'],
}

def ac(st): return STUDY_ACCENT.get(st, C['primary'])
H_ = _html.escape

BASE = (
    "* { box-sizing: border-box; margin: 0; padding: 0; }"
    "html, body {"
    "  width: 1080px; height: 1350px; overflow: hidden;"
    "  font-family: 'Hiragino Sans', 'Hiragino Kaku Gothic ProN',"
    "               'Noto Sans CJK JP', 'Noto Sans JP', 'Yu Gothic',"
    "               -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;"
    "  -webkit-font-smoothing: antialiased;"
    "  text-rendering: optimizeLegibility;"
    "  color: #334155;"
    "}"
    ".slide {"
    "  width: 1080px; height: 1350px;"
    "  display: flex; flex-direction: column; overflow: hidden;"
    "  position: relative; isolation: isolate;"
    "}"
    ".num { font-variant-numeric: tabular-nums; font-feature-settings: 'tnum'; }"
    "b { font-weight: 900; }"
)

def page(body, extra=""):
    return (f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<style>{BASE}{extra}</style></head><body>{body}</body></html>")


# ── Text helpers ───────────────────────────────────────────────────────────────

def _md_bold(text):
    result = ""
    for part in re.split(r'(\*\*.*?\*\*)', text):
        if part.startswith('**') and part.endswith('**'):
            result += f'<b>{H_(part[2:-2])}</b>'
        else:
            result += H_(part)
    return result

def _title_size(text, base=64):
    n = len(text)
    if n <= 18: return base
    if n <= 26: return int(base * 0.87)
    if n <= 34: return int(base * 0.76)
    if n <= 48: return int(base * 0.65)
    return int(base * 0.57)

def _fit(text, base=48, min_size=28):
    n = len(text)
    for max_n, f in [(40, 1.0), (65, 0.87), (100, 0.75), (150, 0.65), (999, 0.55)]:
        if n <= max_n:
            return max(min_size, int(base * f))
    return min_size

def _label(text, color, mb=12):
    return (f'<div style="font-size:15px;font-weight:700;letter-spacing:0.14em;'
            f'text-transform:uppercase;color:{color};margin-bottom:{mb}px">{H_(text)}</div>')

def _study_pill(st, color):
    return (f'<span style="display:inline-block;background:{color};color:#fff;'
            f'font-size:14px;font-weight:700;padding:5px 14px;border-radius:6px;'
            f'letter-spacing:0.06em">{H_(st)}</span>')

def _bullets_clean(text, color, size=32):
    items = [
        s.strip().lstrip('-').lstrip('・').strip()
        for s in re.split(r'[\n・]+', text)
        if s.strip().lstrip('-').lstrip('・').strip()
    ]
    if len(items) <= 1:
        return f'<div style="font-size:{size}px;color:{C["slate"]};line-height:1.5">{H_(text)}</div>'
    return ''.join(
        f'<div style="display:flex;align-items:flex-start;gap:12px;margin-bottom:8px">'
        f'<div style="width:6px;height:6px;border-radius:50%;background:{color};'
        f'margin-top:{int(size*0.52)}px;flex-shrink:0"></div>'
        f'<div style="font-size:{size}px;color:{C["slate"]};line-height:1.45;font-weight:500">'
        f'{H_(item)}</div></div>'
        for item in items[:5]
    )


# ── Header / Footer ────────────────────────────────────────────────────────────

def _hdr(num, color, dark=False):
    fg  = '#fff' if dark else color
    sub = 'rgba(255,255,255,.5)' if dark else C['muted']
    return f"""
<div style="height:6px;background:{color};flex-shrink:0"></div>
<div style="height:76px;display:flex;align-items:center;justify-content:space-between;
            padding:0 60px;flex-shrink:0">
  <span style="font-size:20px;font-weight:800;color:{fg};letter-spacing:0.02em">
    PICU Evidence Daily
  </span>
  <span style="font-size:17px;font-weight:600;color:{sub}">{num} / {N}</span>
</div>"""

def _ftr(d, color, dark=False):
    j  = H_(d.get('journal', ''))
    y  = H_(d.get('year', ''))
    s  = H_(d.get('study_type', ''))
    fg = 'rgba(255,255,255,.35)' if dark else C['muted']
    bg = 'rgba(0,0,0,.15)' if dark else C['gray']
    bd = 'transparent' if dark else C['border']
    return (f'<div style="height:58px;background:{bg};border-top:1px solid {bd};'
            f'display:flex;align-items:center;justify-content:center;'
            f'flex-shrink:0;padding:0 60px">'
            f'<span style="font-size:15px;font-weight:500;color:{fg};letter-spacing:0.04em">'
            f'{j}&nbsp;&nbsp;·&nbsp;&nbsp;{y}&nbsp;&nbsp;·&nbsp;&nbsp;{s}'
            f'</span></div>')

def _rule(color=None, mx=60):
    color = color or C['border']
    return f'<div style="height:1px;background:{color};margin:0 {mx}px;flex-shrink:0"></div>'


# ── Content density check ──────────────────────────────────────────────────────

def _check_density(slide_num, html_str):
    text = re.sub(r'<[^>]+>', '', html_str)
    text = re.sub(r'\s+', ' ', text).strip()
    n = len(text)
    if n < 160:
        print(f"  [WARN] Slide {slide_num}: sparse ({n} chars) — content density may be low")
    return n


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 1: COVER
# ─────────────────────────────────────────────────────────────────────────────
def s1_hook(d):
    st    = d.get('study_type', 'RCT')
    color = ac(st)
    title = d.get('title_jp', '')
    j     = H_(d.get('journal', ''))
    y     = H_(d.get('year', ''))
    sa    = d.get('stat_a', '')
    sb    = d.get('stat_b', '')
    sal   = d.get('stat_a_label', '介入群')
    sbl   = d.get('stat_b_label', '対照群')
    ctx   = d.get('stat_context', '主要アウトカム')
    kf    = d.get('key_finding', '')
    impact = d.get('impact_comment', '')
    pop   = d.get('population', '')
    rq    = d.get('research_question', '')

    nnt_m = re.search(r'NNT\s*[=＝]\s*(\d+)', kf + impact)
    arr_m = re.search(r'ARR\s*(-?[\d.]+\s*%)', kf + impact)
    nnt = nnt_m.group(1) if nnt_m else ''
    arr = arr_m.group(1).replace(' ', '') if arr_m else ''

    n_m   = re.search(r'n\s*=\s*([\d,]+)', pop)
    fac_m = re.search(r'(\d+)施設', pop)
    study_info = []
    if n_m:   study_info.append(f"n={n_m.group(1)}")
    if fac_m: study_info.append(f"{fac_m.group(1)} PICUs")

    ts = _title_size(title)

    comparison_html = ""
    if sa and sb:
        comparison_html = f"""
<div style="display:flex;align-items:flex-end;gap:28px;margin-top:20px">
  <div>
    <div style="font-size:13px;font-weight:700;color:{color};
                letter-spacing:0.1em;margin-bottom:4px">{H_(sal)}</div>
    <div class="num" style="font-size:84px;font-weight:900;color:#fff;line-height:0.92">{H_(sa)}</div>
  </div>
  <div style="font-size:24px;color:rgba(255,255,255,.3);padding-bottom:12px">vs</div>
  <div>
    <div style="font-size:13px;font-weight:700;color:rgba(255,255,255,.45);
                letter-spacing:0.1em;margin-bottom:4px">{H_(sbl)}</div>
    <div class="num" style="font-size:84px;font-weight:900;color:rgba(255,255,255,.45);line-height:0.92">{H_(sb)}</div>
  </div>
</div>"""

    stat_pills = []
    if arr:
        stat_pills.append(
            f'<div style="background:rgba(255,255,255,.12);border-radius:10px;padding:14px 28px">'
            f'<div style="font-size:12px;font-weight:700;color:rgba(255,255,255,.5);'
            f'letter-spacing:0.1em;text-transform:uppercase">ARR</div>'
            f'<div class="num" style="font-size:42px;font-weight:900;color:#fff;line-height:1.05">'
            f'{H_(arr)}</div></div>'
        )
    if nnt:
        stat_pills.append(
            f'<div style="background:{color};border-radius:10px;padding:14px 28px">'
            f'<div style="font-size:12px;font-weight:700;color:rgba(255,255,255,.6);'
            f'letter-spacing:0.1em;text-transform:uppercase">NNT</div>'
            f'<div class="num" style="font-size:42px;font-weight:900;color:#fff;line-height:1.05">'
            f'{H_(nnt)}</div></div>'
        )
    stat_pills_html = ""
    if stat_pills:
        stat_pills_html = (f'<div style="display:flex;gap:12px;margin-top:20px">'
                           f'{"".join(stat_pills)}</div>')

    info_pills_html = ""
    if study_info:
        pills = ''.join(
            f'<span style="background:rgba(255,255,255,.09);color:rgba(255,255,255,.55);'
            f'font-size:15px;font-weight:600;padding:6px 16px;border-radius:8px">{H_(s)}</span>'
            for s in study_info
        )
        info_pills_html = f'<div style="display:flex;gap:8px;margin-top:20px">{pills}</div>'

    rq_html = ""
    if rq:
        rq_html = f"""
<div style="margin:0 60px;background:rgba(255,255,255,.06);border-radius:14px;
            padding:20px 26px;flex-shrink:0">
  <div style="font-size:13px;font-weight:700;color:rgba(255,255,255,.4);
              letter-spacing:0.12em;text-transform:uppercase;margin-bottom:8px">
    Research Question
  </div>
  <div style="font-size:28px;font-weight:600;color:rgba(255,255,255,.75);
              line-height:1.5">{H_(rq)}</div>
</div>"""

    body = f"""
<div class="slide" style="background:{C['navy']}">
  <div style="height:6px;background:{color};flex-shrink:0"></div>

  <div style="height:76px;display:flex;align-items:center;justify-content:space-between;
              padding:0 60px;flex-shrink:0">
    <span style="font-size:20px;font-weight:800;color:rgba(255,255,255,.9);
                 letter-spacing:0.02em">PICU Evidence Daily</span>
    <div style="display:flex;align-items:center;gap:12px">
      {_study_pill(st, color)}
      <span style="font-size:15px;color:rgba(255,255,255,.38)">{j}&nbsp;·&nbsp;{y}</span>
    </div>
  </div>

  <div style="height:1px;background:rgba(255,255,255,.1);margin:0 60px;flex-shrink:0"></div>

  <div style="flex:1;min-height:0;display:flex;flex-direction:column;
              padding:24px 0 8px;overflow:hidden;gap:12px">

    <div style="padding:0 60px;flex-shrink:0">
      <div style="font-size:{ts}px;font-weight:900;color:#FFFFFF;line-height:1.14">
        {H_(title)}
      </div>
    </div>

    <div style="margin:0 60px;flex-shrink:0;background:rgba(255,255,255,.09);
                border:1px solid rgba(255,255,255,.16);border-radius:18px;
                padding:26px 28px">
      <div style="font-size:13px;font-weight:700;color:{color};
                  letter-spacing:0.12em;text-transform:uppercase">{H_(ctx)}</div>
      {comparison_html}
      {stat_pills_html}
    </div>

    <div style="padding:0 60px;flex-shrink:0">
      {info_pills_html}
    </div>

    <div style="margin-top:auto;flex-shrink:0;display:flex;flex-direction:column;gap:10px">
      {rq_html}
      <div style="padding:0 60px 6px">
        <div style="font-size:15px;color:rgba(255,255,255,.25)">スワイプして詳細を見る</div>
      </div>
    </div>

  </div>

  {_ftr(d, color, dark=True)}
</div>"""
    _check_density(1, body)
    return page(body)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 2: CLINICAL BOTTOM LINE
# ─────────────────────────────────────────────────────────────────────────────
def s2_keyfinding(d):
    st     = d.get('study_type', 'RCT')
    color  = ac(st)
    impact = d.get('impact_comment', '')
    kf     = d.get('key_finding', '')
    reading = d.get('clinical_reading', '')

    nnt_m = re.search(r'NNT\s*[=＝]\s*(\d+)', impact + kf)
    arr_m = re.search(r'ARR\s*(-?[\d.]+\s*%)', impact + kf)
    hr_m  = re.search(r'HR\s+([\d.]+)', impact + kf)

    nnt = nnt_m.group(1) if nnt_m else ''
    arr = arr_m.group(1).replace(' ', '') if arr_m else ''
    hr  = hr_m.group(1) if hr_m else ''

    impact_size = _fit(impact, base=52, min_size=32)

    # 3 metric cards
    metrics = []
    if nnt: metrics.append(('NNT', nnt, '治療必要数', True))
    if arr: metrics.append(('ARR', arr, '絶対リスク差', False))
    if hr:  metrics.append(('HR',  hr,  'ハザード比',  False))

    metric_cards = []
    for lbl, val, sub, hi in metrics[:3]:
        bg  = C['ice'] if hi else C['gray']
        fc  = color if hi else C['slate']
        bdr = f'border:2px solid {color};' if hi else f'border:1px solid {C["border"]};'
        val_size = 80 if hi else (60 if len(val) <= 6 else 42)
        metric_cards.append(
            f'<div style="flex:1;background:{bg};border-radius:14px;'
            f'padding:22px 18px;text-align:center;{bdr}">'
            f'<div style="font-size:13px;font-weight:700;color:{C["muted"]};'
            f'letter-spacing:0.12em;text-transform:uppercase;margin-bottom:10px">{H_(lbl)}</div>'
            f'<div class="num" style="font-size:{val_size}px;font-weight:900;'
            f'color:{fc};line-height:1">{H_(val)}</div>'
            f'<div style="font-size:16px;font-weight:600;color:{C["muted"]};'
            f'margin-top:10px">{H_(sub)}</div>'
            f'</div>'
        )
    metric_row = (f'<div style="display:flex;gap:10px;flex-shrink:0">'
                  f'{"".join(metric_cards)}</div>') if metric_cards else ""

    reading_block = ""
    if reading:
        reading_block = f"""
<div style="flex-shrink:0;border-top:1px solid {C['border']};padding-top:18px">
  <div style="font-size:14px;font-weight:700;color:{C['muted']};
              letter-spacing:0.12em;text-transform:uppercase;margin-bottom:10px">
    臨床での読み方
  </div>
  <div style="font-size:30px;font-weight:600;color:{C['slate']};
              line-height:1.5;border-left:4px solid {C['amber']};
              padding:12px 20px;background:{C['gray']};border-radius:0 12px 12px 0">
    {H_(reading)}
  </div>
</div>"""

    body = f"""
<div class="slide" style="background:{C['white']}">
  {_hdr(2, color)}
  {_rule()}

  <div style="flex:1;min-height:0;display:flex;flex-direction:column;
              padding:20px 60px 20px;gap:20px;overflow:hidden;
              justify-content:space-between">

    <div style="flex-shrink:0">
      <div style="font-size:13px;font-weight:700;letter-spacing:0.14em;
                  text-transform:uppercase;color:{color};margin-bottom:14px">
        Clinical Bottom Line
      </div>
      <div style="border-left:5px solid {color};padding:20px 26px;
                  background:{C['gray']};border-radius:0 14px 14px 0">
        <div style="font-size:{impact_size}px;font-weight:800;color:{C['navy']};
                    line-height:1.36">{H_(impact)}</div>
      </div>
    </div>

    {metric_row}

    {reading_block}

  </div>

  {_ftr(d, color)}
</div>"""
    _check_density(2, body)
    return page(body)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 3: BACKGROUND
# ─────────────────────────────────────────────────────────────────────────────
def s3_background(d):
    st    = d.get('study_type', 'RCT')
    color = ac(st)
    bg    = d.get('background', '')
    pop   = d.get('population', '')

    # Split background into problem + evidence gap
    sentences = [s.strip() for s in re.split(r'(?<=。)', bg) if s.strip()]
    problem_text  = sentences[0] if sentences else bg
    gap_text      = ''.join(sentences[1:]).strip() if len(sentences) > 1 else ''

    # Population items
    pop_items = [
        s.strip().lstrip('・').lstrip('-').strip()
        for s in re.split(r'[\n・]+', pop)
        if s.strip().lstrip('・').lstrip('-').strip()
    ]

    pop_grid = ""
    if pop_items:
        cells = ''.join(
            f'<div style="background:{C["sky"]};border-radius:10px;padding:12px 16px;'
            f'text-align:center;border:1px solid {C["ice"]}">'
            f'<div style="font-size:24px;font-weight:700;color:{C["navy_med"]};'
            f'line-height:1.3">{H_(item)}</div>'
            f'</div>'
            for item in pop_items[:4]
        )
        pop_grid = f"""
<div style="flex-shrink:0">
  <div style="font-size:14px;font-weight:700;color:{color};
              letter-spacing:0.12em;text-transform:uppercase;margin-bottom:12px">
    Study Population
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">{cells}</div>
</div>"""

    problem_block = f"""
<div style="flex-shrink:0;background:{C['white']};border-radius:14px;
            padding:20px 24px;border-left:4px solid {color}">
  <div style="font-size:13px;font-weight:700;color:{color};
              letter-spacing:0.12em;text-transform:uppercase;margin-bottom:10px">
    Clinical Problem
  </div>
  <div style="font-size:38px;color:{C['slate']};line-height:1.5;font-weight:500">
    {_md_bold(problem_text)}
  </div>
</div>"""

    gap_block = ""
    if gap_text:
        gap_block = f"""
<div style="flex-shrink:0;background:{C['white']};border-radius:14px;
            padding:20px 24px;border-left:4px solid {C['amber']}">
  <div style="font-size:13px;font-weight:700;color:{C['amber']};
              letter-spacing:0.12em;text-transform:uppercase;margin-bottom:10px">
    Evidence Gap
  </div>
  <div style="font-size:38px;color:{C['slate']};line-height:1.5;font-weight:500">
    {_md_bold(gap_text)}
  </div>
</div>"""

    body = f"""
<div class="slide" style="background:{C['gray']}">
  {_hdr(3, color)}
  {_rule()}

  <div style="padding:20px 60px 10px;flex-shrink:0">
    <div style="font-size:48px;font-weight:900;color:{color};line-height:1.1">Background</div>
    <div style="font-size:18px;font-weight:500;color:{C['muted']};margin-top:4px">
      なぜこの研究が必要だったか
    </div>
  </div>

  <div style="flex:1;min-height:0;display:flex;flex-direction:column;
              padding:0 60px 20px;gap:14px;overflow:hidden;
              justify-content:space-between">

    {problem_block}
    {gap_block}
    {pop_grid}

  </div>

  {_ftr(d, color)}
</div>"""
    _check_density(3, body)
    return page(body)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 4: PICO / METHODS
# ─────────────────────────────────────────────────────────────────────────────
def _flow_arrow_h():
    return (f'<div style="display:flex;justify-content:center;height:26px;'
            f'flex-shrink:0;align-items:center">'
            f'<div style="display:flex;flex-direction:column;align-items:center">'
            f'<div style="width:2px;height:14px;background:{C["border_md"]}"></div>'
            f'<div style="width:0;height:0;border-left:7px solid transparent;'
            f'border-right:7px solid transparent;'
            f'border-top:8px solid {C["border_md"]}"></div>'
            f'</div></div>')

def _pico_card(letter, label_text, value, color, bg, font=28, clamp=4):
    items = [s.strip().lstrip('・').lstrip('-').strip()
             for s in re.split(r'[\n・]+', value)
             if s.strip().lstrip('・').lstrip('-').strip()]

    if len(items) >= 2:
        content = ''.join(
            f'<div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:6px">'
            f'<div style="width:5px;height:5px;border-radius:50%;background:{color};'
            f'margin-top:{int(font*0.5)}px;flex-shrink:0"></div>'
            f'<div style="font-size:{font}px;color:{C["slate"]};line-height:1.45">'
            f'{H_(it)}</div></div>'
            for it in items[:5]
        )
    else:
        clamp_cls = f'style="display:-webkit-box;-webkit-line-clamp:{clamp};-webkit-box-orient:vertical;overflow:hidden"' if clamp else ''
        content = f'<div {clamp_cls} style="font-size:{font}px;color:{C["slate"]};line-height:1.5">{H_(value)}</div>'

    return f"""
<div style="display:flex;overflow:visible;border-radius:14px;flex-shrink:0">
  <div style="width:72px;min-width:72px;background:{color};display:flex;
              flex-direction:column;align-items:center;justify-content:center;
              gap:2px;padding:14px 0;border-radius:14px 0 0 14px">
    <span style="font-size:34px;font-weight:900;color:#fff;line-height:1">{letter}</span>
    <span style="font-size:9px;font-weight:700;color:rgba(255,255,255,.6);
                 letter-spacing:0.08em;writing-mode:vertical-lr;
                 transform:rotate(180deg)">{label_text}</span>
  </div>
  <div style="flex:1;background:{bg};padding:14px 20px;border-radius:0 14px 14px 0">
    {content}
  </div>
</div>"""

def s4_pico(d):
    st     = d.get('study_type', 'RCT')
    color  = ac(st)
    design = d.get('design', '')
    pop    = d.get('population', '')
    intv   = d.get('intervention', '')
    comp   = d.get('comparison', '')
    out    = d.get('outcome', '')

    COLORS = {'P': color, 'I': color, 'C': C['muted'], 'O': C['navy_med']}
    BGS    = {'P': C['white'], 'I': C['ice'], 'C': C['white'], 'O': C['white']}

    font = 27

    design_pill = ""
    if design:
        design_pill = (f'<span style="display:inline-block;background:{C["ice"]};'
                       f'color:{C["navy_med"]};font-size:14px;font-weight:700;'
                       f'padding:5px 14px;border-radius:6px;letter-spacing:0.04em">'
                       f'{H_(design)}</span>')

    rand_label = f"""
<div style="display:flex;justify-content:center;align-items:center;gap:10px;
            flex-shrink:0;padding:4px 0">
  <div style="height:1px;flex:1;background:{C['border_md']}"></div>
  <span style="font-size:14px;font-weight:700;color:{C['muted']};letter-spacing:0.1em;
               text-transform:uppercase;padding:4px 14px;background:{C['border']};
               border-radius:6px">Randomization</span>
  <div style="height:1px;flex:1;background:{C['border_md']}"></div>
</div>"""

    ic_block = ""
    if intv and comp:
        ic_block = f"""
<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;flex-shrink:0;align-items:start">
  {_pico_card('I', 'Intervention', intv, COLORS['I'], BGS['I'], font, clamp=None)}
  {_pico_card('C', 'Comparison',   comp, COLORS['C'], BGS['C'], font-4, clamp=None)}
</div>"""
    elif intv:
        ic_block = _pico_card('I', 'Intervention', intv, COLORS['I'], BGS['I'], font, clamp=None)
    elif comp:
        ic_block = _pico_card('C', 'Comparison', comp, COLORS['C'], BGS['C'], font, clamp=None)

    body = f"""
<div class="slide" style="background:{C['gray']}">
  {_hdr(4, color)}
  {_rule()}

  <div style="flex:1;min-height:0;display:flex;flex-direction:column;
              padding:18px 60px 18px;gap:0;overflow:hidden">

    <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-shrink:0">
      <span style="font-size:34px;font-weight:900;color:{color}">PICO / Methods</span>
      {design_pill}
    </div>

    <div style="flex:1;min-height:0;display:flex;flex-direction:column;
                justify-content:space-evenly;overflow:hidden;gap:4px">
      {_pico_card('P', 'Population', pop, COLORS['P'], BGS['P'], font)}
      {rand_label}
      {ic_block}
      {_flow_arrow_h()}
      {_pico_card('O', 'Outcome', out, COLORS['O'], BGS['O'], font)}
    </div>

  </div>

  {_ftr(d, color)}
</div>"""
    _check_density(4, body)
    return page(body)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 5: RESULTS
# ─────────────────────────────────────────────────────────────────────────────
def _svg_bars(sa, sb, sal, sbl, color):
    try:
        a = float(re.sub(r'[^0-9.]', '', sa))
        b = float(re.sub(r'[^0-9.]', '', sb))
    except Exception:
        return ""
    if a == 0 and b == 0:
        return ""
    mx = max(a, b) * 1.2
    bw = 620

    wa = int(a / mx * bw)
    wb = int(b / mx * bw)

    return f"""
<svg viewBox="0 0 780 220" xmlns="http://www.w3.org/2000/svg"
     style="width:100%;max-height:220px;flex-shrink:0;display:block">
  <text x="0" y="24" fill="{color}" font-size="20" font-weight="700"
        font-family="'Hiragino Sans','Noto Sans JP',sans-serif">{H_(sal)}</text>
  <rect x="0" y="32" width="{wa}" height="56" rx="8" fill="{color}"/>
  <text x="{wa+14}" y="72" fill="{color}" font-size="32" font-weight="800"
        font-family="'Helvetica Neue','Arial',sans-serif">{H_(sa)}</text>

  <text x="0" y="136" fill="{C['muted']}" font-size="20" font-weight="700"
        font-family="'Hiragino Sans','Noto Sans JP',sans-serif">{H_(sbl)}</text>
  <rect x="0" y="144" width="{wb}" height="56" rx="8" fill="{C['border_md']}"/>
  <text x="{wb+14}" y="184" fill="{C['muted']}" font-size="32" font-weight="800"
        font-family="'Helvetica Neue','Arial',sans-serif">{H_(sb)}</text>
</svg>"""

def s5_results(d):
    st    = d.get('study_type', 'RCT')
    color = ac(st)
    sa_   = d.get('stat_a', '')
    sb_   = d.get('stat_b', '')
    sal   = d.get('stat_a_label', '介入群')
    sbl   = d.get('stat_b_label', '対照群')
    ctx   = d.get('stat_context', '')
    stats = d.get('stats', [])
    sec   = d.get('secondary_results', '')
    kf    = d.get('key_finding', '')
    impact = d.get('impact_comment', '')

    if isinstance(stats, str):
        stats = [s.strip() for s in stats.split('\n') if s.strip()]

    nnt_m = re.search(r'NNT\s*[=＝]\s*(\d+)', kf + impact + ' '.join(stats))
    arr_m = re.search(r'ARR\s*(-?[\d.]+\s*%)', kf + impact)
    hr_m  = re.search(r'HR\s+([\d.]+)\s*\(([^)]+)\)', ' '.join(stats))
    p_m   = re.search(r'p\s*[=<]\s*([\d.]+)', ' '.join(stats))

    nnt = nnt_m.group(1) if nnt_m else ''
    arr = arr_m.group(1).replace(' ', '') if arr_m else ''
    hr_val = hr_m.group(1) if hr_m else ''
    hr_ci  = hr_m.group(2) if hr_m else ''
    p_val  = p_m.group(1) if p_m else ''

    # Hero row: ARR + NNT
    hero_cards = []
    if arr:
        hero_cards.append(
            f'<div style="flex:1;background:{C["ice"]};border-radius:16px;'
            f'padding:20px 24px;border:1px solid {C["border"]}">'
            f'<div style="font-size:14px;font-weight:700;color:{C["muted"]};'
            f'letter-spacing:0.12em;text-transform:uppercase;margin-bottom:8px">絶対リスク差 ARR</div>'
            f'<div class="num" style="font-size:72px;font-weight:900;color:{color};'
            f'line-height:0.95">{H_(arr)}</div>'
            f'<div style="font-size:18px;font-weight:600;color:{C["muted"]};margin-top:8px">'
            f'{H_(ctx) if ctx else "主要アウトカム"}</div>'
            f'</div>'
        )
    if nnt:
        hero_cards.append(
            f'<div style="flex:1;background:{color};border-radius:16px;'
            f'padding:20px 24px">'
            f'<div style="font-size:14px;font-weight:700;color:rgba(255,255,255,.65);'
            f'letter-spacing:0.12em;text-transform:uppercase;margin-bottom:8px">治療必要数 NNT</div>'
            f'<div class="num" style="font-size:72px;font-weight:900;color:#fff;'
            f'line-height:0.95">{H_(nnt)}</div>'
            f'<div style="font-size:18px;font-weight:600;color:rgba(255,255,255,.7);'
            f'margin-top:8px">1名を救うために要する治療数</div>'
            f'</div>'
        )
    hero_row = (f'<div style="display:flex;gap:12px;flex-shrink:0">'
                f'{"".join(hero_cards)}</div>') if hero_cards else ""

    svg = _svg_bars(sa_, sb_, sal, sbl, color) if sa_ and sb_ else ""

    bars_block = ""
    if svg:
        bars_block = f"""
<div style="flex-shrink:0">
  <div style="font-size:15px;font-weight:700;color:{C['muted']};
              letter-spacing:0.1em;text-transform:uppercase;margin-bottom:10px">
    {H_(ctx) if ctx else '比較'}
  </div>
  {svg}
</div>"""

    # HR + p secondary stats
    secondary_stats = []
    if hr_val:
        secondary_stats.append(
            f'<div style="flex:2;background:{C["gray"]};border-radius:12px;'
            f'padding:16px 20px;border:1px solid {C["border"]}">'
            f'<div style="font-size:13px;font-weight:700;color:{C["muted"]};'
            f'letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px">HR (95%CI)</div>'
            f'<div class="num" style="font-size:36px;font-weight:900;color:{C["slate"]};'
            f'line-height:1.1">{H_(hr_val)}</div>'
            f'<div style="font-size:18px;color:{C["muted"]};margin-top:6px">'
            f'({H_(hr_ci)})</div>'
            f'</div>'
        )
    if p_val:
        secondary_stats.append(
            f'<div style="flex:1;background:{C["gray"]};border-radius:12px;'
            f'padding:16px 20px;border:1px solid {C["border"]};text-align:center">'
            f'<div style="font-size:13px;font-weight:700;color:{C["muted"]};'
            f'letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px">P値</div>'
            f'<div class="num" style="font-size:42px;font-weight:900;color:{C["slate"]};'
            f'line-height:1">{H_(p_val)}</div>'
            f'</div>'
        )
    stats_row = (f'<div style="display:flex;gap:10px;flex-shrink:0">'
                 f'{"".join(secondary_stats)}</div>') if secondary_stats else ""

    sec_block = ""
    if sec:
        sec_block = f"""
<div style="flex-shrink:0;border-top:1px solid {C['border']};padding-top:14px">
  <div style="font-size:13px;font-weight:700;color:{C['muted']};
              letter-spacing:0.1em;text-transform:uppercase;margin-bottom:8px">
    Secondary Outcomes
  </div>
  <div style="font-size:27px;color:{C['slate']};line-height:1.55;font-weight:500">
    {H_(sec)}
  </div>
</div>"""

    body = f"""
<div class="slide" style="background:{C['white']}">
  {_hdr(5, color)}
  {_rule()}

  <div style="flex:1;min-height:0;display:flex;flex-direction:column;
              padding:20px 60px 16px;gap:14px;overflow:hidden;
              justify-content:space-between">

    <div style="flex-shrink:0">
      <div style="font-size:40px;font-weight:900;color:{color}">Results</div>
    </div>

    {hero_row}
    {bars_block}
    {stats_row}
    {sec_block}

  </div>

  {_ftr(d, color)}
</div>"""
    _check_density(5, body)
    return page(body)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 6: CRITICAL APPRAISAL
# ─────────────────────────────────────────────────────────────────────────────
def _parse_limitations(lims):
    lines = [l.strip() for l in lims.split('\n') if l.strip()]
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i].lstrip('-').strip()
        if not line:
            i += 1
            continue

        is_heading = (len(line) <= 16 and not line.endswith('。') and
                      not line.startswith('→'))
        if is_heading:
            heading = line
            i += 1
            problem = ''
            interp  = ''
            if i < len(lines) and not lines[i].startswith('→'):
                problem = lines[i].lstrip('-').strip()
                i += 1
            if i < len(lines) and lines[i].startswith('→'):
                interp = lines[i][1:].strip().strip('"').strip()
                i += 1
            blocks.append({'heading': heading, 'problem': problem, 'interp': interp})
        else:
            problem = line
            interp  = ''
            i += 1
            if i < len(lines) and lines[i].startswith('→'):
                interp = lines[i][1:].strip().strip('"').strip()
                i += 1
            m = re.split(r'[でがのはにおけるとも（、]', problem, maxsplit=1)
            heading = m[0].rstrip('、').strip() if len(m) > 1 and len(m[0]) <= 14 else f"Limitation {len(blocks)+1:02d}"
            blocks.append({'heading': heading, 'problem': problem, 'interp': interp})

    return blocks

def s6_stats(d):
    st    = d.get('study_type', 'RCT')
    color = ac(st)
    lims  = d.get('limitations', '')
    pri   = d.get('primary_result', '')

    lim_blocks = _parse_limitations(lims)

    def _lim_card(n, heading, problem, interp):
        interp_html = ""
        if interp:
            interp_html = (
                f'<div style="margin-top:10px;padding-top:10px;'
                f'border-top:1px solid {C["border"]};display:flex;'
                f'align-items:flex-start;gap:8px">'
                f'<span style="font-size:18px;font-weight:900;color:{C["amber"]};'
                f'flex-shrink:0;margin-top:2px">→</span>'
                f'<div style="font-size:24px;color:{C["slate"]};line-height:1.45;'
                f'font-weight:500">{H_(interp)}</div>'
                f'</div>'
            )
        return f"""
<div style="background:{C['gray']};border-radius:14px;padding:20px 24px;
            border-left:4px solid {C['amber']};flex-shrink:0">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
    <span style="font-size:26px;font-weight:900;color:{C['amber']};
                 line-height:1;flex-shrink:0">{n:02d}</span>
    <span style="font-size:20px;font-weight:800;color:{C['navy']}">{H_(heading)}</span>
  </div>
  <div style="font-size:26px;color:{C['slate']};line-height:1.5;font-weight:500">
    {H_(problem)}
  </div>
  {interp_html}
</div>"""

    cards_html = ''.join(
        _lim_card(i+1, b['heading'], b['problem'], b['interp'])
        for i, b in enumerate(lim_blocks[:3])
    )
    if not cards_html:
        cards_html = f'<div style="font-size:26px;color:{C["muted"]}">Limitations not reported.</div>'

    pri_block = ""
    if pri:
        pri_block = f"""
<div style="flex-shrink:0;background:{C['sky']};border-radius:12px;
            border-left:4px solid {color};padding:14px 20px">
  <div style="font-size:13px;font-weight:700;color:{color};
              letter-spacing:0.1em;text-transform:uppercase;margin-bottom:6px">
    Primary Result
  </div>
  <div style="font-size:23px;color:{C['slate']};line-height:1.5">{H_(pri)}</div>
</div>"""

    body = f"""
<div class="slide" style="background:{C['white']}">
  {_hdr(6, color)}
  {_rule()}

  <div style="flex:1;min-height:0;display:flex;flex-direction:column;
              padding:20px 60px 16px;gap:14px;overflow:hidden;
              justify-content:space-between">

    <div style="flex-shrink:0">
      <div style="font-size:40px;font-weight:900;color:{C['navy']}">Critical Appraisal</div>
      <div style="font-size:18px;font-weight:500;color:{C['muted']};margin-top:4px">
        研究の限界と臨床解釈
      </div>
    </div>

    {_rule()}

    {cards_html}

    {pri_block}

  </div>
  {_ftr(d, color)}
</div>"""
    _check_density(6, body)
    return page(body)


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 7: TAKE HOME
# ─────────────────────────────────────────────────────────────────────────────
def s7_takehome(d):
    st    = d.get('study_type', 'RCT')
    color = ac(st)
    take  = d.get('take_home', '')
    cit   = d.get('citation', '')
    note  = d.get('take_home_note', '')

    raw = [
        s.strip().lstrip('-').lstrip('・').strip()
        for s in take.split('\n')
        if s.strip().lstrip('-').lstrip('・').strip()
    ]
    main_take  = raw[0] if raw else take
    action_pts = raw[1:4]

    main_size = _fit(main_take, base=48, min_size=32)

    action_items_html = ""
    if action_pts:
        items = ''.join(
            f'<div style="display:flex;align-items:flex-start;gap:16px;'
            f'padding:16px 20px;background:{C["white"]};border-radius:12px;'
            f'flex-shrink:0">'
            f'<div style="font-size:16px;font-weight:900;color:{color};'
            f'flex-shrink:0;min-width:22px;padding-top:4px">{i+1}</div>'
            f'<div style="font-size:29px;color:{C["slate"]};line-height:1.5;'
            f'font-weight:500">{H_(pt)}</div>'
            f'</div>'
            for i, pt in enumerate(action_pts)
        )
        action_items_html = f"""
<div style="flex-shrink:0">
  <div style="font-size:13px;font-weight:700;color:{C['muted']};
              letter-spacing:0.12em;text-transform:uppercase;margin-bottom:10px">
    How to Apply
  </div>
  <div style="display:flex;flex-direction:column;gap:8px">{items}</div>
</div>"""

    note_html = ""
    if note:
        note_html = f"""
<div style="flex-shrink:0;border-top:1px solid {C['border_md']};padding-top:12px">
  <div style="font-size:22px;color:{C['muted']};line-height:1.5;
              font-style:italic">{H_(note)}</div>
</div>"""

    cit_html = ""
    if cit:
        cit_html = f'<div style="font-size:16px;color:{C["muted"]};line-height:1.4">{H_(cit)}</div>'

    body = f"""
<div class="slide" style="background:{C['sky']}">
  {_hdr(7, color)}
  {_rule()}

  <div style="flex:1;min-height:0;display:flex;flex-direction:column;
              padding:22px 60px 16px;gap:18px;overflow:hidden;
              justify-content:space-between">

    <div style="flex-shrink:0">
      <div style="font-size:40px;font-weight:900;color:{color}">Take Home</div>
    </div>

    <div style="background:{C['white']};border-radius:18px;
                border-left:6px solid {color};padding:22px 28px;
                flex-shrink:0">
      <div style="font-size:{main_size}px;font-weight:800;color:{C['navy']};
                  line-height:1.35">{H_(main_take)}</div>
    </div>

    {action_items_html}

    <div style="flex-shrink:0">
      {cit_html}
      {note_html}
    </div>

  </div>

  {_ftr(d, color)}
</div>"""
    _check_density(7, body)
    return page(body)


# ─────────────────────────────────────────────────────────────────────────────
# Infrastructure
# ─────────────────────────────────────────────────────────────────────────────
def _norm(data):
    d = dict(data)
    for f in ["population","limitations","background","intervention","comparison",
              "outcome","primary_result","secondary_results","take_home",
              "key_finding","title_jp","title_en","impact_comment",
              "clinical_reading","take_home_note"]:
        v = d.get(f, "")
        if isinstance(v, list):      d[f] = "\n".join(str(x) for x in v)
        elif not isinstance(v, str): d[f] = str(v) if v else ""
    return d

def screenshot(html_str, path):
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage'])
        pg = browser.new_page(viewport={"width": W, "height": H})
        pg.set_content(html_str, wait_until="domcontentloaded")
        pg.wait_for_timeout(400)
        pg.screenshot(path=str(path), clip={"x": 0, "y": 0, "width": W, "height": H})
        browser.close()

def generate_carousel(data, output_dir="output"):
    if not HAS_PLAYWRIGHT:
        raise RuntimeError("pip install playwright && playwright install chromium")
    data  = _norm(data)
    out   = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    pmid  = data.get("pmid", "unknown")
    fns   = [s1_hook, s2_keyfinding, s3_background, s4_pico,
             s5_results, s6_stats, s7_takehome]
    paths = []
    for i, fn in enumerate(fns, 1):
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
        "pmid": "v16test", "study_type": "RCT",
        "journal": "NEJM", "year": "2025",
        "title_jp": "小児敗血症性ショックに対する早期バソプレシン投与の有効性：多施設無作為化比較試験",
        "research_question": "ノルアドレナリン抵抗性の小児敗血症性ショックにおいて、バソプレシンの早期追加は28日死亡率を改善するか？",
        "key_finding": "28日死亡率が有意に低下（18.2% vs 26.7%, ARR -8.5%, NNT=12）",
        "impact_comment": "NNT=12。小児敗血症性ショックの初期循環管理を変えうる可能性がある。ただし欧州単施設データであり、アジアPICUへの外挿には慎重な解釈が必要。",
        "clinical_reading": "ノルアド反応不良の血管拡張性ショックに対する追加薬として位置づける。",
        "background": "小児敗血症性ショックでは、**カテコラミン抵抗性**の血管拡張が予後不良と関連する。成人ではバソプレシン併用が検討されているが、小児での大規模RCTは乏しかった。この空白が本研究の動機となった。",
        "population": "・生後1か月–17歳\n・敗血症性ショック患児\n・n=1,200\n・28施設PICU",
        "intervention": "ノルアドレナリン開始後6時間以内にバソプレシン 0.0003–0.002 U/kg/min を追加",
        "comparison": "生理食塩水（プラセボ）を追加",
        "outcome": "主要：28日全死亡率 / 副次：臓器障害日数、カテコラミン使用期間",
        "design": "Multicenter double-blind RCT",
        "primary_result": "28日死亡率：バソプレシン群 18.2% vs プラセボ群 26.7%、ARR -8.5%（95%CI: -13.1〜-3.9%, p=0.002）。NNT=12。",
        "stat_a": "18.2%", "stat_a_label": "バソプレシン群",
        "stat_b": "26.7%", "stat_b_label": "プラセボ群", "stat_context": "28日死亡率",
        "stats": ["HR 0.68 (95%CI 0.52–0.89)", "p = 0.002", "NNT = 12"],
        "secondary_results": "ICU滞在期間中央値：8日 vs 11日（p=0.03）。カテコラミン使用期間も有意に短縮。",
        "limitations": "外的妥当性\n欧州中心の試験で、アジア・日本PICUの患者背景とは異なる可能性がある\n→ 国内での導入は対象患者と安全監視を明確にする\n投与タイミング\n「6時間以内」の範囲内で、最適な開始時点は個別化されていない\n→ いつ足すかは循環動態と反応性で判断する\n長期アウトカム\n長期神経発達予後や開放ラベル使用の影響は十分に評価されていない\n→ 生存利益と長期予後は分けて解釈する",
        "take_home": "ノルアドレナリン開始後も血管拡張性ショックが遷延する小児では、6時間以内のバソプレシン併用を検討する。\n・ノルアド反応不良の血管拡張性ショックで適応を検討\n・低Na血症・末梢虚血・冠攣縮を監視しながら投与\n・日本PICUでは導入前に対象患者と安全監視を明確化",
        "take_home_note": "外的妥当性と最適な開始基準には未解決点が残る。",
        "citation": "Smith J, et al. N Engl J Med. 2025;392:1234-1245.",
    }
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "output_v16"
    generate_carousel(sample, out_dir)
