#!/usr/bin/env python3
"""
PICU Evidence Daily — Gemini Imagen 3 Infographic Generator
Imagen 3 API で各スライドを丸ごとAI画像生成。
取得方法: https://aistudio.google.com/apikey
環境変数: GEMINI_API_KEY
"""

import io, os
from pathlib import Path
from PIL import Image

try:
    from google import genai
    from google.genai import types
    HAS_IMAGEN = True
except ImportError:
    HAS_IMAGEN = False

# ─── スタディタイプ別カラー ────────────────────────────────────────────────
STUDY_COLORS = {
    "RCT":               ("deep crimson red",  "#DC2626", "red"),
    "Systematic Review": ("deep violet purple", "#7C3AED", "purple"),
    "Meta-Analysis":     ("deep violet purple", "#7C3AED", "purple"),
    "Cohort Study":      ("deep forest green",  "#059669", "green"),
    "Guideline":         ("deep royal blue",    "#2563EB", "blue"),
    "Review":            ("deep violet purple", "#7C3AED", "purple"),
    "Case Series":       ("deep forest green",  "#059669", "green"),
}

def sc(st):
    return STUDY_COLORS.get(st, ("deep amber orange", "#D97706", "amber"))


def _stats(d, i):
    s = d.get('stats', [])
    return s[i] if len(s) > i else ''


# ─── スライド別プロンプト ───────────────────────────────────────────────────

def prompt_s1(d):
    st = d.get('study_type','RCT')
    col_name, col_hex, _ = sc(st)
    sa, sb = d.get('stat_a',''), d.get('stat_b','')
    compare = ""
    if sa and sb:
        compare = f"""
STATISTICS SECTION - Two side-by-side boxes with rounded corners:
  LEFT BOX (semi-transparent red tint, red border):
    Giant number: "{sa}"
    Small label below: "{d.get('stat_a_label','介入群')}"
  CENTER: Bold "vs" in pale gray
  RIGHT BOX (semi-transparent blue tint, blue border):
    Giant number: "{sb}"
    Small label below: "{d.get('stat_b_label','対照群')}"
  Context text centered: "{d.get('stat_context','')}"
"""
    stats_row = " | ".join(filter(None, [_stats(d,0), _stats(d,1), _stats(d,2)]))

    return f"""
Professional medical education infographic slide for Instagram, portrait 4:5 ratio (1080x1350px).
Pure graphic design, no photos, no people.
Every pixel filled - absolutely zero empty white space.

BACKGROUND: Deep navy blue gradient (very dark #0F172A top to #1E3A8A bottom).
Two large translucent circles as decorative elements (top-right and bottom-left corners, subtle).

HEADER ROW (top of slide):
  Left: White bold text "PICU Evidence Daily"
  Right: Gray text "1 / 7"

BADGE + JOURNAL (below header):
  Pill-shaped badge in {col_name} with white text: "{st}"
  Beside it: Small light blue text "{d.get('journal','')} · {d.get('year','')}"
  Thin white horizontal divider line below

LABEL (small, amber/gold color, uppercase letter-spaced):
  "KEY  FINDING"

HERO TEXT (dominant element, takes ~35% of slide height):
  Very large bold white Japanese text:
  "{d.get('key_finding','')}"

DIVIDER: Thin white line

{compare}

STATS ROW (three small colored rounded rectangles side by side):
  "{_stats(d,0)}" | "{_stats(d,1)}" | "{_stats(d,2)}"

TITLE SECTION:
  Medium bold light-blue Japanese text: "{d.get('title_jp','')}"
  Tiny gray text: "{d.get('title_en','')[:60]}"

SWIPE CTA:
  Centered white text with top border line:
  "スライドをスワイプして詳細を見る  ▶"

FOOTER STRIP (bottom, slightly darker navy band, 70px tall):
  Centered light-blue text: "📰 {d.get('journal','')}  ·  {d.get('year','')}  ·  {st}"

Style: Modern, clean, impactful, professional medical design. Dark mode aesthetic.
"""


