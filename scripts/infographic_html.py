#!/usr/bin/env python3
"""
PICU Evidence Daily — Infographic Generator v7
設計思想: ゼロ余白 / 大活字 / フルカラーブロック / インスタ最適化
Playwright + headless Chromium
"""

import base64, html as _html, io, re
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

try:
    import matplotlib, matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    matplotlib.use('Agg')
    _JP      = FontProperties(fname='/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc')
    _JP_BOLD = FontProperties(fname='/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc')
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

W, H, N = 1080, 1350, 7

STUDY_ACCENT = {
    "RCT":               ("#7F1D1D", "#DC2626", "#FEE2E2"),
    "Systematic Review": ("#3B0764", "#7C3AED", "#EDE9FE"),
    "Meta-Analysis":     ("#3B0764", "#7C3AED", "#EDE9FE"),
    "Cohort Study":      ("#064E3B", "#059669", "#D1FAE5"),
    "Guideline":         ("#1E3A8A", "#2563EB", "#DBEAFE"),
    "Review":            ("#3B0764", "#7C3AED", "#EDE9FE"),
    "Case Series":       ("#064E3B", "#059669", "#D1FAE5"),
}
def sa(st):
    return STUDY_ACCENT.get(st, ("#78350F", "#D97706", "#FEF3C7"))

H_ = _html.escape

BASE = """
* { box-sizing: border-box; margin: 0; padding: 0; }
html {
    width: 1080px; height: 1350px;
    font-family: 'Hiragino Sans', 'Hiragino Kaku Gothic ProN', -apple-system, sans-serif;
    -webkit-font-smoothing: antialiased;
}
body { width: 1080px; height: 1350px; overflow: hidden; }
.slide { width: 1080px; height: 1350px; display: flex; flex-direction: column; overflow: hidden; position: relative; }
.hdr {
    display: flex; align-items: center; justify-content: space-between;
    padding: 22px 48px 0; flex-shrink: 0; position: relative; z-index: 2;
}
.hdr-brand { font-size: 20px; font-weight: 700; letter-spacing: .02em; }
.hdr-count { font-size: 17px; opacity: .7; }
.strip {
    height: 72px; display: flex; align-items: center; justify-content: center;
    flex-shrink: 0; font-size: 17px; font-weight: 700; letter-spacing: .04em;
    position: relative; z-index: 2;
}
.badge {
    display: inline-flex; align-items: center; padding: 6px 18px;
    border-radius: 8px; font-size: 19px; font-weight: 900; flex-shrink: 0;
}
.clamp2  { display: -webkit-box; -webkit-line-clamp: 2;  -webkit-box-orient: vertical; overflow: hidden; }
.clamp3  { display: -webkit-box; -webkit-line-clamp: 3;  -webkit-box-orient: vertical; overflow: hidden; }
.clamp4  { display: -webkit-box; -webkit-line-clamp: 4;  -webkit-box-orient: vertical; overflow: hidden; }
.clamp5  { display: -webkit-box; -webkit-line-clamp: 5;  -webkit-box-orient: vertical; overflow: hidden; }
.clamp6  { display: -webkit-box; -webkit-line-clamp: 6;  -webkit-box-orient: vertical; overflow: hidden; }
.clamp8  { display: -webkit-box; -webkit-line-clamp: 8;  -webkit-box-orient: vertical; overflow: hidden; }
.clamp10 { display: -webkit-box; -webkit-line-clamp: 10; -webkit-box-orient: vertical; overflow: hidden; }
.clamp12 { display: -webkit-box; -webkit-line-clamp: 12; -webkit-box-orient: vertical; overflow: hidden; }
"""

def page(body: str, extra: str = "") -> str:
    return f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{BASE}{extra}</style></head><body>{body}</body></html>"

def info_strip(d, bg="#1E3A8A", fg="#AACCFF"):
    j, y, s = H_(d.get('journal','')), H_(d.get('year','')), H_(d.get('study_type',''))
    return f'<div class="strip" style="background:{bg};color:{fg}">📰 {j} &nbsp;·&nbsp; {y} &nbsp;·&nbsp; {s}</div>'

def hdr_dark(num, col="rgba(255,255,255,0.85)"):
    return f'''<div class="hdr">
  <span class="hdr-brand" style="color:{col}">PICU Evidence Daily</span>
  <span class="hdr-count" style="color:{col}">{num} / {N}</span>
</div>'''

