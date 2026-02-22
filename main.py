from argparse import ArgumentParser
from dataclasses import dataclass, asdict, field
from typing import Optional, List, Tuple
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
from pathlib import Path
import json
import csv


def fetch_html(url: str, timeout: int = 30) -> str:
    headers = {
        "User-Agent": "foa-ingestor/0.1 (minimal script)",
        "Accept": "text/html,application/xhtml+xml",
    }
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text



def clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def to_iso_date(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = clean_text(s)
    for fmt in ("%m/%d/%Y", "%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return s 

def extract_title(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if h1:
        t = clean_text(h1.get_text(" ", strip=True))
        if t:
            return t
    if soup.title:
        t = clean_text(soup.title.get_text(" ", strip=True))
        if t:
            return t
    return ""


def extract_opportunity_id(url: str) -> Optional[str]:
    m = re.search(r"/search-results-detail/(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"/opportunity/([0-9a-fA-F-]{16,})", url)
    if m:
        return m.group(1)
    return None


LABELS = [
    "Agency",
    "Assistance Listings",
    "Posted date",
    "Closing",
    "Close date",
    "Closing date",
    "Archive date",
    "Funding opportunity number",
    "Cost sharing or matching requirement",
    "Funding instrument type",
    "Opportunity Category",
    "Opportunity Category Explanation",
    "Category of Funding Activity",
    "Category Explanation",
    "Last Updated",
]


def find_label(text: str, label: str) -> Optional[str]:
    other_labels = [l for l in LABELS if l.lower() != label.lower()]
    stop = "|".join(re.escape(l) for l in other_labels)
    pattern = rf"{re.escape(label)}\s*:\s*(.*?)(?=\s*(?:{stop})\s*:|$)"
    m = re.search(pattern, text, flags=re.IGNORECASE)
    return clean_text(m.group(1)) if m else None


def extract_links(soup: BeautifulSoup) -> Tuple[List[str], List[str]]:
    external_links: List[str] = []
    documents: List[str] = []

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        if href.startswith("http"):
            low = href.lower()
            if low.endswith(".pdf") or ".pdf?" in low:
                documents.append(href)
            else:
                external_links.append(href)

    return external_links, documents


TAG_RULES = [
    ("health_biomed", ["health", "cdc", "nih", "disease", "registry"]),
    ("ai_ml", ["machine learning", "artificial intelligence", "deep learning", "llm", "nlp"]),
    ("cybersecurity", ["cyber", "ransomware", "phishing", "zero trust", "infosec"]),
    ("education", ["education", "teacher", "school", "curriculum"]),
    ("climate_environment", ["climate", "environment", "sustainability", "emissions"]),
    ("energy", ["energy", "renewable", "solar", "wind", "grid", "battery"]),
]


def apply_tags(opp: "Opportunity") -> None:
    hay = " ".join(
        [
            opp.opportunity_title or "",
            opp.agency_name or "",
            opp.category or "",
            " ".join(opp.funding_categories or []),
            opp.applicant_eligibility_description or "",
        ]
    ).lower()

    tags: List[str] = []
    for tag, kws in TAG_RULES:
        if any(kw in hay for kw in kws):
            tags.append(tag)

    if opp.close_date:
        tags.append("has_deadline")
    if opp.is_cost_sharing is True:
        tags.append("cost_sharing")

    seen = set()
    out = []
    for t in tags:
        if t not in seen:
            out.append(t)
            seen.add(t)
    opp.tags = out


@dataclass
class Opportunity:
    opportunity_id: Optional[str] = None
    opportunity_number: Optional[str] = None
    opportunity_title: Optional[str] = None
    opportunity_status: Optional[str] = None
    agency_code: Optional[str] = None
    category: Optional[str] = None
    category_explanation: Optional[str] = None
    post_date: Optional[str] = None
    close_date: Optional[str] = None
    close_date_description: Optional[str] = None
    archive_date: Optional[str] = None
    is_cost_sharing: Optional[bool] = None
    expected_number_of_awards: Optional[int] = None
    estimated_total_program_funding: Optional[int] = None
    award_floor: Optional[int] = None
    award_ceiling: Optional[int] = None
    additional_info_url: Optional[str] = None
    additional_info_url_description: Optional[str] = None
    opportunity_assistance_listings: Optional[List[str]] = None
    funding_instruments: Optional[List[str]] = None
    funding_categories: Optional[List[str]] = None
    funding_category_description: Optional[str] = None
    applicant_types: Optional[List[str]] = None
    applicant_eligibility_description: Optional[str] = None
    agency_name: Optional[str] = None
    top_level_agency_name: Optional[str] = None
    agency_contact_description: Optional[str] = None
    agency_email_address: Optional[str] = None
    agency_email_address_description: Optional[str] = None
    is_forecast: Optional[bool] = None
    forecasted_post_date: Optional[str] = None
    forecasted_close_date: Optional[str] = None
    forecasted_close_date_description: Optional[str] = None
    forecasted_award_date: Optional[str] = None
    forecasted_project_start_date: Optional[str] = None
    fiscal_year: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    summary_description: Optional[str] = None
    tags: List[str] = field(default_factory=list)

def drop_empty_fields(data: dict) -> dict:
    cleaned = {}

    for k, v in data.items():
        if v is None:
            continue
        if v == "":
            continue
        if isinstance(v, list) and len(v) == 0:
            continue

        cleaned[k] = v

    return cleaned

def first_date_token(s: Optional[str]) -> Optional[str]:
    """Extract and normalize the first date that appears in a string."""
    if not s:
        return None
    s = clean_text(s)

    m = re.search(r"\b([A-Za-z]+ \d{1,2}, \d{4})\b", s)
    if m:
        return to_iso_date(m.group(1))

    m = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", s)
    if m:
        return to_iso_date(m.group(1))

    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", s)
    if m:
        return m.group(1)

    return None

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--url", required=True, help="A single Grants.gov FOA URL")
    parser.add_argument("--out_dir", required=True, type=Path, help="Output directory (e.g., ./out)")
    args = parser.parse_args()

    html = fetch_html(args.url)
    soup = BeautifulSoup(html, "html.parser")

    title = extract_title(soup)
    page_text = clean_text(" ".join(soup.stripped_strings))

    opportunity = Opportunity(
        opportunity_id=extract_opportunity_id(args.url),
        opportunity_title=title,
        created_at=datetime.utcnow().isoformat() + "Z",
        updated_at=datetime.utcnow().isoformat() + "Z",
    )

    opportunity.agency_name = find_label(page_text, "Agency")
    opportunity.opportunity_number = find_label(page_text, "Funding opportunity number")

    posted_raw  = find_label(page_text, "Posted date")
    close_raw   = (find_label(page_text, "Closing") or find_label(page_text, "Close date") or find_label(page_text, "Closing date"))
    archive_raw = find_label(page_text, "Archive date")

    opportunity.post_date = first_date_token(posted_raw)
    opportunity.close_date = first_date_token(close_raw)
    opportunity.archive_date = first_date_token(archive_raw)

    cost_sharing = find_label(page_text, "Cost sharing or matching requirement")
    if cost_sharing:
        opportunity.is_cost_sharing = cost_sharing.strip().lower().startswith("y")

    instrument = find_label(page_text, "Funding instrument type")
    if instrument:
        opportunity.funding_instruments = [instrument]

    opportunity.category = find_label(page_text, "Opportunity Category")
    opportunity.category_explanation = find_label(page_text, "Opportunity Category Explanation")

    funding_activity = find_label(page_text, "Category of Funding Activity")
    if funding_activity:
        opportunity.funding_categories = [funding_activity]

    al = find_label(page_text, "Assistance Listings")
    if al:
        codes = re.findall(r"\b\d{2}\.\d{3}\b", al)
        opportunity.opportunity_assistance_listings = sorted(set(codes)) or None

    external_links, documents = extract_links(soup)
    external_links = sorted(set(external_links))
    documents = sorted(set(documents))

    if documents:
        opportunity.additional_info_url = documents[0]
        opportunity.additional_info_url_description = "primary_pdf"
    elif external_links:
        opportunity.additional_info_url = external_links[0]
        opportunity.additional_info_url_description = "external_link"

    apply_tags(opportunity)

    out_path: Path = args.out_dir
    out_path.mkdir(parents=True, exist_ok=True)

    json_path = out_path / "foa.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(drop_empty_fields(asdict(opportunity)), f, indent=2, ensure_ascii=False)

    csv_path = out_path / "foa.csv"
    row = drop_empty_fields(asdict(opportunity))

    for k, v in list(row.items()):
        if isinstance(v, list):
            row[k] = "|".join(map(str, v))

    fieldnames = list(asdict(opportunity).keys())
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)

    print(f"Wrote: {json_path}")
    print(f"Wrote: {csv_path}")