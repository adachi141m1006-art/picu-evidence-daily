#!/usr/bin/env python3
"""
PubMed E-utilities を使って小児集中治療関連の最新論文を取得する。
NCBI API Key を設定すると rate limit が緩和される（10 req/s）。
"""

import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import requests

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "PICUEvidenceDaily/1.0"})

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# PCCM のみ: 全記事が PICU 関連
PICU_DEDICATED_JOURNALS = [
    '"Pediatric critical care medicine"[Journal]',
]

# ICU ジャーナル: 小児語を AND 必須
ICU_JOURNALS = [
    '"Intensive care medicine"[Journal]',
    '"Critical care medicine"[Journal]',
    '"Critical care"[Journal]',
]

# 高インパクト + 小児科ジャーナル: PICU コンテンツ語を AND 必須
GENERAL_JOURNALS = [
    '"The New England journal of medicine"[Journal]',
    '"Lancet"[Journal]',
    '"JAMA"[Journal]',
    '"BMJ"[Journal]',
    '"Pediatrics"[Journal]',
    '"JAMA pediatrics"[Journal]',
    '"The Journal of pediatrics"[Journal]',
    '"Archives of disease in childhood"[Journal]',
]

# Cochrane は MeSH でのみフィルタ（テキスト語では誤ヒットが多い）
COCHRANE_JOURNAL = '"The Cochrane database of systematic reviews"[Journal]'

# PICU コンテンツ語 ([tiab]) — 広すぎる語（oxygen, epinephrine 等）は除外
PICU_CONTENT_TERMS = [
    "critical care[tiab]",
    "intensive care[tiab]",
    "PICU[tiab]",
    "NICU[tiab]",
    "mechanical ventilation[tiab]",
    "mechanically ventilated[tiab]",
    "septic shock[tiab]",
    "sepsis[tiab]",
    "cardiac arrest[tiab]",
    "cardiopulmonary resuscitation[tiab]",
    "ECMO[tiab]",
    "extracorporeal membrane oxygenation[tiab]",
    "ARDS[tiab]",
    "acute respiratory distress[tiab]",
    "critically ill[tiab]",
    "vasopressor[tiab]",
    "vasoactive[tiab]",
    "vasopressin[tiab]",
    "fluid resuscitation[tiab]",
    "high flow nasal[tiab]",
    "high-flow nasal[tiab]",
    "bronchiolitis[tiab]",
    "status epilepticus[tiab]",
    "pediatric trauma[tiab]",
    "congenital heart disease[tiab]",
    "extubation[tiab]",
    "intubation[tiab]",
]

# Cochrane 専用 MeSH フィルタ（これだけで十分に PICU 特異的）
PICU_MESH_TERMS = [
    '"Intensive Care Units, Pediatric"[Mesh]',
    '"Critical Illness"[Mesh]',
    '"Sepsis"[Mesh]',
    '"Shock, Septic"[Mesh]',
    '"Respiration, Artificial"[Mesh]',
    '"Heart Arrest"[Mesh]',
    '"Cardiopulmonary Resuscitation"[Mesh]',
    '"Extracorporeal Membrane Oxygenation"[Mesh]',
    '"Respiratory Distress Syndrome"[Mesh]',
    '"Bronchiolitis"[Mesh]',
    '"Status Epilepticus"[Mesh]',
]

# 小児年齢語 ([tiab])
PEDIATRIC_TERMS = [
    "pediatric[tiab]",
    "paediatric[tiab]",
    "children[tiab]",
    "child[tiab]",
    "infant[tiab]",
    "neonatal[tiab]",
    "neonate[tiab]",
    '"Infant"[Mesh]',
    '"Child"[Mesh]',
    '"Adolescent"[Mesh]',
    '"Infant, Newborn"[Mesh]',
]

STUDY_TYPE_FILTERS = [
    "Randomized Controlled Trial[pt]",
    "Systematic Review[pt]",
    "Meta-Analysis[pt]",
    "Practice Guideline[pt]",
    "Clinical Trial[pt]",
]

# スコアリング用 PICU キーワード（タイトル/abstract全文検索）
_PICU_SCORE_KEYWORDS = [
    "critical care", "intensive care", "picu", "nicu",
    "mechanical ventilation", "septic shock", "sepsis",
    "cardiac arrest", "ecmo", "ards", "critically ill",
    "vasopressor", "vasopressin", "fluid resuscitation",
    "bronchiolitis", "status epilepticus", "congenital heart",
    "respiratory failure", "shock", "resuscitation",
]


def _date_filter(days_back):
    end_date   = datetime.now().strftime("%Y/%m/%d")
    start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y/%m/%d")
    return f'("{start_date}"[Date - Publication] : "{end_date}"[Date - Publication])'


