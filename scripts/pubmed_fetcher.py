#!/usr/bin/env python3
"""
PubMed E-utilities を使って小児・集中治療関連の最新論文を取得・スコアリングする。
"""

import re
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import requests

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "PICUEvidenceDaily/1.0"})
BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# ============================================================
# ジャーナルリスト
# ============================================================

# 小児専用ジャーナル（全記事対象。小児語フィルタ不要）
PEDIATRIC_JOURNALS = [
    '"Pediatric critical care medicine"[Journal]',
    '"JAMA pediatrics"[Journal]',
    '"Pediatrics"[Journal]',
    '"Lancet child & adolescent health"[Journal]',
    '"The Journal of pediatrics"[Journal]',
    '"Archives of disease in childhood"[Journal]',
    '"Pediatric pulmonology"[Journal]',
    '"Pediatric emergency care"[Journal]',
    '"Neonatology"[Journal]',
    '"Pediatric research"[Journal]',
    '"European journal of pediatrics"[Journal]',
    '"Journal of pediatric intensive care"[Journal]',
    '"Pediatric infectious disease journal"[Journal]',
    '"Pediatric nephrology"[Journal]',
    '"Pediatric cardiology"[Journal]',
    '"Pediatric neurology"[Journal]',
    '"Journal of pediatric surgery"[Journal]',
    '"Pediatric emergency care and communications"[Journal]',
]

# 汎用・集中治療・救急・呼吸器ジャーナル（小児語フィルタ必要）
GENERAL_ICU_JOURNALS = [
    '"The New England journal of medicine"[Journal]',
    '"Lancet"[Journal]',
    '"JAMA"[Journal]',
    '"BMJ"[Journal]',
    '"Nature medicine"[Journal]',
    '"Intensive care medicine"[Journal]',
    '"Critical care medicine"[Journal]',
    '"Critical care"[Journal]',
    '"American journal of respiratory and critical care medicine"[Journal]',
    '"Chest"[Journal]',
    '"Annals of emergency medicine"[Journal]',
    '"Resuscitation"[Journal]',
    '"JAMA network open"[Journal]',
    '"eClinicalMedicine"[Journal]',
    '"BMJ medicine"[Journal]',
    '"PLOS medicine"[Journal]',
    '"Annals of internal medicine"[Journal]',
    '"European respiratory journal"[Journal]',
    '"Clinical infectious diseases"[Journal]',
    '"The Cochrane database of systematic reviews"[Journal]',
    '"Anesthesiology"[Journal]',
    '"Anesthesia and analgesia"[Journal]',
    '"The Journal of allergy and clinical immunology"[Journal]',
    '"Infection"[Journal]',
]

PEDIATRIC_TERMS = [
    "pediatric[tiab]", "paediatric[tiab]",
    "children[tiab]", "child[tiab]",
    "infant[tiab]", "neonatal[tiab]", "neonate[tiab]",
    "newborn[tiab]", "adolescent[tiab]",
    '"Child"[Mesh]', '"Infant"[Mesh]', '"Adolescent"[Mesh]',
    '"Infant, Newborn"[Mesh]', '"Intensive Care Units, Pediatric"[Mesh]',
]

# ============================================================
# スコアリング設定
# ============================================================