def hdr_light(num, col="#1E40AF"):
    return f'''<div style="height:8px;background:{col};flex-shrink:0"></div>
<div class="hdr" style="flex-shrink:0">
  <span class="hdr-brand" style="color:{col}">PICU Evidence Daily</span>
  <span class="hdr-count" style="color:#64748B">{num} / {N}</span>
</div>
<div style="height:1px;background:#E2E8F0;margin:12px 48px 0;flex-shrink:0"></div>'''

# ─── matplotlib chart → base64 ────────────────────────────────────────────
def chart_b64(va, vb, la, lb, ctx, w=984, h=380):
    if not HAS_MPL: return None
    def p(s):
        try: return float(str(s).replace('%','').replace('％','').strip())
        except: return None
    a, b = p(va), p(vb)
    if a is None or b is None: return None
    fig, ax = plt.subplots(figsize=(w/100, h/100), dpi=100)
    fig.patch.set_facecolor('#0F172A')
    ax.set_facecolor('#0F172A')
    labs   = [lb or 'Control', la or 'Intervention']
    vals   = [b, a]
    clrs   = [(0.22, 0.48, 0.94), (0.86, 0.15, 0.15)]
    bars   = ax.barh(labs, vals, color=clrs, height=0.55, edgecolor='#0F172A', linewidth=2)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_width() + max(a,b)*0.03,
                bar.get_y() + bar.get_height()/2,
                f'{val:.1f}%', va='center', ha='left',
                fontproperties=_JP_BOLD, fontsize=26, color='white', fontweight='bold')
    if ctx:
        ax.set_title(ctx, fontproperties=_JP_BOLD, fontsize=19, color='white', pad=16)
    ax.set_xlim(0, max(a,b)*1.42)
    ax.tick_params(axis='y', labelsize=22, colors='white')
    ax.tick_params(axis='x', labelsize=14, colors='#64748B')
    for tick in ax.get_yticklabels(): tick.set_fontproperties(_JP)
    for sp in ['top','right','left','bottom']:
        ax.spines[sp].set_color('#334155')
    ax.grid(axis='x', color='#334155', linestyle='--', linewidth=0.8)
    buf = io.BytesIO()
    plt.tight_layout(pad=0.4)
    fig.savefig(buf, format='PNG', dpi=100, bbox_inches='tight', facecolor='#0F172A')
    buf.seek(0); b64 = base64.b64encode(buf.read()).decode()
    plt.close(fig); return b64

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 1: HOOK  ダークネイビー全面 / KEY FINDING ヒーロー
# ─────────────────────────────────────────────────────────────────────────────
def s1_hook(d):
    st = d.get('study_type','RCT'); dark, mid, light = sa(st)
    sa_ = d.get('stat_a',''); sb_ = d.get('stat_b','')
    sal = H_(d.get('stat_a_label','介入群')); sbl = H_(d.get('stat_b_label','対照群'))
    ctx = H_(d.get('stat_context',''))

    compare = ""
    if sa_ and sb_:
        compare = f"""
<div style="flex-shrink:0">
  <div style="font-size:16px;font-weight:700;color:rgba(255,255,255,.6);
              text-align:center;margin-bottom:10px;letter-spacing:.06em">{ctx}</div>
  <div style="display:flex;gap:12px">
    <div style="flex:1;background:rgba(220,38,38,.25);border:2px solid #EF4444;
                border-radius:16px;display:flex;flex-direction:column;
                align-items:center;justify-content:center;padding:18px 8px">
      <span style="font-size:82px;font-weight:900;color:#FCA5A5;line-height:1">{H_(sa_)}</span>
      <span style="font-size:17px;font-weight:700;color:#FCA5A5;margin-top:8px">{sal}</span>
    </div>
    <div style="width:36px;display:flex;align-items:center;justify-content:center;
                font-size:20px;font-weight:700;color:rgba(255,255,255,.4)">vs</div>
    <div style="flex:1;background:rgba(37,99,235,.25);border:2px solid #60A5FA;
                border-radius:16px;display:flex;flex-direction:column;
                align-items:center;justify-content:center;padding:18px 8px">
      <span style="font-size:82px;font-weight:900;color:#93C5FD;line-height:1">{H_(sb_)}</span>
      <span style="font-size:17px;font-weight:700;color:#93C5FD;margin-top:8px">{sbl}</span>
    </div>
  </div>
</div>"""

    stats = d.get('stats',[])
    stat_row = ""
    if stats:
        cols = ["#FCD34D","#6EE7B7","#93C5FD"]
        items = "".join(
            f'<div style="flex:1;text-align:center;padding:12px 6px;'
            f'background:rgba(255,255,255,.06);border-radius:10px;'
            f'font-size:17px;font-weight:700;color:{cols[i%3]};line-height:1.4">{H_(s)}</div>'
            for i, s in enumerate(stats[:3]))
        stat_row = f'<div style="display:flex;gap:10px;flex-shrink:0">{items}</div>'

    body = f"""
<div class="slide" style="background:linear-gradient(150deg,#0F172A 0%,#1E3A8A 60%,#1E1B4B 100%)">
  <div style="position:absolute;width:560px;height:560px;border-radius:50%;
              background:rgba(37,99,235,.18);top:-160px;right:-100px"></div>
  <div style="position:absolute;width:400px;height:400px;border-radius:50%;
              background:rgba(30,27,75,.5);bottom:-120px;left:-100px"></div>

  {hdr_dark(1)}
  <div style="flex:1;display:flex;flex-direction:column;padding:18px 48px 18px;
              gap:14px;overflow:hidden;min-height:0;position:relative;z-index:2">
    <div style="display:flex;align-items:center;gap:12px;flex-shrink:0">
      <span class="badge" style="background:{mid};color:#FFF">{H_(st)}</span>
      <span style="font-size:17px;color:rgba(255,255,255,.55)">
        {H_(d.get('journal',''))} &nbsp;·&nbsp; {H_(d.get('year',''))}
      </span>
    </div>
    <div style="height:1px;background:rgba(255,255,255,.15);flex-shrink:0"></div>
    <div style="font-size:13px;font-weight:800;color:{mid};flex-shrink:0;
                letter-spacing:.15em;opacity:.9">KEY &nbsp; FINDING</div>
    <div style="font-size:38px;font-weight:900;color:#FFFFFF;line-height:1.4;
                flex-shrink:0" class="clamp4">
      {H_(d.get('key_finding',''))}
    </div>
    <div style="height:1px;background:rgba(255,255,255,.15);flex-shrink:0"></div>
    {compare}
    {stat_row}
    <div style="flex:1;min-height:0;display:flex;flex-direction:column;justify-content:flex-end">
      <div style="font-size:24px;font-weight:700;color:rgba(255,255,255,.75);
                  line-height:1.35" class="clamp3">
        {H_(d.get('title_jp',''))}
      </div>
      <div style="font-size:15px;color:rgba(255,255,255,.35);margin-top:6px;
                  line-height:1.4" class="clamp2">
        {H_(d.get('title_en',''))}
      </div>
    </div>
    <div style="text-align:center;font-size:16px;font-weight:700;
                color:rgba(255,255,255,.6);padding:10px 0;
                border-top:1px solid rgba(255,255,255,.12);flex-shrink:0">
      スライドをスワイプして詳細を見る &nbsp;▶
    </div>
  </div>
  {info_strip(d, '#0A0F1E', 'rgba(170,204,255,.7)')}
</div>"""
    return page(body)

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 2: KEY FINDING  スタディタイプ色全面 / 大テキスト + 統計パネル
# ─────────────────────────────────────────────────────────────────────────────
def s2_keyfinding(d):
    st = d.get('study_type','RCT'); dark, mid, light = sa(st)
    kf = H_(d.get('key_finding',''))
    jtext = f"{H_(d.get('journal',''))} &nbsp;·&nbsp; {H_(d.get('year',''))} &nbsp;·&nbsp; {H_(d.get('design',''))}"
    sa_ = d.get('stat_a',''); sb_ = d.get('stat_b','')
    sal = H_(d.get('stat_a_label','介入群')); sbl = H_(d.get('stat_b_label','対照群'))

    # 下部の統計比較パネル (固定 310px)
    has_stats = bool(sa_ and sb_)
    stat_panel = ""
    if has_stats:
        stat_panel = f"""
<div style="height:310px;display:flex;flex-shrink:0;gap:4px;position:relative;z-index:2">
  <div style="flex:1;background:rgba(220,38,38,.35);border-top:3px solid rgba(255,255,255,.2);
              display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px">
    <span style="font-size:100px;font-weight:900;color:#FFFFFF;line-height:1">{H_(sa_)}</span>
    <span style="font-size:20px;font-weight:700;color:rgba(255,255,255,.75)">{sal}</span>
  </div>
  <div style="width:50px;display:flex;align-items:center;justify-content:center;
              font-size:24px;font-weight:900;color:rgba(255,255,255,.4);
              background:rgba(0,0,0,.15)">vs</div>
  <div style="flex:1;background:rgba(255,255,255,.08);border-top:3px solid rgba(255,255,255,.15);
              display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px">
    <span style="font-size:100px;font-weight:900;color:rgba(255,255,255,.55);line-height:1">{H_(sb_)}</span>
    <span style="font-size:20px;font-weight:700;color:rgba(255,255,255,.45)">{sbl}</span>
  </div>
</div>"""

    body = f"""
<div class="slide" style="background:{dark}">
  <div style="position:absolute;font-size:520px;font-weight:900;color:rgba(255,255,255,.04);
              top:-100px;left:-15px;line-height:1;pointer-events:none;user-select:none">"</div>

  {hdr_dark(2)}

  <!-- テキストエリア: flex:1 で残り高さを全て使用 -->
  <div style="flex:1;display:flex;flex-direction:column;padding:24px 48px 0;
              position:relative;z-index:2;overflow:hidden;min-height:0">

    <!-- バッジ + ジャーナル行 (上端固定) -->
    <div style="display:flex;align-items:center;gap:12px;flex-shrink:0">
      <span class="badge" style="background:{mid};color:#FFF">{H_(st)}</span>
      <span style="font-size:16px;color:rgba(255,255,255,.5)">{jtext}</span>
    </div>

    <!-- スペーサー: バッジとKEY FINDINGの間を押し広げる -->
    <div style="flex:1;min-height:20px"></div>

    <!-- KEY FINDING ラベル -->
    <div style="font-size:15px;font-weight:800;color:{mid};letter-spacing:.14em;
                flex-shrink:0;margin-bottom:16px">KEY &nbsp; FINDING</div>

    <!-- ヒーローテキスト (大活字) -->
    <div style="font-size:72px;font-weight:900;color:#FFFFFF;line-height:1.38;
                flex-shrink:0" class="clamp5">
      {kf}
    </div>

    <!-- 区切り + 論文タイトル (下端固定) -->
    <div style="flex-shrink:0;border-top:1px solid rgba(255,255,255,.15);
                padding:14px 0 20px;margin-top:20px">
      <div style="font-size:20px;font-weight:700;color:rgba(255,255,255,.65);
                  line-height:1.4" class="clamp2">
        {H_(d.get('title_jp',''))}
      </div>
    </div>
  </div>

  {stat_panel}
  {info_strip(d, 'rgba(0,0,0,.4)', 'rgba(255,255,255,.6)')}
</div>"""
    return page(body)

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 3: BACKGROUND + POPULATION  大活字 2パネル
# ─────────────────────────────────────────────────────────────────────────────
def s3_background(d):
    bg_text = H_(d.get('background',''))
    pop     = H_(d.get('population',''))

    if pop:
        panels = f"""
<div style="flex:0.55;background:#0F172A;display:flex;flex-direction:column;
            padding:32px 48px 24px;overflow:hidden;min-height:0;position:relative">
  <div style="position:absolute;font-size:280px;font-weight:900;color:rgba(59,130,246,.06);
              right:-20px;top:-40px;line-height:1;pointer-events:none">📚</div>
  <div style="font-size:13px;font-weight:800;color:#3B82F6;letter-spacing:.14em;
              margin-bottom:18px;flex-shrink:0">BACKGROUND</div>
  <!-- テキストを縦中央揃えにして余白を均等分散 -->
  <div style="flex:1;min-height:0;display:flex;flex-direction:column;justify-content:center">
    <div style="font-size:36px;color:rgba(255,255,255,.9);line-height:1.65" class="clamp8">
      {bg_text}
    </div>
  </div>
</div>
<div style="height:4px;background:linear-gradient(90deg,#1E40AF,#7C3AED);flex-shrink:0"></div>
<div style="flex:0.45;background:#1E3A8A;display:flex;flex-direction:column;
            padding:28px 48px 24px;overflow:hidden;min-height:0;position:relative">
  <div style="position:absolute;font-size:220px;font-weight:900;color:rgba(96,165,250,.06);
              right:-10px;bottom:-40px;line-height:1;pointer-events:none">👥</div>
  <div style="font-size:13px;font-weight:800;color:#60A5FA;letter-spacing:.14em;
              margin-bottom:18px;flex-shrink:0">対象患者 &nbsp;/&nbsp; POPULATION</div>
  <!-- 44px大活字 + 縦中央揃え -->
  <div style="flex:1;min-height:0;display:flex;flex-direction:column;justify-content:center">
    <div style="font-size:44px;color:rgba(255,255,255,.9);line-height:1.6;
                font-weight:700" class="clamp6">
      {pop}
    </div>
  </div>
</div>"""
    else:
        panels = f"""
<div style="flex:1;background:#0F172A;display:flex;flex-direction:column;
            padding:32px 48px 24px;overflow:hidden;min-height:0">
  <div style="font-size:13px;font-weight:800;color:#3B82F6;letter-spacing:.14em;
              margin-bottom:18px;flex-shrink:0">BACKGROUND</div>
  <div style="flex:1;min-height:0;display:flex;flex-direction:column;justify-content:center">
    <div style="font-size:42px;color:rgba(255,255,255,.9);line-height:1.65" class="clamp12">
      {bg_text}
    </div>
  </div>
</div>"""

    body = f"""
<div class="slide" style="flex-direction:column">
  <div style="background:#0F172A;flex-shrink:0">
    {hdr_dark(3)}
  </div>
  <div style="background:#1E3A8A;padding:18px 48px 20px;flex-shrink:0">
    <div style="font-size:44px;font-weight:900;color:#FFFFFF;line-height:1">なぜこの研究？</div>
  </div>
  <div style="flex:1;display:flex;flex-direction:column;overflow:hidden;min-height:0">
    {panels}
  </div>
  {info_strip(d, '#0A0F1E', 'rgba(170,204,255,.7)')}
</div>"""
    return page(body)

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 4: PICO  カラーストライプ4段 / 余白ゼロ
# ─────────────────────────────────────────────────────────────────────────────
def s4_pico(d):
    pico = [
        ("P", "Population",   d.get('population',''),   "#1D4ED8", "#DBEAFE", "#1E40AF"),
        ("I", "Intervention", d.get('intervention',''), "#B91C1C", "#FEE2E2", "#DC2626"),
        ("C", "Comparison",   d.get('comparison',''),   "#B45309", "#FEF3C7", "#D97706"),
        ("O", "Outcome",      d.get('outcome',''),      "#065F46", "#D1FAE5", "#059669"),
    ]
    items = [x for x in pico if x[2]]
    n = len(items) or 1

    rows = ""
    for letter, label, value, fg, bg, mid in items:
        rows += f"""
<div style="flex:1;min-height:0;display:flex;overflow:hidden">
  <div style="width:88px;background:{fg};flex-shrink:0;display:flex;flex-direction:column;
              align-items:center;justify-content:center;gap:6px">
    <span style="font-size:42px;font-weight:900;color:#FFF">{letter}</span>
    <span style="font-size:11px;font-weight:700;color:rgba(255,255,255,.7);
                 writing-mode:vertical-lr;transform:rotate(180deg);letter-spacing:.1em">{label}</span>
  </div>
  <div style="flex:1;background:{bg};padding:20px 24px;overflow:hidden;
              display:flex;align-items:center">
    <div style="font-size:26px;color:#1E293B;line-height:1.6;overflow:hidden" class="clamp4">
      {H_(value)}
    </div>
  </div>
</div>"""

    design = d.get('design','')
    dbadge = f'<span class="badge" style="background:#5B21B6;color:#FFF;font-size:16px">{H_(design)}</span>' if design else ''

    body = f"""
<div class="slide" style="background:#F8FAFC">
  {hdr_light(4, '#5B21B6')}
  <!-- ヘッダー行: flex-shrink:0 (flex:1 を使わない！) -->
  <div style="flex-shrink:0;padding:14px 48px 12px;display:flex;align-items:center;gap:12px">
    <span style="font-size:38px;font-weight:900;color:#5B21B6">PICO &nbsp;/&nbsp; Methods</span>
    {dbadge}
  </div>
  <!-- PICOセクション: flex:1 で残り高さを全占有 -->
  <div style="flex:1;display:flex;flex-direction:column;gap:3px;overflow:hidden;min-height:0">
    {rows}
  </div>
  {info_strip(d)}
</div>"""
    return page(body)

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 5: RESULTS  ダーク背景 / チャート + 大活字アウトカム
# ─────────────────────────────────────────────────────────────────────────────
def s5_results(d):
    sa_ = d.get('stat_a',''); sb_ = d.get('stat_b','')
    sal = d.get('stat_a_label','介入群'); sbl = d.get('stat_b_label','対照群')
    ctx = d.get('stat_context','')
    primary = H_(d.get('primary_result',''))

    chart_block = ""
    if sa_ and sb_:
        b64 = chart_b64(sa_, sb_, sal, sbl, ctx) if HAS_MPL else None
        if b64:
            chart_block = f"""
<div style="flex-shrink:0;background:#0F172A;border-radius:14px;overflow:hidden;padding:8px">
  <img src="data:image/png;base64,{b64}" style="width:100%;display:block"/>
</div>"""
        else:
            chart_block = f"""
<div style="display:flex;gap:12px;flex-shrink:0">
  <div style="flex:1;background:rgba(220,38,38,.2);border:2px solid #EF4444;border-radius:16px;
              display:flex;flex-direction:column;align-items:center;justify-content:center;padding:20px 8px">
    <span style="font-size:80px;font-weight:900;color:#FCA5A5;line-height:1">{H_(sa_)}</span>
    <span style="font-size:16px;font-weight:700;color:#FCA5A5;margin-top:6px">{H_(sal)}</span>
  </div>
  <div style="width:34px;display:flex;align-items:center;justify-content:center;
              font-size:18px;color:rgba(255,255,255,.4)">vs</div>
  <div style="flex:1;background:rgba(37,99,235,.2);border:2px solid #60A5FA;border-radius:16px;
              display:flex;flex-direction:column;align-items:center;justify-content:center;padding:20px 8px">
    <span style="font-size:80px;font-weight:900;color:#93C5FD;line-height:1">{H_(sb_)}</span>
    <span style="font-size:16px;font-weight:700;color:#93C5FD;margin-top:6px">{H_(sbl)}</span>
  </div>
</div>"""

    stats = d.get('stats',[])
    stat_pills = ""
    if stats:
        items = "".join(
            f'<div style="flex:1;background:rgba(255,255,255,.1);border-radius:10px;'
            f'padding:18px 8px;text-align:center;font-size:22px;font-weight:700;'
            f'color:#FFF;line-height:1.3">{H_(s)}</div>'
            for s in stats[:3])
        stat_pills = f'<div style="display:flex;gap:10px;flex-shrink:0">{items}</div>'

    body = f"""
<div class="slide" style="background:#0F172A">
  <div style="position:absolute;width:480px;height:480px;border-radius:50%;
              background:rgba(220,38,38,.08);top:-100px;right:-80px"></div>

  {hdr_dark(5)}
  <div style="flex:1;display:flex;flex-direction:column;padding:16px 48px 16px;
              gap:14px;overflow:hidden;min-height:0;position:relative;z-index:2">
    <div style="font-size:40px;font-weight:900;color:#EF4444;flex-shrink:0">📊 &nbsp;Results</div>
    {chart_block}
    <!-- アウトカム: カード不使用でダーク背景に直接テキスト表示 -->
    <div style="flex:1;min-height:0;display:flex;flex-direction:column;gap:10px;
                border-left:4px solid #EF4444;padding-left:20px">
      <div style="font-size:13px;font-weight:800;color:#EF4444;letter-spacing:.12em;flex-shrink:0">
        PRIMARY OUTCOME
      </div>
      <!-- テキストを縦中央揃えにして余白を均等分散 -->
      <div style="flex:1;min-height:0;display:flex;flex-direction:column;justify-content:center">
        <div style="font-size:36px;color:#FFF;line-height:1.6;overflow:hidden" class="clamp8">
          {primary}
        </div>
      </div>
      {stat_pills}
    </div>
  </div>
  {info_strip(d, '#070B14', 'rgba(170,204,255,.7)')}
</div>"""
    return page(body)

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 6: STATISTICS  大数値カード / カラーボーダー
# ─────────────────────────────────────────────────────────────────────────────
def s6_stats(d):
    stats     = d.get('stats',[])
    secondary = d.get('secondary_results','')

    dot_cols  = ["#DC2626","#2563EB","#059669","#7C3AED","#D97706","#64748B"]
    bg_cols   = ["rgba(220,38,38,.09)","rgba(37,99,235,.09)","rgba(5,150,105,.09)",
                 "rgba(124,58,237,.09)","rgba(217,119,6,.09)","rgba(100,116,139,.09)"]

    n_stats = len(stats[:6])
    # 統計数が少ないほど大きいフォント
    card_font = 56 if n_stats <= 2 else (46 if n_stats == 3 else (36 if n_stats <= 4 else 28))

    stat_cards = ""
    for i, s in enumerate(stats[:6]):
        col = dot_cols[i % len(dot_cols)]
        bg  = bg_cols[i % len(bg_cols)]
        m = re.search(r'(\d+\.?\d*)\s*%', s)
        bar = ""
        if m:
            pct = min(float(m.group(1)), 100)
            bar = f"""<div style="height:10px;border-radius:5px;background:#E2E8F0;
                          overflow:hidden;margin-top:12px;flex-shrink:0">
              <div style="width:{pct:.1f}%;height:100%;background:{col};border-radius:5px"></div></div>"""
        stat_cards += f"""
<div style="flex:1;min-height:0;background:{bg};border-radius:14px;
            border-left:6px solid {col};padding:24px 28px;overflow:hidden;
            display:flex;flex-direction:column;justify-content:center">
  <div style="font-size:{card_font}px;font-weight:900;color:#0F172A;line-height:1.3;
              overflow:hidden" class="clamp3">
    {H_(s)}
  </div>
  {bar}
</div>"""

    sec_block = ""
    if secondary:
        sec_block = f"""
<div style="flex-shrink:0;background:#D1FAE5;border-radius:12px;border-left:6px solid #059669;
            padding:18px 24px;overflow:hidden">
  <div style="font-size:13px;font-weight:800;color:#065F46;letter-spacing:.1em;margin-bottom:10px">
    副次アウトカム
  </div>
  <div style="font-size:26px;color:#064E3B;line-height:1.55;overflow:hidden" class="clamp4">
    {H_(secondary)}
  </div>
</div>"""

    body = f"""
<div class="slide" style="background:#F8FAFC">
  {hdr_light(6, '#D97706')}
  <div style="flex:1;display:flex;flex-direction:column;padding:16px 48px 16px;
              gap:10px;overflow:hidden;min-height:0">
    <div style="font-size:40px;font-weight:900;color:#D97706;flex-shrink:0">📈 &nbsp;Statistics</div>
    <div style="flex:1;min-height:0;display:flex;flex-direction:column;gap:10px">
      {stat_cards}
    </div>
    {sec_block}
  </div>
  {info_strip(d)}
</div>"""
    return page(body)

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 7: TAKE HOME  ダーク全面 / 大活字メッセージ + CTA
# ─────────────────────────────────────────────────────────────────────────────
def s7_takehome(d):
    take = H_(d.get('take_home',''))
    lim  = d.get('limitations','')
    lim_text = '\n'.join(l.strip() for l in lim.split('\n') if l.strip())
    cit  = d.get('citation','')

    lim_block = ""
    if lim_text:
        lim_block = f"""
<div style="flex-shrink:0;background:rgba(255,255,255,.06);border-radius:12px;
            border:1px solid rgba(255,255,255,.15);padding:18px 22px;overflow:hidden">
  <div style="font-size:13px;font-weight:800;color:rgba(255,255,255,.4);
              letter-spacing:.1em;margin-bottom:10px">LIMITATIONS</div>
  <div style="font-size:22px;color:rgba(255,255,255,.65);line-height:1.6;
              overflow:hidden" class="clamp4">
    {H_(lim_text)}
  </div>
</div>"""

    cit_block = ""
    if cit:
        cit_block = f'<div style="font-size:13px;color:rgba(255,255,255,.3);line-height:1.5;flex-shrink:0">{H_(cit)}</div>'

    body = f"""
<div class="slide" style="background:linear-gradient(160deg,#0F172A 0%,#1E3A8A 100%)">
  <div style="position:absolute;width:500px;height:500px;border-radius:50%;
              background:rgba(37,99,235,.12);bottom:-140px;right:-80px"></div>

  {hdr_dark(7)}
  <div style="flex:1;display:flex;flex-direction:column;padding:20px 48px 16px;
              gap:16px;overflow:hidden;min-height:0;position:relative;z-index:2">
    <div style="font-size:36px;font-weight:900;color:#FFFFFF;flex-shrink:0">
      💡 &nbsp;Take Home Message
    </div>
    <div style="height:2px;background:linear-gradient(90deg,#3B82F6,transparent);
                flex-shrink:0"></div>
    <!-- ヒーローメッセージ: flex:1で垂直中央 -->
    <div style="flex:1;min-height:0;display:flex;flex-direction:column;justify-content:center;gap:16px">
      <div style="font-size:14px;font-weight:800;color:#60A5FA;letter-spacing:.12em">
        CLINICAL IMPLICATION
      </div>
      <div style="font-size:46px;font-weight:900;color:#FFFFFF;line-height:1.45;
                  overflow:hidden" class="clamp8">
        {take}
      </div>
    </div>
    {lim_block}
    {cit_block}
  </div>
  <div style="height:72px;background:#1E1B4B;display:flex;align-items:center;
              justify-content:center;flex-shrink:0;position:relative;z-index:2">
    <div style="background:linear-gradient(90deg,#2563EB,#1D4ED8);
                border-radius:14px;padding:13px 40px;
                font-size:18px;font-weight:800;color:#FFF;white-space:nowrap;
                box-shadow:0 4px 20px rgba(37,99,235,.4)">
      💾 保存して後で読み返そう &nbsp;·&nbsp; フォローで最新エビデンスを 🔔
    </div>
  </div>
</div>"""
    return page(body)

