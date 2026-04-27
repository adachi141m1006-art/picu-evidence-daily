#!/usr/bin/env python3
"""
PICU Evidence Daily — Hybrid Infographic Generator
===================================================
Gemini AI → 背景ビジュアル生成（テキストなし）
Playwright → 正確な日本語テキストをオーバーレイ
PIL → 合成

アーキテクチャ:
  1. Gemini: 抽象的な背景画像を生成（日本語テキストなし）
  2. HTML builders (v7): CSS !important で Gemini 背景を注入しスクリーンショット
  3. 出力: Gemini の美しいビジュアル + 正確な日本語テキスト
"""

import base64, io, os, sys, time
from pathlib import Path
from PIL import Image

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

sys.path.insert(0, str(Path(__file__).parent))
from infographic_html import (
    s1_hook, s2_keyfinding, s3_background, s4_pico,
    s5_results, s6_stats, s7_takehome, _norm, W, H, N, sa
)

# ─── Gemini 背景プロンプト (英語のみ、テキスト一切なし) ────────────────────

def _dark_bg(c1, c2, accent, hint=""):
    return (
        f"Abstract digital art background for a medical infographic slide. "
        f"Dominant color: {c1} transitioning to {c2}. "
        f"Accent: glowing {accent} bokeh orbs and radial light effects. "
        f"Style: professional, dramatic, scientific. "
        f"Elements: soft circular glows, subtle hexagonal grid pattern, depth layers. "
        f"Very dark, moody atmosphere. Portrait 4:5 ratio. "
        f"ABSOLUTELY NO TEXT. NO LETTERS. NO NUMBERS. NO LABELS. NO UI ELEMENTS. "
        f"Pure abstract visual background only. {hint}"
    )

def _light_bg(accent, hint=""):
    return (
        f"Clean minimal light background for a medical statistics slide. "
        f"Very light warm white base with subtle {accent} accent gradient on edges. "
        f"Faint soft geometric shapes. Professional medical aesthetic. "
        f"ABSOLUTELY NO TEXT. NO LETTERS. NO NUMBERS. NO LABELS. NO UI ELEMENTS. "
        f"Pure abstract light background. {hint}"
    )

STUDY_COLORS = {
    "RCT":               ("deep crimson red",    "near-black charcoal", "bright red"),
    "Systematic Review": ("deep violet purple",  "dark navy",           "violet"),
    "Meta-Analysis":     ("deep violet purple",  "dark navy",           "violet"),
    "Cohort Study":      ("very dark forest green","dark navy",          "emerald green"),
    "Guideline":         ("very dark navy blue", "dark indigo",         "royal blue"),
    "Review":            ("deep violet purple",  "dark navy",           "violet"),
    "Case Series":       ("very dark forest green","dark navy",          "emerald green"),
}
def _study_cols(st):
    return STUDY_COLORS.get(st, ("dark amber brown", "near-black", "gold amber"))

def _bg(slide_num: int, st: str) -> str:
    c1, c2, acc = _study_cols(st)
    prompts = {
        1: _dark_bg("very dark navy blue", "dark indigo",  "electric blue",
                    "Subtle abstract molecular network silhouette in background."),
        2: _dark_bg(c1, c2, acc,
                    "Abstract large decorative quotation mark shape, very subtle. " +
                    "Drama and impact. Strong visual presence."),
        3: _dark_bg("very dark navy",      "dark royal blue", "cyan blue",
                    "Split-horizon design, upper portion darker than lower."),
        4: _light_bg("soft purple-blue", "Very nearly white. Extremely minimal."),
        5: _dark_bg("very dark navy",      "near black",     c1.split()[0]+" red glow",
                    "Abstract bar chart silhouette shapes, very subtle, in background."),
        6: _light_bg("warm amber-gold",   "Slightly warm tone. Clean."),
        7: _dark_bg("dark navy blue",      "deep blue",      "bright electric blue",
                    "Soft upward light beam or spotlight, hopeful mood. Aspirational."),
    }
    return prompts.get(slide_num, _dark_bg("dark navy", "near black", "blue"))

# ─── Gemini 背景生成 ──────────────────────────────────────────────────────