# ジャーナルの略称（ISO abbreviation）→ スコア
JOURNAL_SCORES = {
    # Tier 1: Top general (+10)
    "N Engl J Med": 10, "Lancet": 10, "JAMA": 10, "BMJ": 10, "Nat Med": 10,
    # Tier 2: Top pediatric (+9)
    "JAMA Pediatr": 9, "Pediatrics": 9, "Lancet Child Adolesc Health": 9,
    # Tier 3: High-quality clinical/open (+8)
    "JAMA Netw Open": 8, "eClinicalMedicine": 8, "BMJ Med": 8,
    "PLoS Med": 7, "Ann Intern Med": 8, "Clin Infect Dis": 7,
    # Tier 4: Critical care / emergency / respiratory (+7-9)
    "Intensive Care Med": 9, "Crit Care Med": 9, "Crit Care": 8,
    "Am J Respir Crit Care Med": 8, "Chest": 7, "Ann Emerg Med": 8,
    "Resuscitation": 7, "Eur Respir J": 7,
    # Tier 5: Pediatric subspecialty (+6-8)
    "Pediatr Crit Care Med": 8, "J Pediatr": 7, "Arch Dis Child": 8,
    "Pediatr Pulmonol": 7, "Pediatr Emerg Care": 6, "Neonatology": 7,
    "Pediatr Res": 6, "Eur J Pediatr": 6, "Pediatr Infect Dis J": 7,
    "Pediatr Cardiol": 6, "J Pediatr Surg": 6, "Pediatr Neurol": 6,
    "Anesthesiology": 7, "Anesth Analg": 6,
}

DESIGN_SCORES = {
    "Guideline":        10,
    "Meta-Analysis":     9,
    "Systematic Review": 9,
    "RCT":               8,
    "Clinical Trial":    7,
    "Cohort Study":      6,
    "Review":            3,
    "Original Article":  4,
}

# PICU関連性キーワード（加点条件）
_PICU_CORE = [
    "picu", "pediatric icu", "pediatric intensive care",
    "mechanical ventilation", "mechanically ventilated",
    "ecmo", "extracorporeal membrane oxygenation",
    "vasopressor", "vasoactive", "vasopressin", "norepinephrine",
    "cardiac arrest", "cardiopulmonary resuscitation", "cpr",
    "septic shock", "sepsis", "ards", "acute respiratory distress",
    "critically ill", "fluid resuscitation",
]
_PICU_ADJACENT = [
    "nicu", "neonatal icu", "emergency department",
    "high-flow nasal", "high flow nasal",
    "bronchiolitis", "status epilepticus", "status asthmaticus",
    "congenital heart", "respiratory failure",
    "intubation", "extubation", "weaning", "reintubation",
    "oxygen therapy", "sedation", "analgesia", "delirium",
    "enteral nutrition", "parenteral nutrition",
    "acute kidney injury", "diabetic ketoacidosis", "dka",
]
_PEDIATRIC_CLINICAL = [
    "fever", "febrile", "seizure", "meningitis", "pneumonia",
    "asthma", "croup", "trauma", "drowning", "airway management",
    "resuscitation", "anaphylaxis", "kawasaki", "appendicitis",
]

# 長期的価値キーワード
_LANDMARK_TERMS = [
    "landmark", "practice changing", "practice-changing",
    "guideline", "consensus", "clinical practice guideline",
    "highly cited", "updated guideline", "seminal",
]

# 除外キーワード（動物実験・基礎研究）
_EXCLUDE_ABS = [
    "mouse model", "murine", "rat model", "animal model",
    "in vitro", "cell culture", "molecular mechanism",
    "gene expression", "knockout mice", "zebrafish",
]


def _date_filter(days_back: int) -> str:
    end   = datetime.now().strftime("%Y/%m/%d")
    start = (datetime.now() - timedelta(days=days_back)).strftime("%Y/%m/%d")
    return f'("{start}"[Date - Publication] : "{end}"[Date - Publication])'


def build_query(days_back: int = 30, landmark_only: bool = False) -> str:
    ped_j  = " OR ".join(PEDIATRIC_JOURNALS)
    gen_j  = " OR ".join(GENERAL_ICU_JOURNALS)
    ped    = " OR ".join(PEDIATRIC_TERMS)
    date_f = _date_filter(days_back)

    base = f"(({ped_j}) OR (({gen_j}) AND ({ped}))) AND {date_f}"

    if landmark_only:
        # 5年超を検索するときは高品質デザインのみに絞る
        design_filter = (
            "(Randomized Controlled Trial[pt] OR Systematic Review[pt] "
            "OR Meta-Analysis[pt] OR Practice Guideline[pt])"
        )
        base += f" AND {design_filter}"

    return base