def prompt_s2(d):
    st = d.get('study_type','RCT')
    col_name, col_hex, _ = sc(st)
    return f"""
Professional medical education infographic slide for Instagram, portrait 4:5 ratio (1080x1350px).
Pure graphic design only. Zero empty white space — background color fills every pixel.

BACKGROUND: Solid {col_name} ({col_hex}), rich saturated color covering entire slide.
DECORATIVE ELEMENT: Enormous semi-transparent white quotation mark character (")
  positioned at top-left, very large (~400px), almost fills left half, opacity 5-8%.

HEADER ROW (top):
  Left: White bold "PICU Evidence Daily"
  Right: White "2 / 7" (slightly transparent)

BADGE ROW:
  White pill badge with {col_name} text: "{st}"
  Small white text: "{d.get('journal','')}  ·  {d.get('year','')}  ·  {d.get('design','')}"

MAIN CONTENT (center, takes 60% of height, vertically centered):
  Small amber/gold uppercase spaced label:
  "KEY  FINDING"

  VERY LARGE bold white Japanese text — hero element, maximum readable size:
  "{d.get('key_finding','')}"
  (Make this text as large as possible while keeping it fully visible)

BOTTOM SECTION:
  Thin white horizontal divider line
  Medium white Japanese text (70% opacity):
  "{d.get('title_jp','')}"

FOOTER: Slightly darker translucent strip at very bottom.
  Centered white text (60% opacity):
  "📰 {d.get('journal','')} · {d.get('year','')} · {st}"

Style: Bold, confident, typographic poster aesthetic. The colored background IS the design.
"""


def prompt_s3(d):
    return f"""
Professional medical education infographic slide for Instagram, portrait 4:5 ratio (1080x1350px).
Pure graphic design. Absolutely no empty white space.

LAYOUT: Two horizontal color blocks stacked vertically.

TOP BLOCK (~55% of height, dark navy #0F172A background):
  HEADER ROW: White "PICU Evidence Daily" left, gray "3 / 7" right.

  TITLE BAND (below header, dark royal blue #1E3A8A background, 60px tall):
    Large bold white Japanese text: "なぜこの研究？"

  CONTENT AREA (fills rest of top block, dark background):
    Small bright blue uppercase label: "BACKGROUND"
    Medium white Japanese text (line height 1.6):
    "{d.get('background','')}"

THIN DIVIDER: 3px gradient line (blue to purple)

BOTTOM BLOCK (~45% of height, dark blue #1E3A8A background):
  Small light blue uppercase label: "対象患者  /  POPULATION"
  Medium white Japanese text (line height 1.6):
  "{d.get('population','')}"

FOOTER STRIP (bottom 70px, very dark navy):
  Centered light blue text: "📰 {d.get('journal','')} · {d.get('year','')} · {d.get('study_type','')}"

Style: Two-tone dark design. Bold and informative. Every inch used.
"""


def prompt_s4(d):
    pico = [
        ("P", "Population",   d.get('population',''),   "royal blue",  "#1D4ED8", "#DBEAFE"),
        ("I", "Intervention", d.get('intervention',''), "crimson red", "#DC2626", "#FEE2E2"),
        ("C", "Comparison",   d.get('comparison',''),   "amber brown", "#D97706", "#FEF3C7"),
        ("O", "Outcome",      d.get('outcome',''),      "forest green","#059669", "#D1FAE5"),
    ]
    rows_desc = ""
    for letter, label, value, col_name, col_hex, bg_hex in pico:
        if value:
            rows_desc += f"""
  ROW "{letter}" ({col_name}):
    LEFT STRIP (80px wide, solid {col_name} {col_hex} background):
      Large bold white letter "{letter}" centered
      Small white vertical label "{label}"
    RIGHT AREA ({bg_hex} light background):
      Japanese text: "{value}"
"""

    design = d.get('design','')
    return f"""
Professional medical education infographic slide for Instagram, portrait 4:5 ratio (1080x1350px).
Pure graphic design. Zero empty white space.

BACKGROUND: Very light gray #F8FAFC

HEADER (white/light background):
  Purple top accent bar (8px, full width)
  "PICU Evidence Daily" in purple left, "4 / 7" in gray right
  Thin gray divider line

TITLE ROW:
  Large bold purple text: "PICO  /  Methods"
  Purple pill badge: "{design}"

PICO ROWS (4 equal-height horizontal strips, fill remaining height):
  Each row: colored left strip + content area
{rows_desc}

Rows separated by 3px gaps.

FOOTER STRIP (bottom 70px, dark navy #1E3A8A):
  Light blue text: "📰 {d.get('journal','')} · {d.get('year','')} · {d.get('study_type','')}"

Style: Structured table-like design. Color-coded rows make P-I-C-O instantly clear.
"""


