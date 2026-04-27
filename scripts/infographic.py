#!/usr/bin/env python3
"""
PICU Evidence Daily — Infographic Generator v4
7枚カルーセル (1080×1350px)
設計: 高インプレッション・大文字・グラフ・余白なし
"""

import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.font_manager import FontProperties
    _JP      = FontProperties(fname='/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc')
    _JP_BOLD = FontProperties(fname='/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc')
    HAS_MPL  = True
except ImportError:
    HAS_MPL  = False

WIDTH     = 1080
HEIGHT    = 1350
MARGIN    = 44
CONTENT_W = WIDTH - MARGIN * 2   # 992
N_SLIDES  = 7

C = {
    "bg":        "#F8FAFC",
    "card":      "#FFFFFF",
    "blue":      "#1E40AF",
    "blue_lt":   "#DBEAFE",
    "blue_mid":  "#3B82F6",
    "red":       "#B91C1C",
    "red_lt":    "#FEE2E2",
    "amber":     "#92400E",
    "amber_lt":  "#FEF3C7",
    "amber_mid": "#F59E0B",
    "green":     "#065F46",
    "green_lt":  "#D1FAE5",
    "green_mid": "#10B981",
    "purple":    "#5B21B6",
    "purple_lt": "#EDE9FE",
    "text":      "#0F172A",
    "text2":     "#334155",
    "muted":     "#64748B",
    "div":       "#E2E8F0",
    "hook":      "#1E3A8A",
    "hook2":     "#1E1B4B",
}

STUDY_COLOR = {
    "RCT":               ("red",    "red_lt"),
    "Systematic Review": ("purple", "purple_lt"),
    "Meta-Analysis":     ("purple", "purple_lt"),
    "Cohort Study":      ("green",  "green_lt"),
    "Guideline":         ("blue",   "blue_lt"),
    "Review":            ("purple", "purple_lt"),
    "Case Series":       ("green",  "green_lt"),
}

FONT_CJK      = "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"
FONT_CJK_BOLD = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
FONT_LATIN    = "/System/Library/Fonts/Helvetica.ttc"
FONT_LATIN_B  = "/System/Library/Fonts/HelveticaNeue.ttc"

_fc = {}
def fnt(size, bold=False):
    k = (size, bold)
    if k not in _fc:
        _fc[k] = {
            "latin": ImageFont.truetype(FONT_LATIN_B if bold else FONT_LATIN, size),
            "cjk":   ImageFont.truetype(FONT_CJK_BOLD if bold else FONT_CJK, size),
        }
    return _fc[k]

def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def rc(key):
    return rgb(C[key])

def resolve(color):
    if isinstance(color, tuple):
        return color
    if color in C:
        return rgb(C[color])
    return rgb(color)

def is_cjk(ch):
    cp = ord(ch)
    return (0x2E80 <= cp <= 0x9FFF) or (0xF900 <= cp <= 0xFAFF) or \
           (0x3000 <= cp <= 0x30FF) or (0xFF00 <= cp <= 0xFFEF)

def pf(ch, fonts):
    return fonts["cjk"] if is_cjk(ch) else fonts["latin"]

def tw(text, fonts):
    return sum(pf(ch, fonts).getbbox(ch)[2] - pf(ch, fonts).getbbox(ch)[0] + 1
               for ch in text)

def dtx(draw, x, y, text, fonts, color):
    fill = resolve(color)
    for ch in text:
        f = pf(ch, fonts)
        bb = f.getbbox(ch)
        draw.text((x, y), ch, fill=fill, font=f)
        x += bb[2] - bb[0] + 1
    return x

def wrap(text, fonts, max_w):
    lines = []
    for para in text.split('\n'):
        if not para.strip():
            lines.append("")
            continue
        cur, cw = "", 0
        for ch in para:
            f = pf(ch, fonts)
            w = f.getbbox(ch)[2] - f.getbbox(ch)[0] + 1
            if cw + w > max_w and cur:
                lines.append(cur)
                cur, cw = ch, w
            else:
                cur += ch
                cw += w
        if cur:
            lines.append(cur)
    return lines

def lh(fonts, sp=1.5):
    bb = fonts["cjk"].getbbox("あ")
    return int((bb[3] - bb[1]) * sp)

def th(text, fonts, max_w, sp=1.5, ml=None):
    lines = wrap(text, fonts, max_w)
    if ml:
        lines = lines[:ml]
    return len(lines) * lh(fonts, sp)

def dml(draw, x, y, text, fonts, color, max_w, sp=1.5, ml=None):
    lines = wrap(text, fonts, max_w)
    if ml:
        lines = lines[:ml]
    lhv = lh(fonts, sp)
    for line in lines:
        dtx(draw, x, y, line, fonts, color)
        y += lhv
    return y