def _gen_background(client, prompt: str, max_retries: int = 4) -> bytes:
    for attempt in range(max_retries):
        try:
            resp = client.models.generate_content(
                model='gemini-2.5-flash-image',
                contents=prompt,
                config=types.GenerateContentConfig(response_modalities=['IMAGE', 'TEXT'])
            )
            for part in resp.candidates[0].content.parts:
                if part.inline_data is not None:
                    img = Image.open(io.BytesIO(part.inline_data.data)).convert('RGB')
                    w, h = img.size
                    target_h = int(w * H / W)
                    if h > target_h:
                        top = (h - target_h) // 2
                        img = img.crop((0, top, w, top + target_h))
                    elif h < target_h:
                        new_w = int(h * W / H)
                        left = (w - new_w) // 2
                        img = img.crop((left, 0, left + new_w, h))
                    img = img.resize((W, H), Image.LANCZOS)
                    buf = io.BytesIO()
                    img.save(buf, 'PNG')
                    return buf.getvalue()
            raise ValueError("Gemini returned no image data")
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait = 10 * (attempt + 1)
            print(f"retry({attempt+1}/{max_retries-1}) in {wait}s [{e}]...", end=" ", flush=True)
            time.sleep(wait)

# ─── HTML に Gemini 背景を注入 ───────────────────────────────────────────

def _inject_bg(html_str: str, bg_b64: str, dark: bool) -> str:
    # CSS 多重背景: 半透明グラデーション(前面) + Gemini画像(背面)
    # !important で inline style background を上書き（CSS仕様: !important author > inline normal）
    overlay = "rgba(0,0,0,0.36)" if dark else "rgba(0,0,0,0.07)"
    extra = f"""
    .slide {{
        background:
            linear-gradient({overlay}, {overlay}),
            url('data:image/png;base64,{bg_b64}') center / cover no-repeat !important;
    }}
    """
    return html_str.replace('</style>', extra + '</style>')

# ─── スクリーンショット ──────────────────────────────────────────────────

def _screenshot(html_str: str, path: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage'])
        pg = browser.new_page(viewport={"width": W, "height": H})
        pg.set_content(html_str, wait_until="domcontentloaded")
        pg.wait_for_timeout(400)
        pg.screenshot(path=str(path), clip={"x": 0, "y": 0, "width": W, "height": H})
        browser.close()

# ─── メインエントリ ──────────────────────────────────────────────────────

DARK_SLIDES = {1, 2, 3, 5, 7}

def generate_carousel(data, output_dir="output"):
    if not HAS_PLAYWRIGHT:
        raise RuntimeError("pip install playwright && playwright install chromium")
    if not HAS_GENAI:
        raise RuntimeError("pip install google-genai")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    client = genai.Client(api_key=api_key)
    data = _norm(data)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    pmid = data.get("pmid", "unknown")
    st   = data.get("study_type", "RCT")

    builders = [s1_hook, s2_keyfinding, s3_background, s4_pico,
                s5_results, s6_stats, s7_takehome]
    paths = []

    for i, fn in enumerate(builders, 1):
        path = out / f"pmid_{pmid}_slide{i}.png"
        print(f"  [{i}/7] Gemini BG...", end=" ", flush=True)

        bg_bytes = _gen_background(client, _bg(i, st))
        bg_b64   = base64.b64encode(bg_bytes).decode()

        print("HTML overlay...", end=" ", flush=True)
        html_str     = fn(data)
        html_with_bg = _inject_bg(html_str, bg_b64, dark=(i in DARK_SLIDES))
        _screenshot(html_with_bg, str(path))

        print("done")
        paths.append(path)

    print(f"Generated {len(paths)} hybrid slides -> {out}/")
    return paths


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")

    sample = {
        "pmid": "hybrid_test", "study_type": "RCT",
        "journal": "NEJM", "year": "2025",
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
        "stat_a": "18.2%", "stat_a_label": "バソプレシン群",
        "stat_b": "26.7%", "stat_b_label": "プラセボ群", "stat_context": "28日死亡率",
        "stats": ["HR 0.68 (95%CI 0.52-0.89)", "p = 0.002", "NNT = 12"],
        "secondary_results": "ICU滞在期間中央値はバソプレシン群8日 vs プラセボ群11日（p=0.03）。カテコラミン使用期間も有意に短縮。",
        "take_home": "小児敗血症性ショックでは、ノルアドレナリン開始後早期のバソプレシン追加が28日死亡率を有意に低下させる。NNT=12。ガイドラインへの反映が期待される。",
        "limitations": "- 単一民族（欧州）での試験で一般化可能性に限界\n- バソプレシン投与タイミングの個別最適化は未解明\n- 開放ラベル延長試験なし",
        "citation": "Smith J, et al. NEJM. 2025. doi:10.1056/test",
        "hashtags": ["PICU", "Sepsis", "Vasopressin", "小児敗血症", "RCT"],
        "authors": ["Smith J", "Doe A"], "doi": "10.1056/test",
    }
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "output"
    generate_carousel(sample, out_dir)