def prompt_s5(d):
    sa, sb = d.get('stat_a',''), d.get('stat_b','')
    stats_text = "  ·  ".join(filter(None, [_stats(d,0), _stats(d,1), _stats(d,2)]))

    compare_section = ""
    if sa and sb:
        compare_section = f"""
GIANT COMPARISON (takes ~45% of content height):
  Context label centered: "{d.get('stat_context','')}"
  Two boxes side by side:
    LEFT (red glow, dark red border, translucent red bg):
      Enormous number "{sa}" in bright red
      Label "{d.get('stat_a_label','介入群')}" in red
    CENTER: "vs" in pale gray
    RIGHT (blue glow, dark blue border, translucent blue bg):
      Enormous number "{sb}" in bright blue
      Label "{d.get('stat_b_label','対照群')}" in blue
"""

    return f"""
Professional medical education infographic slide for Instagram, portrait 4:5 ratio (1080x1350px).
Pure graphic design. Dark mode. Zero empty space.

BACKGROUND: Very dark #0F172A (near black), entire slide.
Subtle red-tinted decorative circle top-right (translucent, large).

HEADER:
  White "PICU Evidence Daily" left, gray "5 / 7" right.

TITLE:
  Large bold red text with chart emoji: "📊  Results"

{compare_section}

PRIMARY OUTCOME SECTION (fills remaining height):
  Left border: 4px solid red vertical bar
  Dark red translucent background, rounded right corners
  Small red uppercase label: "PRIMARY OUTCOME"
  Medium white Japanese text:
  "{d.get('primary_result','')}"

  STATS PILLS ROW (3 pills, bottom of section):
    "{_stats(d,0)}" | "{_stats(d,1)}" | "{_stats(d,2)}"
    Each pill: dark translucent bg, white text

FOOTER STRIP (bottom 70px, even darker #070B14):
  Light blue: "📰 {d.get('journal','')} · {d.get('year','')} · {d.get('study_type','')}"

Style: Dark, dramatic, data-focused. Numbers are the star.
"""


def prompt_s6(d):
    stats = d.get('stats', [])
    stats_desc = ""
    dot_colors = ["crimson red", "royal blue", "forest green", "violet purple", "amber orange", "slate gray"]
    for i, s in enumerate(stats[:6]):
        col = dot_colors[i % len(dot_colors)]
        stats_desc += f'  Card {i+1} ({col} accent): "{s}"\n'

    secondary = d.get('secondary_results','')
    sec_section = ""
    if secondary:
        sec_section = f"""
SECONDARY OUTCOMES CARD (bottom, green accent, light green bg):
  Small green label: "副次アウトカム"
  Japanese text: "{secondary}"
"""

    return f"""
Professional medical education infographic slide for Instagram, portrait 4:5 ratio (1080x1350px).
Pure graphic design. Light mode. Zero empty white space.

BACKGROUND: Very light gray #F8FAFC

HEADER:
  Amber/orange top accent bar (8px full width)
  "PICU Evidence Daily" in amber left, "6 / 7" in gray right
  Thin gray divider

TITLE:
  Large bold amber text: "📈  Statistics"

STATISTICS CARDS (vertical stack, fills available height):
  Each card: rounded rectangle, colored left border (4px), light tinted background
  Card content: colored dot + bold Japanese/English stat text + progress bar if percentage
{stats_desc}

{sec_section}

FOOTER STRIP (bottom 70px, dark navy):
  Light blue: "📰 {d.get('journal','')} · {d.get('year','')} · {d.get('study_type','')}"

Style: Clean list of evidence. Color-coded cards make each stat visually distinct.
"""


def prompt_s7(d):
    lim = d.get('limitations','')
    lim_text = '\n'.join(l.strip() for l in lim.split('\n') if l.strip())
    return f"""
Professional medical education infographic slide for Instagram, portrait 4:5 ratio (1080x1350px).
Pure graphic design. Dark mode. Zero empty space.

BACKGROUND: Deep navy gradient (#0F172A top to #1E3A8A bottom), full slide.
Large translucent circle decorative element bottom-right.

HEADER:
  White "PICU Evidence Daily" left, light gray "7 / 7" right.

TITLE:
  White text with emoji: "💡  Take Home Message"

CLINICAL IMPLICATION SECTION (fills ~55% of remaining height):
  Small blue uppercase label: "CLINICAL IMPLICATION"
  VERY LARGE bold white Japanese text:
  "{d.get('take_home','')}"
  (Make this as large as possible while keeping fully visible)

LIMITATIONS CARD (translucent white border, ~25% of height):
  Small gray uppercase label: "LIMITATIONS"
  Smaller white/gray Japanese text:
  "{lim_text}"

CITATION (tiny text):
  Gray: "{d.get('citation','')}"

FOOTER / CTA (bottom 72px, very dark #1E1B4B):
  Blue rounded rectangle button centered:
  "💾 保存して後で読み返そう  ·  フォローで最新エビデンスを 🔔"

Style: Dark, authoritative, memorable final slide. Large take-home text dominates.
"""


# ─── メイン生成ロジック ────────────────────────────────────────────────────