def esearch(query: str, retmax: int = 50, api_key: str = None) -> list:
    params = {
        "db": "pubmed", "term": query,
        "retmax": retmax, "retmode": "json", "sort": "date",
    }
    if api_key:
        params["api_key"] = api_key
    data   = _SESSION.get(f"{BASE}/esearch.fcgi", params=params, timeout=30).json()
    result = data.get("esearchresult", {})
    pmids  = result.get("idlist", [])
    count  = int(result.get("count", 0))
    print(f"[esearch] {count} hits → returning {len(pmids)}")
    return pmids


def efetch(pmids: list, api_key: str = None) -> list:
    if not pmids:
        return []
    params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"}
    if api_key:
        params["api_key"] = api_key
    xml_data = _SESSION.get(f"{BASE}/efetch.fcgi", params=params, timeout=30).content
    root     = ET.fromstring(xml_data)
    articles = []
    for elem in root.findall(".//PubmedArticle"):
        try:
            art = parse_article(elem)
            if art:
                articles.append(art)
        except Exception as e:
            print(f"[efetch] parse error: {e}")
    return articles


def parse_article(elem) -> dict:
    medline = elem.find(".//MedlineCitation")
    article = medline.find(".//Article")
    if article is None:
        return None

    pmid  = medline.findtext(".//PMID", "")
    title = article.findtext(".//ArticleTitle", "")

    abstract_parts = []
    abstract_elem  = article.find(".//Abstract")
    if abstract_elem is not None:
        for at in abstract_elem.findall(".//AbstractText"):
            label = at.get("Label", "")
            text  = "".join(at.itertext())
            abstract_parts.append(f"{label}: {text}" if label else text)
    abstract = "\n".join(abstract_parts)

    journal_elem   = article.find(".//Journal")
    journal_title  = journal_elem.findtext(".//Title", "")          if journal_elem is not None else ""
    journal_abbrev = journal_elem.findtext(".//ISOAbbreviation", "") if journal_elem is not None else ""

    pub_date = article.find(".//ArticleDate")
    if pub_date is None:
        pub_date = journal_elem.find(".//PubDate") if journal_elem is not None else None
    year  = pub_date.findtext("Year",  "") if pub_date is not None else ""
    month = pub_date.findtext("Month", "") if pub_date is not None else ""

    authors = []
    author_list = article.find(".//AuthorList")
    if author_list is not None:
        for author in author_list.findall("Author"):
            last     = author.findtext("LastName", "")
            initials = author.findtext("Initials", "")
            if last:
                authors.append(f"{last} {initials}")

    pub_types = [pt.text for pt in article.findall(".//PublicationTypeList/PublicationType")]

    doi = ""
    for eid in article.findall(".//ELocationID"):
        if eid.get("EIdType") == "doi":
            doi = eid.text or ""
            break

    try:
        year_int = int(year)
    except (ValueError, TypeError):
        year_int = 0
    days_old = max(0, (datetime.now().year - year_int) * 365) if year_int else 9999

    return {
        "pmid":         pmid,
        "title_en":     title,
        "abstract":     abstract,
        "journal":      journal_abbrev or journal_title,
        "journal_full": journal_title,
        "year":         year,
        "month":        month,
        "authors":      authors,
        "pub_types":    pub_types,
        "study_type":   classify_study_type(pub_types),
        "doi":          doi,
        "days_old":     days_old,
    }


