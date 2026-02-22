# Minimal Grants.gov FOA Ingestor

This repository implements a minimal ingestion pipeline that accepts a single Grants.gov Funding Opportunity Announcement (FOA) URL, extracts structured fields into a predefined schema, applies deterministic rule-based tagging, and outputs both JSON and CSV records.

The script supports both:

* classic `grants.gov/search-results-detail/...`
* new `simpler.grants.gov/opportunity/...`

---

## Features

* Fetches FOA HTML from a provided URL
* Extracts key metadata fields (agency, dates, funding category, etc.)
* Normalizes dates into ISO format (YYYY-MM-DD)
* Extracts Assistance Listing numbers (e.g., `93.262`)
* Deterministically selects a primary document (PDF or external link)
* Applies rule-based tags (no machine learning used)
* Outputs structured files:

  * `foa.json`
  * `foa.csv`
* Removes empty/null fields from final JSON output

---

## Installation

Create a virtual environment (recommended):

```bash
python -m venv venv
```

Activate it:

**Linux / macOS**

```bash
source venv/bin/activate
```

**Windows**

```bash
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Usage

Run the program:

```bash
python main.py --url "FOA_URL" --out_dir ./out
```

Example:

```bash
python main.py --url "https://simpler.grants.gov/opportunity/884213ea-b324-42da-b8cf-733df39df1f6" --out_dir ./out
```

---

## Output

The script creates:

```
out/
  foa.json
  foa.csv
```

### foa.json

A cleaned structured JSON record containing only non-empty fields.

### foa.csv

A single-row CSV representation of the same record.
List fields are pipe-separated (`|`).

---

## Deterministic Tagging

The script applies keyword-based tags derived from the opportunity title, agency name, and funding category.
Example tags include:

* `health_biomed`
* `ai_ml`
* `cybersecurity`
* `education`
* `climate_environment`
* `energy`
* `has_deadline`
* `cost_sharing`

The tagging system is fully deterministic — no machine learning models or external APIs are used.

---

## Supported Fields

The parser attempts to extract:

* Opportunity ID and number
* Agency name
* Posted, closing, and archive dates
* Funding instrument and category
* Assistance Listings (CFDA numbers)
* Cost sharing requirement
* Primary document link (PDF or official opportunity page)

Dates are normalized to ISO format (`YYYY-MM-DD`) whenever possible.

---

## Design Overview

This project demonstrates a minimal ETL-style ingestion pipeline:

1. **Extract**
   HTTP fetch + HTML parsing using `requests` and `BeautifulSoup`.

2. **Transform**
   Label detection, regex parsing, normalization, and data cleaning.

3. **Load**
   Structured JSON and CSV output.

The implementation intentionally avoids heavy frameworks and focuses on reliability, determinism, and clarity.

---

## Requirements

* Python 3.9+

External libraries:

* `requests`
* `beautifulsoup4`

---

## Notes

The `simpler.grants.gov` interface is still evolving.
The parser uses label-based extraction with safe fallbacks to remain robust across layout changes while keeping the implementation minimal.

---

## Deliverables

This submission includes:

* `main.py`
* `requirements.txt`
* `README.md`
* `out/foa.json`
* `out/foa.csv`

---

## Example Command

```bash
python main.py --url "https://www.grants.gov/search-results-detail/360555" --out_dir ./out
```

After running, the extracted FOA record will be available inside the `out/` directory.