def build_query(days_back=7):
    picu_content = " OR ".join(PICU_CONTENT_TERMS)
    picu_mesh    = " OR ".join(PICU_MESH_TERMS)
    pediatric    = " OR ".join(PEDIATRIC_TERMS)
    icu_j        = " OR ".join(ICU_JOURNALS)
    general_j    = " OR ".join(GENERAL_JOURNALS)
    picu_only_j  = " OR ".join(PICU_DEDICATED_JOURNALS)
    date_f       = _date_filter(days_back)

    query = (
        f"("
        # PCCM: 全記事
        f"  ({picu_only_j})"
        # ICU ジャーナル: 小児語 AND 必須
        f"  OR (({icu_j}) AND ({pediatric}))"
        # 高インパクト + 小児ジャーナル: PICU コンテンツ tiab AND 小児語 AND 必須
        f"  OR (({general_j}) AND ({picu_content}) AND ({pediatric}))"
        # Cochrane: PICU 専用 MeSH AND 小児語（テキストではなく MeSH でフィルタ）
        f"  OR (({COCHRANE_JOURNAL}) AND ({picu_mesh}) AND ({pediatric}))"
        f") AND {date_f}"
    )
    return query


def esearch(query, retmax=20, api_key=None):
    params = {
        "db":      "pubmed",
        "term":    query,
        "retmax":  retmax,
        "retmode": "json",
        "sort":    "date",
    }
    if api_key:
        params["api_key"] = api_key

    url  = f"{BASE}/esearch.fcgi"
    data = _SESSION.get(url, params=params, timeout=30).json()

    result = data.get("esearchresult", {})
    pmids  = result.get("idlist", [])
    count  = int(result.get("count", 0))
    print(f"[esearch] Found {count} articles, returning top {len(pmids)}")
    return pmids


def efetch(pmids, api_key=None):
    if not pmids:
        return []

    params = {
        "db":      "pubmed",
        "id":      ",".join(pmids),
        "retmode": "xml",
    }
    if api_key:
        params["api_key"] = api_key

    url      = f"{BASE}/efetch.fcgi"
    xml_data = _SESSION.get(url, params=params, timeout=30).content

    root     = ET.fromstring(xml_data)
    articles = []
    for elem in root.findall(".//PubmedArticle"):
        try:
            art = parse_article(elem)
            if art:
                articles.append(art)
        except Exception as e:
            print(f"[efetch] Parse error: {e}")
    return articles


def parse_article(elem):
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
    journal_title  = journal_elem.findtext(".//Title", "")         if journal_elem is not None else ""
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
            doi = eid.text
            break

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
    }


def classify_study_type(pub_types):
    tl = [pt.lower() for pt in pub_types]
    if any("meta-analysis"          in t for t in tl): return "Meta-Analysis"
    if any("systematic review"      in t for t in tl): return "Systematic Review"
    if any("randomized controlled"  in t for t in tl): return "RCT"
    if any("practice guideline" in t or "guideline" in t for t in tl): return "Guideline"
    if any("clinical trial"         in t for t in tl): return "Clinical Trial"
    if any("review"                 in t for t in tl): return "Review"
    if any("observational" in t or "cohort" in t for t in tl): return "Cohort Study"
    return "Original Article"


def score_article(article):
    score = 0

    design_scores = {
        "Meta-Analysis": 10, "Systematic Review": 9, "RCT": 8,
        "Guideline": 8, "Clinical Trial": 6, "Cohort Study": 5,
        "Review": 4, "Original Article": 3,
    }
    score += design_scores.get(article["study_type"], 3)

    journal = article.get("journal", "")
    if any(j in journal for j in ["N Engl J Med", "Lancet", "JAMA", "BMJ"]):
        score += 5
    elif any(j in journal for j in ["Pediatr Crit Care Med", "Intensive Care Med", "Crit Care Med"]):
        score += 4
    else:
        score += 2

    # PICU コンテンツマッチ数ボーナス（最大 5 点）
    haystack = (article.get("title_en", "") + " " + article.get("abstract", "")).lower()
    picu_hits = sum(1 for k in _PICU_SCORE_KEYWORDS if k in haystack)
    score += min(picu_hits, 5)

    # 小児語ヒットボーナス
    ped_hits = sum(1 for k in ["pediatric", "paediatric", "children", "infant", "neonatal"] if k in haystack)
    if ped_hits > 0:
        score += 2

    if len(article.get("abstract", "")) > 500:
        score += 2

    return score


def fetch_latest(days_back=7, top_n=5, api_key=None):
    for window in [days_back, days_back * 2, 30]:
        query = build_query(days_back=window)
        print(f"[PubMed] Query (days={window}): {query[:120]}...")
        pmids = esearch(query, retmax=30, api_key=api_key)
        if pmids:
            break
        print(f"[PubMed] No results. Expanding window to {window * 2} days...")

    articles = efetch(pmids, api_key=api_key)
    print(f"[PubMed] Fetched {len(articles)} articles")

    for art in articles:
        art["_score"] = score_article(art)
    articles.sort(key=lambda a: a["_score"], reverse=True)

    return articles[:top_n]


def save_articles(articles, output_dir="data"):
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
    articles = fetch_latest(days_back=14, top_n=5, api_key=api_key)
    for i, art in enumerate(articles, 1):
        print(f"\n--- #{i} (score={art['_score']}) ---")
        print(f"  PMID: {art['pmid']}")
        print(f"  Type: {art['study_type']}")
        print(f"  Journal: {art['journal']}")
        print(f"  Title: {art['title_en'][:100]}")