def normalize_title(title: str) -> str:
    """タイトル正規化（大文字小文字・記号・末尾ピリオド等を吸収）"""
    t = title.lower()
    t = re.sub(r'[^\w\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def classify_study_type(pub_types: list) -> str:
    tl = [pt.lower() for pt in pub_types]
    if any("meta-analysis"         in t for t in tl): return "Meta-Analysis"
    if any("systematic review"     in t for t in tl): return "Systematic Review"
    if any("randomized controlled" in t for t in tl): return "RCT"
    if any("practice guideline" in t or "guideline" in t for t in tl): return "Guideline"
    if any("clinical trial"        in t for t in tl): return "Clinical Trial"
    if any("review"                in t for t in tl): return "Review"
    if any("cohort" in t or "observational" in t     for t in tl): return "Cohort Study"
    return "Original Article"


def score_article(article: dict) -> int:
    haystack = (article.get("title_en", "") + " " + article.get("abstract", "")).lower()

    # --- 除外チェック ---
    if any(t in haystack for t in _EXCLUDE_ABS):
        return -999
    if len(article.get("abstract", "")) < 100:
        return -999  # Abstract なし・極端に短い

    score = 0

    # --- ジャーナルスコア ---
    j = article.get("journal", "")
    j_score = 2  # デフォルト（低IF・無名誌）
    for key, val in JOURNAL_SCORES.items():
        if key.lower() in j.lower():
            j_score = val
            break
    score += j_score

    # --- 研究デザインスコア ---
    score += DESIGN_SCORES.get(article["study_type"], 3)

    # 多施設ボーナス
    if any(t in haystack for t in ["multicenter", "multi-center", "multicentre", "multi-centre"]):
        score += 1

    # --- PICU関連性スコア（加点のみ・必須でない） ---
    if any(t in haystack for t in _PICU_CORE):
        score += 8
    elif any(t in haystack for t in _PICU_ADJACENT):
        score += 6
    elif any(t in haystack for t in _PEDIATRIC_CLINICAL):
        score += 4

    # --- 鮮度スコア ---
    days = article.get("days_old", 9999)
    if   days <= 7:    score += 5
    elif days <= 30:   score += 4
    elif days <= 90:   score += 3
    elif days <= 365:  score += 2
    elif days <= 1825: score += 1

    # --- 長期的価値スコア ---
    if any(t in haystack for t in _LANDMARK_TERMS):
        score += 5

    # --- Abstract充実度 ---
    if len(article.get("abstract", "")) > 500:
        score += 2

    return score


def fetch_latest(days_back: int = 30, top_n: int = 5, api_key: str = None) -> list:
    """3段階検索: 30日 → 90日 → 5年（landmark限定）"""
    MIN_CANDIDATES = 3

    for window, landmark_only in [(days_back, False), (90, False), (365 * 5, True)]:
        query = build_query(days_back=window, landmark_only=landmark_only)
        print(f"[PubMed] Searching days={window} landmark_only={landmark_only}...")
        pmids = esearch(query, retmax=50, api_key=api_key)
        if pmids:
            break
        print(f"[PubMed] No results, expanding window...")

    articles = efetch(pmids, api_key=api_key)
    print(f"[PubMed] Fetched {len(articles)} articles")

    for art in articles:
        art["_score"] = score_article(art)

    articles = [a for a in articles if a["_score"] > 0]
    articles.sort(key=lambda a: a["_score"], reverse=True)

    return articles[:top_n]


def save_articles(articles: list, output_dir: str = "data") -> Path:
    out      = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    filepath = out / f"articles_{date_str}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"[PubMed] Saved {len(articles)} articles to {filepath}")
    return filepath


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
    import os
    api_key  = os.environ.get("NCBI_API_KEY")
    articles = fetch_latest(days_back=30, top_n=5, api_key=api_key)
    for i, art in enumerate(articles, 1):
        print(f"\n--- #{i} (score={art['_score']}) ---")
        print(f"  PMID:    {art['pmid']}")
        print(f"  Type:    {art['study_type']}")
        print(f"  Journal: {art['journal']}")
        print(f"  Title:   {art['title_en'][:100]}")