def rrect(draw, xy, r, fill=None, outline=None, ow=2):
    x0, y0, x1, y1 = xy
    r = max(0, min(r, (x1-x0)//2, (y1-y0)//2))
    if fill is not None:
        fill = resolve(fill)
    if outline is not None:
        outline = resolve(outline)
    if r == 0:
        if fill:
            draw.rectangle(xy, fill=fill)
        if outline:
            draw.rectangle(xy, outline=outline, width=ow)
        return
    if fill:
        draw.rectangle([x0+r, y0, x1-r, y1], fill=fill)
        draw.rectangle([x0, y0+r, x1, y1-r], fill=fill)
        draw.pieslice([x0, y0, x0+2*r, y0+2*r], 180, 270, fill=fill)
        draw.pieslice([x1-2*r, y0, x1, y0+2*r], 270, 360, fill=fill)
        draw.pieslice([x0, y1-2*r, x0+2*r, y1], 90, 180, fill=fill)
        draw.pieslice([x1-2*r, y1-2*r, x1, y1], 0, 90, fill=fill)
    if outline:
        draw.arc([x0, y0, x0+2*r, y0+2*r], 180, 270, fill=outline, width=ow)
        draw.arc([x1-2*r, y0, x1, y0+2*r], 270, 360, fill=outline, width=ow)
        draw.arc([x0, y1-2*r, x0+2*r, y1], 90, 180, fill=outline, width=ow)
        draw.arc([x1-2*r, y1-2*r, x1, y1], 0, 90, fill=outline, width=ow)
        draw.line([x0+r, y0, x1-r, y0], fill=outline, width=ow)
        draw.line([x0+r, y1, x1-r, y1], fill=outline, width=ow)
        draw.line([x0, y0+r, x0, y1-r], fill=outline, width=ow)
        draw.line([x1, y0+r, x1, y1-r], fill=outline, width=ow)

def badge(draw, x, y, text, bg, fg, fonts, r=8):
    cw = tw(text, fonts)
    bb = fonts["cjk"].getbbox("あ")
    ch = bb[3] - bb[1]
    px, py = 16, 9
    rrect(draw, [x, y, x+cw+px*2, y+ch+py*2], r, fill=bg)
    dtx(draw, x+px, y+py, text, fonts, fg)
    return cw+px*2, ch+py*2

def card_top(draw, x, y, w, h, accent, bg=None, r=14):
    bg_fill = rc(bg) if bg else rc("card")
    rrect(draw, [x, y, x+w, y+h], r, fill=bg_fill)
    tr = min(r, 10)
    draw.rectangle([x+tr, y, x+w-tr, y+6], fill=resolve(accent))
    draw.pieslice([x, y, x+2*tr, y+2*tr], 180, 270, fill=resolve(accent))
    draw.pieslice([x+w-2*tr, y, x+w, y+2*tr], 270, 360, fill=resolve(accent))

def sec_h(draw, x, y, text, color, sz=24):
    f = fnt(sz, bold=True)
    h = lh(f, 1.0)
    draw.rectangle([x, y+2, x+6, y+h-2], fill=resolve(color))
    dtx(draw, x+16, y, text, f, color)
    return y + lh(f, 1.35)

def top_header(draw, slide_num, accent="blue", dark=False):
    acc = C[accent]
    if not dark:
        draw.rectangle([0, 0, WIDTH, 10], fill=rgb(acc))
    y = 26
    bf = fnt(24, bold=True)
    nf = fnt(19)
    nt = f"{slide_num} / {N_SLIDES}"
    tc = "#FFFFFF" if dark else acc
    mc = "#AAAAAA" if dark else C["muted"]
    dtx(draw, MARGIN, y, "PICU Evidence Daily", bf, tc)
    dtx(draw, WIDTH - MARGIN - tw(nt, nf), y+3, nt, nf, mc)
    if not dark:
        draw.rectangle([MARGIN, 68, WIDTH-MARGIN, 69], fill=rc("div"))
    return 84

# ─── matplotlib bar chart ──────────────────────────────────────────────────

def make_chart(val_a_str, val_b_str, label_a, label_b, context, w_px, h_px):
    """横棒グラフ (PIL Image) — Agg backend + 日本語フォント指定"""
    if not HAS_MPL:
        return None

    def parse(s):
        try:
            return float(str(s).replace('%','').replace('％','').strip())
        except:
            return None

    a, b = parse(val_a_str), parse(val_b_str)
    if a is None or b is None:
        return None

    fig, ax = plt.subplots(figsize=(w_px/100, h_px/100), dpi=100)
    fig.patch.set_facecolor('#FFFFFF')
    ax.set_facecolor('#F8FAFC')

    labs  = [label_b or 'Control', label_a or 'Intervention']
    vals  = [b, a]
    clrs  = [rgb(C["blue_mid"]), rgb(C["red"])]
    # matplotlib expects 0-1 floats for colors
    clrs_f = [(r/255, g/255, b_/255) for r, g, b_ in clrs]

    bars = ax.barh(labs, vals, color=clrs_f, height=0.52, edgecolor='white', linewidth=3)

    for bar, val in zip(bars, vals):
        ax.text(bar.get_width() + max(a, b)*0.025,
                bar.get_y() + bar.get_height()/2,
                f'{val:.1f}%', va='center', ha='left',
                fontproperties=_JP_BOLD, fontsize=20, color=C["text"])

    if context:
        ax.set_title(context, fontproperties=_JP_BOLD, fontsize=17,
                     color=C["text"], pad=12)

    ax.set_xlim(0, max(a, b) * 1.38)
    ax.tick_params(axis='y', labelsize=16)
    ax.tick_params(axis='x', labelsize=13)
    for tick in ax.get_yticklabels():
        tick.set_fontproperties(_JP)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#E2E8F0')
    ax.spines['bottom'].set_color('#E2E8F0')
    ax.grid(axis='x', color='#E2E8F0', linestyle='--', linewidth=0.8, alpha=0.8)

    buf = io.BytesIO()
    plt.tight_layout(pad=0.6)
    fig.savefig(buf, format='PNG', dpi=100, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    chart = Image.open(buf).copy()
    plt.close(fig)
    buf.close()
    return chart

# ─── shared visual helpers ─────────────────────────────────────────────────

def progress_bar(draw, x, y, w, h, value, max_val, fill, bg):
    pct = min(max(value / max_val, 0), 1.0)
    rrect(draw, [x, y, x+w, y+h], h//2, fill=bg)
    fw = max(int(w * pct), h)
    rrect(draw, [x, y, x+fw, y+h], h//2, fill=fill)

def stat_pill_row(draw, y, stats_list, color_cycle):
    """stats_list の最初の3件を横並びカラーピルで表示"""
    items = stats_list[:3]
    if not items:
        return y
    pill_w = (CONTENT_W - 16 * (len(items)-1)) // len(items)
    pill_f = fnt(21, bold=True)
    pill_h = 66
    for i, s in enumerate(items):
        px = MARGIN + i * (pill_w + 16)
        col = color_cycle[i % len(color_cycle)]
        lt  = col + "_lt"
        rrect(draw, [px, y, px+pill_w, y+pill_h], 10, fill=lt)
        rrect(draw, [px, y, px+pill_w, y+pill_h], 10, outline=col, ow=2)
        label_w = tw(s, pill_f)
        if label_w <= pill_w - 12:
            dtx(draw, px + (pill_w - label_w)//2, y + (pill_h - lh(pill_f, 1.0))//2,
                s, pill_f, col)
        else:
            dml(draw, px+8, y+8, s, pill_f, col, pill_w-16, 1.25, ml=2)
    return y + pill_h

def big_compare(draw, x, y, w, h,
                val_a, lbl_a, col_a, lt_a,
                val_b, lbl_b, col_b, lt_b):
    """2分割の大きな数値比較ボックス"""
    hw = (w - 12) // 2
    # Left
    rrect(draw, [x, y, x+hw, y+h], 14, fill=lt_a)
    rrect(draw, [x, y, x+hw, y+h], 14, outline=col_a, ow=3)
    nf = fnt(96, bold=True)
    nw = tw(val_a, nf)
    nx = x + (hw - nw)//2
    dtx(draw, nx, y + 16, val_a, nf, col_a)
    lf = fnt(22, bold=True)
    lw = tw(lbl_a, lf)
    dtx(draw, x + (hw-lw)//2, y + h - 42, lbl_a, lf, col_a)
    # VS
    vsf = fnt(26, bold=True)
    vsw = tw("vs", vsf)
    dtx(draw, x + hw + (12 - vsw)//2, y + (h - lh(vsf))//2, "vs", vsf, "muted")
    # Right
    rx = x + hw + 12
    rrect(draw, [rx, y, rx+hw, y+h], 14, fill=lt_b)
    rrect(draw, [rx, y, rx+hw, y+h], 14, outline=col_b, ow=3)
    bw = tw(val_b, nf)
    bx = rx + (hw - bw)//2
    dtx(draw, bx, y + 16, val_b, nf, col_b)
    lbw = tw(lbl_b, lf)
    dtx(draw, rx + (hw-lbw)//2, y + h - 42, lbl_b, lf, col_b)

# ─── Layout constants ──────────────────────────────────────────────────────
FLOOR   = HEIGHT - 72   # 全コンテンツはここで終わる
STRIP_H = 72            # 下端ストリップ高さ
CTA_H   = 64            # CTAボタン高さ (スライド7)

def fill_to(y, reserve=0):
    """y から FLOOR までの残り高さ"""
    return max(80, FLOOR - y - reserve - 14)

def info_strip(draw, data):
    """FLOOR〜HEIGHT に固定情報ストリップ"""
    draw.rectangle([0, FLOOR, WIDTH, HEIGHT], fill=resolve("hook"))
    sf   = fnt(20, bold=True)
    info = (f"\U0001f4f0 {data.get('journal','')}  ·  {data.get('year','')}"
            f"  ·  {data.get('study_type','')}")
    iw   = tw(info, sf)
    cy   = FLOOR + (STRIP_H - lh(sf, 1.0)) // 2
    if iw <= CONTENT_W:
        dtx(draw, (WIDTH - iw) // 2, cy, info, sf, "#AACCFF")
    else:
        dml(draw, MARGIN, cy, info, sf, "#AACCFF", CONTENT_W, 1.2, ml=1)

def cta_bar(draw):
    """FLOOR 位置に固定CTAボタン (スライド7用)"""
    cy    = FLOOR + (STRIP_H - CTA_H) // 2
    rrect(draw, [MARGIN, cy, MARGIN+CONTENT_W, cy+CTA_H], 14, fill="blue")
    cta_f = fnt(20, bold=True)
    cta   = "\U0001f4be 保存して後で読み返そう  ·  フォローで最新エビデンスを \U0001f514"
    ctaw  = tw(cta, cta_f)
    ty    = cy + (CTA_H - lh(cta_f, 1.0)) // 2
    if ctaw <= CONTENT_W - 32:
        dtx(draw, (WIDTH - ctaw) // 2, ty, cta, cta_f, "#FFFFFF")
    else:
        dml(draw, MARGIN+16, ty - 4, cta, cta_f, "#FFFFFF", CONTENT_W-32, 1.25, ml=2)

import re as _re

# ─── SLIDE 1 : Hook (dark blue) ────────────────────────────────────────────

def slide1_hook(data, path):
    img  = Image.new("RGB", (WIDTH, HEIGHT), rc("hook"))
    draw = ImageDraw.Draw(img)

    # Decorative circles
    draw.ellipse([760, -140, 1200, 300],  fill=(30, 60, 180))
    draw.ellipse([-160, 1050, 280, 1490], fill=(25, 50, 160))

    y = top_header(draw, 1, dark=True)
    y += 18

    # Study badge + journal
    st = data.get("study_type", "RCT")
    sc_key, _ = STUDY_COLOR.get(st, ("amber","amber_lt"))
    sc = C[sc_key]
    bf = fnt(24, bold=True)
    bw, bh = badge(draw, MARGIN, y, f"  {st}  ", sc, "#FFFFFF", bf)
    dtx(draw, MARGIN+bw+14, y+7, f"{data.get('journal','')}  ·  {data.get('year','')}", fnt(22), "#AACCFF")
    y += bh + 20
    draw.rectangle([MARGIN, y, WIDTH-MARGIN, y+2], fill=(255,255,255,50))
    y += 18

    # KEY FINDING label
    dtx(draw, MARGIN, y, "KEY  FINDING", fnt(20, bold=True), "#FCD34D")
    y += 38

    # Key finding text — BIG
    kf = data.get("key_finding", "")
    kff = fnt(42, bold=True)
    y = dml(draw, MARGIN, y, kf, kff, "#FFFFFF", CONTENT_W, 1.35, ml=5)
    y += 28

    draw.rectangle([MARGIN, y, WIDTH-MARGIN, y+3], fill=(255,255,255,60))
    y += 22

    # Big comparison boxes if available
    sa = data.get("stat_a", "")
    sb = data.get("stat_b", "")
    if sa and sb:
        ctx = data.get("stat_context", "")
        if ctx:
            ctxf = fnt(24, bold=True)
            ctxw = tw(ctx, ctxf)
            dtx(draw, (WIDTH-ctxw)//2, y, ctx, ctxf, "#FFFFFF")
            y += lh(ctxf, 1.2) + 10

        big_h = 148
        big_compare(draw, MARGIN, y, CONTENT_W, big_h,
                    sa, data.get("stat_a_label","介入群"), "#EF4444","#FEE2E2",
                    sb, data.get("stat_b_label","対照群"), "#3B82F6","#DBEAFE")
        y += big_h + 16

        # NNT / stats row
        stats = data.get("stats", [])
        if stats:
            row_f = fnt(22, bold=True)
            col_list = ["#FCD34D","#6EE7B7","#93C5FD","#F9A8D4"]
            for i, s in enumerate(stats[:3]):
                px = MARGIN + i * (CONTENT_W//3 + 6)
                dtx(draw, px, y, f"▸ {s}", row_f, col_list[i % len(col_list)])
            y += lh(row_f, 1.3) + 12
    else:
        # No stats: show title bigger
        pass

    draw.rectangle([MARGIN, y, WIDTH-MARGIN, y+2], fill=(255,255,255,40))
    y += 18

    # Title JP
    tf = fnt(28, bold=True)
    y = dml(draw, MARGIN, y, data.get("title_jp",""), tf, "#CCE0FF", CONTENT_W, 1.3, ml=3)
    y += 16

    # EN title
    ef = fnt(20)
    y = dml(draw, MARGIN, y, data.get("title_en",""), ef, "#7799BB", CONTENT_W, 1.25, ml=2)
    y += 20

    # Fill remaining with stats pills if space and no big compare
    stats = data.get("stats", [])
    if stats and not (sa and sb) and y + 90 < FLOOR - 80:
        y = stat_pill_row(draw, y + 10, stats[:3], ["blue","red","amber"]) + 10

    # Swipe CTA — just above FLOOR
    cta_y = max(y + 20, FLOOR - 72)
    draw.rectangle([0, cta_y - 14, WIDTH, cta_y - 12], fill=(255, 255, 255, 30))
    cta_f = fnt(22, bold=True)
    cta   = "スライドをスワイプして詳細を見る  ▶"
    ctaw  = tw(cta, cta_f)
    dtx(draw, (WIDTH - ctaw) // 2, cta_y, cta, cta_f, "#FFFFFF")

    info_strip(draw, data)
    img.save(path, quality=95)
    return img


# ─── SLIDE 2 : Title overview (white) ──────────────────────────────────────

def slide2_title(data, path):
    img  = Image.new("RGB", (WIDTH, HEIGHT), rc("bg"))
    draw = ImageDraw.Draw(img)
    st   = data.get("study_type","RCT")
    sc_key, sc_lt = STUDY_COLOR.get(st, ("blue","blue_lt"))
    y = top_header(draw, 2, sc_key)
    y += 10

    # Study band
    band_h = 76
    bf  = fnt(24, bold=True)
    bb_ = bf["cjk"].getbbox("あ")
    bh_e = (bb_[3]-bb_[1]) + 18
    badge_y = y + (band_h - bh_e) // 2
    rrect(draw, [MARGIN, y, MARGIN+CONTENT_W, y+band_h], 12, fill=sc_lt)
    bw, bh = badge(draw, MARGIN+16, badge_y, f"  {st}  ", C[sc_key], "#FFFFFF", bf)
    jf    = fnt(21)
    jtext = f"{data.get('journal','')}  ·  {data.get('year','')}  ·  {data.get('design','')}"
    dml(draw, MARGIN+16+bw+14, badge_y+5, jtext, jf, "text2", CONTENT_W-bw-60, 1.2, ml=1)
    y += band_h + 20

    # JP title
    tf = fnt(42, bold=True)
    y = dml(draw, MARGIN, y, data.get("title_jp",""), tf, "text", CONTENT_W, 1.35, ml=4)
    y += 10

    # EN title
    ef = fnt(19)
    y = dml(draw, MARGIN, y, data.get("title_en",""), ef, "muted", CONTENT_W, 1.3, ml=2)
    y += 22

    # Key finding card — expands to fill all remaining space to FLOOR
    kf  = data.get("key_finding","")
    kff = fnt(28, bold=True)
    iw  = CONTENT_W - 52
    kf_h = fill_to(y)
    card_top(draw, MARGIN, y, CONTENT_W, kf_h, "amber", "amber_lt")
    cy = y + 22
    cy = sec_h(draw, MARGIN+22, cy, "Key Finding", "amber")
    cy += 8
    dml(draw, MARGIN+26, cy, kf, kff, "text", iw, 1.45)

    info_strip(draw, data)
    img.save(path, quality=95)
    return img


# ─── SLIDE 3 : Background (white) ──────────────────────────────────────────

def slide3_background(data, path):
    img  = Image.new("RGB", (WIDTH, HEIGHT), rc("bg"))
    draw = ImageDraw.Draw(img)
    y = top_header(draw, 3, "blue")
    y += 10

    ptf = fnt(44, bold=True)
    dtx(draw, MARGIN, y, "なぜこの研究？", ptf, "blue")
    y += lh(ptf, 1.2) + 16

    iw      = CONTENT_W - 52
    bg_text = data.get("background","")
    bgf     = fnt(27)
    pop     = data.get("population","")

    if pop:
        # Split remaining: 55% background, 45% population
        remaining = FLOOR - y - 12
        bg_h  = int(remaining * 0.55)
        pop_h = remaining - bg_h
        card_top(draw, MARGIN, y, CONTENT_W, bg_h, "blue", "blue_lt")
        cy = y + 20
        cy = sec_h(draw, MARGIN+22, cy, "Background", "blue")
        cy += 8
        dml(draw, MARGIN+26, cy, bg_text, bgf, "text2", iw, 1.5)
        y += bg_h + 12
        popf = fnt(27)
        card_top(draw, MARGIN, y, CONTENT_W, pop_h, "green", "green_lt")
        cy = y + 20
        cy = sec_h(draw, MARGIN+22, cy, "対象患者 / Population", "green")
        cy += 8
        dml(draw, MARGIN+26, cy, pop, popf, "text2", iw, 1.45)
    else:
        bg_h = fill_to(y)
        card_top(draw, MARGIN, y, CONTENT_W, bg_h, "blue", "blue_lt")
        cy = y + 20
        cy = sec_h(draw, MARGIN+22, cy, "Background", "blue")
        cy += 8
        dml(draw, MARGIN+26, cy, bg_text, bgf, "text2", iw, 1.5)

    info_strip(draw, data)
    img.save(path, quality=95)
    return img


# ─── SLIDE 4 : Methods / PICO (white) ──────────────────────────────────────

def slide4_pico(data, path):
    img  = Image.new("RGB", (WIDTH, HEIGHT), rc("bg"))
    draw = ImageDraw.Draw(img)
    y = top_header(draw, 4, "purple")
    y += 10

    ptf = fnt(44, bold=True)
    dtx(draw, MARGIN, y, "研究デザイン / Methods", ptf, "purple")
    y += lh(ptf, 1.2) + 12

    design = data.get("design","")
    if design:
        df = fnt(21, bold=True)
        dw, dh = badge(draw, MARGIN, y, f"  {design}  ", "purple", "#FFFFFF", df)
        y += dh + 14

    pico_items = [
        ("P", "Population",   "blue",  "blue_lt",  data.get("population",   "")),
        ("I", "Intervention", "red",   "red_lt",   data.get("intervention", "")),
        ("C", "Comparison",   "amber", "amber_lt", data.get("comparison",   "")),
        ("O", "Outcome",      "green", "green_lt", data.get("outcome",      "")),
    ]

    n_items = sum(1 for *_, v in pico_items if v)
    if n_items == 0:
        n_items = 1
    item_gap = 10
    total_h  = FLOOR - y - item_gap * (n_items - 1)
    item_h   = max(80, total_h // n_items)

    val_f = fnt(24)
    lbl_f = fnt(17, bold=True)
    iw    = CONTENT_W - 84

    for letter, label, acc, acc_lt, value in pico_items:
        if not value:
            continue
        rrect(draw, [MARGIN, y, MARGIN+CONTENT_W, y+item_h], 12, fill=acc_lt)
        rrect(draw, [MARGIN, y, MARGIN+CONTENT_W, y+item_h], 12, outline=acc, ow=2)
        rrect(draw, [MARGIN+12, y+12, MARGIN+58, y+58], 23, fill=acc)
        ltr_f = fnt(28, bold=True)
        lw_   = tw(letter, ltr_f)
        dtx(draw, MARGIN+12+(46-lw_)//2, y+14, letter, ltr_f, "#FFFFFF")
        dtx(draw, MARGIN+70, y+10, label, lbl_f, acc)
        dml(draw, MARGIN+70, y+36, value, val_f, "text2", iw, 1.4)
        y += item_h + item_gap

    info_strip(draw, data)
    img.save(path, quality=95)
    return img


# ─── SLIDE 5 : Results — big numbers + chart (white) ───────────────────────

def slide5_results(data, path):
    img  = Image.new("RGB", (WIDTH, HEIGHT), rc("bg"))
    draw = ImageDraw.Draw(img)
    y = top_header(draw, 5, "red")
    y += 10

    ptf = fnt(44, bold=True)
    dtx(draw, MARGIN, y, "Results", ptf, "red")
    y += lh(ptf, 1.2) + 16

    sa     = data.get("stat_a","")
    sb     = data.get("stat_b","")
    sa_lbl = data.get("stat_a_label","介入群")
    sb_lbl = data.get("stat_b_label","対照群")
    ctx    = data.get("stat_context","")

    if sa and sb and HAS_MPL:
        chart_h   = 320
        chart_img = make_chart(sa, sb, sa_lbl, sb_lbl, ctx, CONTENT_W, chart_h)
        if chart_img:
            chart_img = chart_img.resize((CONTENT_W, chart_h), Image.LANCZOS)
            rrect(draw, [MARGIN, y, MARGIN+CONTENT_W, y+chart_h+20], 14, fill="card")
            img.paste(chart_img, (MARGIN, y+10))
            y += chart_h + 30
    elif sa and sb:
        ctx_f = fnt(24, bold=True)
        if ctx:
            ctxw = tw(ctx, ctx_f)
            dtx(draw, (WIDTH-ctxw)//2, y, ctx, ctx_f, "text")
            y += lh(ctx_f, 1.2) + 8
        big_h = 160
        big_compare(draw, MARGIN, y, CONTENT_W, big_h,
                    sa, sa_lbl, "red","red_lt",
                    sb, sb_lbl, "blue","blue_lt")
        y += big_h + 18

    # Primary result card — fills all remaining space
    primary = data.get("primary_result","")
    iw  = CONTENT_W - 52
    prf = fnt(26, bold=True)
    pr_h = fill_to(y)
    card_top(draw, MARGIN, y, CONTENT_W, pr_h, "red", "red_lt")
    cy = y + 20
    cy = sec_h(draw, MARGIN+22, cy, "Primary Outcome", "red")
    cy += 8
    cy = dml(draw, MARGIN+26, cy, primary, prf, "text", iw, 1.45)
    # Stats pills anchored inside card near bottom
    stats = data.get("stats",[])
    if stats and cy + 80 < y + pr_h - 10:
        stat_pill_row(draw, max(cy + 14, y + pr_h - 90), stats[:3], ["red","blue","amber"])

    info_strip(draw, data)
    img.save(path, quality=95)
    return img


# ─── SLIDE 6 : Stats + progress bars (white) ───────────────────────────────

def slide6_stats(data, path):
    img  = Image.new("RGB", (WIDTH, HEIGHT), rc("bg"))
    draw = ImageDraw.Draw(img)
    y = top_header(draw, 6, "amber")
    y += 10

    ptf = fnt(44, bold=True)
    dtx(draw, MARGIN, y, "Statistics", ptf, "amber")
    y += lh(ptf, 1.2) + 16

    iw        = CONTENT_W - 52
    stats     = data.get("stats",[])
    secondary = data.get("secondary_results","")
    secf      = fnt(26)

    # Reserve height for secondary card if present
    if secondary:
        sec_card_h = min(th(secondary, secf, iw, 1.5, ml=4) + 84, 320)
        sec_card_h = max(sec_card_h, 140)
    else:
        sec_card_h = 0

    reserve = sec_card_h + (14 if sec_card_h else 0)
    s_h = fill_to(y, reserve)

    if stats:
        card_top(draw, MARGIN, y, CONTENT_W, s_h, "amber", "amber_lt")
        cy = y + 20
        cy = sec_h(draw, MARGIN+22, cy, "Key Statistics", "amber")
        cy += 8
        stat_f = fnt(24, bold=True)
        for i, s in enumerate(stats[:6]):
            if cy + 40 > y + s_h - 8:
                break
            dot_col = ["red","blue","green","purple","amber","muted"][i % 6]
            rrect(draw, [MARGIN+24, cy+10, MARGIN+44, cy+30], 10, fill=dot_col)
            pct_val = None
            m = _re.search(r'(\d+\.?\d*)\s*%', s)
            if m:
                pct_val = float(m.group(1))
            if pct_val is not None and pct_val <= 100:
                cy = dml(draw, MARGIN+52, cy, s, stat_f, "text", iw-42, 1.4, ml=2)
                pb_h = 12
                progress_bar(draw, MARGIN+52, cy+2, iw-42, pb_h, pct_val, 100, dot_col, "div")
                cy += pb_h + 10
            else:
                cy = dml(draw, MARGIN+52, cy, s, stat_f, "text", iw-42, 1.4, ml=2)
            cy += 12
        y += s_h + 14

    if secondary and sec_card_h > 0:
        card_top(draw, MARGIN, y, CONTENT_W, sec_card_h, "green", "green_lt")
        cy = y + 20
        cy = sec_h(draw, MARGIN+22, cy, "副次アウトカム", "green")
        cy += 8
        dml(draw, MARGIN+26, cy, secondary, secf, "text2", iw, 1.5, ml=4)

    info_strip(draw, data)
    img.save(path, quality=95)
    return img


# ─── SLIDE 7 : Take Home + CTA (white) ─────────────────────────────────────

def slide7_takehome(data, path):
    img  = Image.new("RGB", (WIDTH, HEIGHT), rc("bg"))
    draw = ImageDraw.Draw(img)
    y = top_header(draw, 7, "blue")
    y += 10

    ptf = fnt(44, bold=True)
    dtx(draw, MARGIN, y, "Take Home Message", ptf, "blue")
    y += lh(ptf, 1.2) + 16

    iw = CONTENT_W - 52

    # Pre-calculate sizes of elements below the main card
    lim      = data.get("limitations","")
    lim_text = '\n'.join([l.strip() for l in lim.split('\n') if l.strip()][:3])
    limf     = fnt(22)
    lim_h    = min(th(lim_text, limf, iw, 1.4, ml=4) + 80, 260) if lim_text else 0

    cit   = data.get("citation","")
    cf    = fnt(16)
    cit_h = th(cit, cf, CONTENT_W, 1.3, 2) + 14 if cit else 0

    gaps    = (14 if lim_h else 0) + (14 if cit_h else 0)
    reserve = lim_h + cit_h + gaps

    # Take home card fills remaining space above limitations + citation
    thf  = fnt(28, bold=True)
    th_h = fill_to(y, reserve)
    card_top(draw, MARGIN, y, CONTENT_W, th_h, "blue", "blue_lt")
    cy = y + 22
    cy = sec_h(draw, MARGIN+22, cy, "Take Home Message", "blue")
    cy += 8
    cy = dml(draw, MARGIN+26, cy, data.get("take_home",""), thf, "text", iw, 1.45)
    # Stats pills near bottom of card if space
    stats = data.get("stats",[])
    if stats and cy + 80 < y + th_h - 10:
        stat_pill_row(draw, max(cy + 14, y + th_h - 90), stats[:3], ["blue","red","green"])
    y += th_h + 14

    if lim_text and lim_h:
        card_top(draw, MARGIN, y, CONTENT_W, lim_h, "muted", None)
        cy = y + 20
        cy = sec_h(draw, MARGIN+22, cy, "Limitations", "muted")
        cy += 8
        dml(draw, MARGIN+26, cy, lim_text, limf, "text2", iw, 1.4, ml=4)
        y += lim_h + 14

    if cit:
        dml(draw, MARGIN, y, cit, cf, "muted", CONTENT_W, 1.3, ml=2)

    # Dark bottom strip with CTA button
    draw.rectangle([0, FLOOR, WIDTH, HEIGHT], fill=resolve("hook2"))
    cta_bar(draw)
    img.save(path, quality=95)
    return img


# ─── Entry point ────────────────────────────────────────────────────────────

def _normalize(data):
    d = dict(data)
    list_fields = ["population","limitations","background","intervention",
                   "comparison","outcome","primary_result","secondary_results",
                   "take_home","key_finding","title_jp","title_en"]
    for f in list_fields:
        v = d.get(f, "")
        if isinstance(v, list):
            d[f] = "\n".join(str(x) for x in v)
        elif not isinstance(v, str):
            d[f] = str(v) if v else ""
    return d


def generate_carousel(data, output_dir="output"):
    data   = _normalize(data)
    out    = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    pmid   = data.get("pmid","unknown")
    prefix = f"pmid_{pmid}"

    slides = [
        slide1_hook(data,       out / f"{prefix}_slide1.png"),
        slide2_title(data,      out / f"{prefix}_slide2.png"),
        slide3_background(data, out / f"{prefix}_slide3.png"),
        slide4_pico(data,       out / f"{prefix}_slide4.png"),
        slide5_results(data,    out / f"{prefix}_slide5.png"),
        slide6_stats(data,      out / f"{prefix}_slide6.png"),
        slide7_takehome(data,   out / f"{prefix}_slide7.png"),
    ]
    print(f"Generated {len(slides)} slides -> {out}/")
    for i in range(N_SLIDES):
        print(f"  Slide {i+1}: {prefix}_slide{i+1}.png")
    return slides


if __name__ == "__main__":
    sample = {
        "pmid": "39876543",
        "study_type": "RCT",
        "journal": "NEJM",
        "year": "2025",
        "title_jp": "小児敗血症性ショックに対する早期バソプレシン投与の有効性",
        "title_en": "Early Vasopressin in Pediatric Septic Shock: A Randomized Controlled Trial",
        "key_finding": "早期バソプレシン追加により28日死亡率が有意に低下した（18.2% vs 26.7%, p=0.002）",
        "background": "小児敗血症性ショックでは、ノルアドレナリン不応性の血管拡張が予後不良因子となる。成人領域ではバソプレシンの早期併用が推奨されているが、小児での大規模RCTは存在しなかった。",
        "population": "生後1ヶ月-17歳の敗血症性ショック患児 (n=1,200)、28施設の小児ICU",
        "intervention": "ノルアドレナリン開始後6時間以内にバソプレシン 0.0003-0.002 U/kg/min を追加",
        "comparison": "生理食塩水（プラセボ）を追加",
        "outcome": "28日全死亡率（主要）、臓器障害日数、カテコラミン使用期間（副次）",
        "design": "Multicenter double-blind placebo-controlled RCT",
        "primary_result": "28日死亡率はバソプレシン群18.2% vs プラセボ群26.7%、絶対リスク差 -8.5% (95%CI: -13.1〜-3.9%, p=0.002)。NNT=12。",
        "stat_a":       "18.2%",
        "stat_a_label": "バソプレシン群",
        "stat_b":       "26.7%",
        "stat_b_label": "プラセボ群",
        "stat_context": "28日死亡率",
        "stats": [
            "HR 0.64 (95%CI: 0.49-0.84)",
            "NNT = 12 (95%CI: 8-26)",
            "PELOD-2: p<0.001 改善",
        ],
        "secondary_results": "PELOD-2スコアで評価した臓器障害日数は有意に短縮（中央値5日 vs 8日, p<0.001）。カテコラミン総投与量も有意に減少。",
        "take_home": "小児敗血症性ショックにおいて、ノルアドレナリン開始後6時間以内のバソプレシン追加は28日死亡率を有意に低下させた（NNT=12）。安全性プロファイルも良好であり、今後のガイドライン改訂で議論されるべきエビデンス。",
        "limitations": "- 対象の約70%が高所得国のPICU\n- 敗血症の原因微生物の分布に偏りあり\n- 生後1ヶ月未満の新生児は除外",
        "citation": "Smith J, et al. Early Vasopressin in Pediatric Septic Shock. N Engl J Med. 2025;392(15):1423-1435.",
    }
    generate_carousel(sample, "../output")
