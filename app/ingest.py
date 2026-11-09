
# app/ingest.py

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup


# ---------------------------------
# FILE PATHS AND SOURCES
# ---------------------------------

RAW_DIR = Path("data/raw")
OUTPUT_FILE = Path("data/records.json")

DOGR_URL = (
    "https://www.dogr.res.in/index.php/research/"
    "varieties-developed?layout=edit"
)

NHB_URL = (
    "https://nhb.gov.in/pdf/vegetable/onion/oni013.pdf"
)


# ---------------------------------
# DOGR VARIETY LIST
# ---------------------------------

VARIETIES = {
    "Bhima Light Red": "onion",
    "Bhima Dark Red": "onion",
    "Bhima Raj": "onion",
    "Bhima Red": "onion",
    "Bhima Super": "onion",
    "Bhima Kiran": "onion",
    "Bhima Shakti": "onion",
    "Bhima Shweta": "onion",
    "Bhima Shubra": "onion",
    "Bhima Safed": "onion",
    "Bhima Prasanskaran": "onion",
    "Bhima Omkar": "garlic",
    "Bhima Purple": "garlic"
}


# ---------------------------------
# READ HTML FILE
# ---------------------------------

def read_html(path):

    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run python -m app.fetch first."
        )

    html = path.read_text(
        encoding="utf-8",
        errors="replace"
    )

    soup = BeautifulSoup(html, "html.parser")

    # Remove unnecessary elements
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    return soup


# ---------------------------------
# EXTRACT VARIETY SECTIONS
# ---------------------------------

def extract_sections(soup):

    # Extract ALL visible text, including divs and spans.
    lines = [
        line.strip()
        for line in soup.get_text("\n", strip=True).splitlines()
        if line.strip()
    ]

    # Locate the variety headings.
    positions = {}

    for name in VARIETIES:

        for index, line in enumerate(lines):

            if line.casefold() == name.casefold():
                positions[name] = index
                break

    sections = {}

    # Sort varieties by their position on the webpage.
    ordered = sorted(
        positions.items(),
        key=lambda item: item[1]
    )

    for i, (name, start) in enumerate(ordered):

        if i + 1 < len(ordered):
            end = ordered[i + 1][1]
        else:
            end = len(lines)

        sections[name] = " ".join(lines[start + 1:end])

    return sections


# ---------------------------------
# EXTRACT FIELD VALUES
# ---------------------------------

def extract_value(pattern, text):

    match = re.search(
        pattern,
        text,
        re.IGNORECASE
    )

    if match:
        return re.sub(
            r"\s+",
            " ",
            match.group(1)
        ).strip(" .;,:-")

    return None


def convert_yield(value):

    if not value:
        return None

    def convert(match):

        number = float(match.group(1))

        return f"{number / 10:g} t/ha"

    value = re.sub(
        r"(\d+(?:\.\d+)?)\s*(?:q|quintals?)\s*/\s*ha",
        convert,
        value,
        flags=re.IGNORECASE
    )

    return value.strip()


# ---------------------------------
# CLEAN INDIVIDUAL RECORD
# ---------------------------------

def clean_record(name, category, text):

    # Extract season
    season = extract_value(
        r"Season\s*:\s*(.*?)"
        r"(?=Maturity\s*:|Bolting\s*:|"
        r"Average\s+Yield\s*:|Yield\s*:|Storability\s*:|$)",
        text
    )

    # Extract maturity
    maturity = extract_value(
        r"Maturity\s*:\s*(.*?)"
        r"(?=Bolting\s*:|Average\s+Yield\s*:|"
        r"Highest\s+Yield\s*:|Yield\s*:|Storability\s*:|$)",
        text
    )

    maturity_note = None

    # Only use the required DAT field when source says
    # days after transplanting.
    if maturity:

        if "transplant" not in maturity.lower():

            maturity_note = maturity
            maturity = None

    # Prefer Average Yield over the shorter Yield label.
    yield_value = extract_value(
        r"Average\s+Yield\s*:\s*(.*?)"
        r"(?=Highest\s+Yield\s*:|Storability\s*:|"
        r"Total\s+Soluble|Reaction\s+to|Uniqueness\s*:|$)",
        text
    )

    # Some DOGR varieties use only Yield.
    if not yield_value:

        yield_value = extract_value(
            r"(?<!Average )Yield\s*:\s*(.*?)"
            r"(?=Bolting\s*:|Highest\s+Yield\s*:|"
            r"Storability\s*:|Total\s+Soluble|"
            r"Reaction\s+to|Uniqueness\s*:|$)",
            text
        )

    yield_value = convert_yield(yield_value)

    # Extract storage information
    storage = extract_value(
        r"Storability\s*:\s*(.*?)"
        r"(?=Total\s+Soluble|Reaction\s+to|"
        r"Uniqueness\s*:|$)",
        text
    )

    # Bhima Light Red uses a descriptive storage statement.
    if not storage and "excellent storage qualities" in text.lower():
        storage = "Excellent storage qualities"

    return {
        "variety_name": name,
        "category": category,
        "season": season,
        "maturity_days_after_transplanting": maturity,
        "yield_t_ha": yield_value,
        "storage_life": storage,
        "source_url": DOGR_URL,
        "maturity_note": maturity_note
    }