def _call_imagen(client, prompt: str, path: str):
    """Gemini image generation API を呼び出して画像を保存"""
    # Gemini 2.5 Flash Image (generateContent API)
    response = client.models.generate_content(
        model='gemini-2.5-flash-image',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=['IMAGE', 'TEXT'],
        )
    )
    # レスポンスから画像データを取得
    img_bytes = None
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            img_bytes = part.inline_data.data
            break
    if img_bytes is None:
        raise ValueError("画像データがレスポンスに含まれていません")

    img = Image.open(io.BytesIO(img_bytes))
    # 正確に 1080x1350 にリサイズ（中央クロップ）
    w, h = img.size
    target_h = int(w * 1350 / 1080)
    if h > target_h:
        top = (h - target_h) // 2
        img = img.crop((0, top, w, top + target_h))
    img = img.resize((1080, 1350), Image.LANCZOS)
    img.save(path, 'PNG', quality=95)
    return path


def _normalize(data):
    d = dict(data)
    for f in ["population","limitations","background","intervention","comparison",
              "outcome","primary_result","secondary_results","take_home",
              "key_finding","title_jp","title_en"]:
        v = d.get(f,"")
        if isinstance(v, list): d[f] = "\n".join(str(x) for x in v)
        elif not isinstance(v, str): d[f] = str(v) if v else ""
    return d


def generate_carousel(data, output_dir="output"):
    if not HAS_IMAGEN:
        raise RuntimeError("pip install google-genai")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY が未設定です。.env に追加してください。\n取得: https://aistudio.google.com/apikey")

    client = genai.Client(api_key=api_key)
    data   = _normalize(data)
    out    = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    pmid   = data.get("pmid","unknown")
    prefix = f"pmid_{pmid}"

    prompts = [
        ("Hook",         prompt_s1(data)),
        ("Key Finding",  prompt_s2(data)),
        ("Background",   prompt_s3(data)),
        ("PICO",         prompt_s4(data)),
        ("Results",      prompt_s5(data)),
        ("Statistics",   prompt_s6(data)),
        ("Take Home",    prompt_s7(data)),
    ]

    paths = []
    for i, (name, prompt) in enumerate(prompts, 1):
        path = out / f"{prefix}_slide{i}.png"
        print(f"  [{i}/7] {name}... ", end="", flush=True)
        try:
            _call_imagen(client, prompt, str(path))
            print("done")
        except Exception as e:
            print(f"ERROR: {e}")
            raise
        paths.append(path)

    print(f"Generated {len(paths)} slides -> {out}/")
    return paths


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")

    sample = {
        "pmid":"imagen_test","study_type":"RCT","journal":"NEJM","year":"2025",
        "title_jp":"小児敗血症性ショックに対する早期バソプレシン投与の有効性",
        "title_en":"Early Vasopressin in Pediatric Septic Shock: A Randomized Controlled Trial",
        "key_finding":"早期バソプレシン追加により28日死亡率が有意に低下した（18.2% vs 26.7%, p=0.002）",
        "background":"小児敗血症性ショックでは、ノルアドレナリン不応性の血管拡張が予後不良因子となる。成人領域ではバソプレシンの早期併用が推奨されているが、小児での大規模RCTは存在しなかった。",
        "population":"生後1ヶ月-17歳の敗血症性ショック患児 (n=1,200)、28施設の小児ICU",
        "intervention":"ノルアドレナリン開始後6時間以内にバソプレシン 0.0003-0.002 U/kg/min を追加",
        "comparison":"生理食塩水（プラセボ）を追加",
        "outcome":"28日全死亡率（主要）、臓器障害日数、カテコラミン使用期間（副次）",
        "design":"Multicenter double-blind placebo-controlled RCT",
        "primary_result":"28日死亡率はバソプレシン群18.2% vs プラセボ群26.7%、絶対リスク差-8.5% (95%CI: -13.1〜-3.9%, p=0.002)。NNT=12。",
        "stat_a":"18.2%","stat_a_label":"バソプレシン群",
        "stat_b":"26.7%","stat_b_label":"プラセボ群","stat_context":"28日死亡率",
        "stats":["HR 0.68 (95%CI 0.52-0.89)","p = 0.002","NNT = 12"],
        "secondary_results":"ICU滞在期間中央値はバソプレシン群8日 vs プラセボ群11日（p=0.03）。",
        "take_home":"小児敗血症性ショックでは、ノルアドレナリン開始後早期のバソプレシン追加が28日死亡率を有意に低下させる。NNT=12。ガイドラインへの反映が期待される。",
        "limitations":"- 単一民族（欧州）での試験\n- バソプレシン投与タイミングの個別最適化は未解明\n- 開放ラベル延長試験なし",
        "citation":"Smith J, et al. NEJM. 2025. doi:10.1056/test",
        "authors":["Smith J"],"doi":"10.1056/test",
    }
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "output"
    generate_carousel(sample, out_dir)