# ─────────────────────────────────────────────────────────────────────────────
# normalize + screenshot + entry point
# ─────────────────────────────────────────────────────────────────────────────
def _norm(data):
    d = dict(data)
    for f in ["population","limitations","background","intervention","comparison",
              "outcome","primary_result","secondary_results","take_home",
              "key_finding","title_jp","title_en"]:
        v = d.get(f,"")
        if isinstance(v, list): d[f] = "\n".join(str(x) for x in v)
        elif not isinstance(v, str): d[f] = str(v) if v else ""
    return d

def screenshot(html_str: str, path: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox','--disable-dev-shm-usage'])
        pg      = browser.new_page(viewport={"width": W, "height": H})
        pg.set_content(html_str, wait_until="domcontentloaded")
        pg.wait_for_timeout(300)
        pg.screenshot(path=str(path), clip={"x":0,"y":0,"width":W,"height":H})
        browser.close()

def generate_carousel(data, output_dir="output"):
    if not HAS_PLAYWRIGHT:
        raise RuntimeError("pip install playwright && playwright install chromium")
    data   = _norm(data)
    out    = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    pmid   = data.get("pmid","unknown")
    prefix = f"pmid_{pmid}"
    builders = [s1_hook, s2_keyfinding, s3_background, s4_pico,
                s5_results, s6_stats, s7_takehome]
    paths = []
    for i, fn in enumerate(builders, 1):
        path = out / f"{prefix}_slide{i}.png"
        print(f"  Rendering slide {i}/{N}...", end=" ", flush=True)
        screenshot(fn(data), str(path))
        print("done")
        paths.append(path)
    print(f"Generated {len(paths)} slides -> {out}/")
    return paths

if __name__ == "__main__":
    import sys
    sample = {
        "pmid":"v7test","study_type":"RCT","journal":"NEJM","year":"2025",
        "title_jp":"小児敗血症性ショックに対する早期バソプレシン投与の有効性",
        "title_en":"Early Vasopressin in Pediatric Septic Shock: A Randomized Controlled Trial",
        "key_finding":"早期バソプレシン追加により28日死亡率が有意に低下した（18.2% vs 26.7%, p=0.002）",
        "background":"小児敗血症性ショックでは、ノルアドレナリン不応性の血管拡張が予後不良因子となる。成人領域ではバソプレシンの早期併用が推奨されているが、小児での大規模RCTは存在しなかった。",
        "population":"生後1ヶ月-17歳の敗血症性ショック患児 (n=1,200)、28施設の小児ICU",
        "intervention":"ノルアドレナリン開始後6時間以内にバソプレシン 0.0003-0.002 U/kg/min を追加",
        "comparison":"生理食塩水（プラセボ）を追加",
        "outcome":"28日全死亡率（主要）、臓器障害日数、カテコラミン使用期間（副次）",
        "design":"Multicenter double-blind placebo-controlled RCT",
        "primary_result":"28日死亡率はバソプレシン群18.2% vs プラセボ群26.7%、絶対リスク差 -8.5% (95%CI: -13.1〜-3.9%, p=0.002)。NNT=12。",
        "stat_a":"18.2%","stat_a_label":"バソプレシン群",
        "stat_b":"26.7%","stat_b_label":"プラセボ群","stat_context":"28日死亡率",
        "stats":["HR 0.68 (95%CI 0.52-0.89)","p = 0.002","NNT = 12"],
        "secondary_results":"ICU滞在期間中央値はバソプレシン群8日 vs プラセボ群11日（p=0.03）。カテコラミン使用期間も有意に短縮。",
        "take_home":"小児敗血症性ショックでは、ノルアドレナリン開始後早期のバソプレシン追加が28日死亡率を有意に低下させる。NNT=12。ガイドラインへの反映が期待される。",
        "limitations":"- 単一民族（欧州）での試験で一般化可能性に限界\n- バソプレシン投与タイミングの個別最適化は未解明\n- 開放ラベル延長試験なし",
        "citation":"Smith J, et al. Early Vasopressin in Pediatric Septic Shock. NEJM. 2025. doi:10.1056/test",
        "hashtags":["PICU","Sepsis","Vasopressin","小児敗血症","RCT"],
        "authors":["Smith J","Doe A"],"doi":"10.1056/test",
    }
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "output"
    generate_carousel(sample, out_dir)