# ---------------------------------
# ADD NHB VARIETIES
# ---------------------------------

def get_nhb_records():

    return [

        {
            "variety_name": "N-2-4-1",
            "category": "onion",
            "season": None,
            "maturity_days_after_transplanting": "140-145 days",
            "yield_t_ha": "30-35 t/ha",
            "storage_life": "Good keeping quality",
            "source_url": NHB_URL,
            "maturity_note": None
        },

        {
            "variety_name": "N-53",
            "category": "onion",
            "season": "Kharif",
            "maturity_days_after_transplanting": "90-100 days",
            "yield_t_ha": "25 t/ha",
            "storage_life": "Poor keeping quality",
            "source_url": NHB_URL,
            "maturity_note": None
        },

        {
            "variety_name": "Agrifound Dark Red",
            "category": "onion",
            "season": "Kharif",
            "maturity_days_after_transplanting": "95-110 days",
            "yield_t_ha": "30-40 t/ha",
            "storage_life": "Average keeping quality",
            "source_url": NHB_URL,
            "maturity_note": None
        },

        {
            "variety_name": "Agrifound White",
            "category": "onion",
            "season": "Kharif, Rabi",
            "maturity_days_after_transplanting": None,
            "yield_t_ha": "20-25 t/ha",
            "storage_life": "Good keeping quality",
            "source_url": NHB_URL,
            "maturity_note": "160-165 days after sowing"
        }

    ]


# ---------------------------------
# MAIN INGESTION FUNCTION
# ---------------------------------

def main():

    print("\nKANDAGUIDE DATA INGESTION")
    print("------------------------")

    soup = read_html(
        RAW_DIR / "dogr_varieties.html"
    )

    sections = extract_sections(soup)

    records = []

    # Process DOGR records
    for name, category in VARIETIES.items():

        try:

            if name not in sections:

                print(f"[WARNING] {name} not found")
                continue

            record = clean_record(
                name,
                category,
                sections[name]
            )

            records.append(record)

            print(
                f"[OK] {name} | "
                f"Season: {record['season']} | "
                f"Maturity: {record['maturity_days_after_transplanting']} | "
                f"Yield: {record['yield_t_ha']} | "
                f"Storage: {record['storage_life']}"
            )

        except (ValueError, TypeError, AttributeError) as error:

            print(f"[ERROR] {name}: {error}")

    # Add four NHB records
    try:

        nhb_records = get_nhb_records()

        records.extend(nhb_records)

        print("\nAdded NHB records:", len(nhb_records))

    except (ValueError, TypeError) as error:

        print("NHB record error:", error)

    # Save JSON
    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            records,
            indent=4,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    # Final summary
    onion_count = sum(
        1 for r in records
        if r["category"] == "onion"
    )

    garlic_count = sum(
        1 for r in records
        if r["category"] == "garlic"
    )

    print("\n========== FINAL SUMMARY ==========")

    print("Total records:", len(records))
    print("Onion records:", onion_count)
    print("Garlic records:", garlic_count)

    print("\nMISSING FIELD REPORT")

    for field in [
        "season",
        "maturity_days_after_transplanting",
        "yield_t_ha",
        "storage_life"
    ]:

        missing = sum(
            1 for r in records
            if r.get(field) is None
        )

        print(f"{field}: {missing} missing")

    print("\nSaved successfully:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
