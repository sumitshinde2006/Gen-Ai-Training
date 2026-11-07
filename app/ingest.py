
# app/ingest.py

import json
import re

from pathlib import Path
from bs4 import BeautifulSoup
from pypdf import PdfReader


RAW_DIR = Path("data/raw")
OUTPUT_FILE = Path("data/records.json")

DOGR_URL = (
    "https://www.dogr.res.in/index.php/research/"
    "varieties-developed?layout=edit"
)

variety_categories = {
    "Bhima Light Red": "onion",
    "Bhima Dark Red": "onion",
    "Bhima Red": "onion",
    "Bhima Raj": "onion",
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


def extract_sections(html):

    soup = BeautifulSoup(html, "html.parser")
    sections = {}

    for heading in soup.find_all(["h2", "h3", "h4"]):

        name = heading.get_text(" ", strip=True)

        if name not in variety_categories:
            continue

        content = []

        for element in heading.find_all_next(
            ["h2", "h3", "h4", "p", "li"]
        ):

            if element.name in ["h2", "h3", "h4"]:
                break

            content.append(element.get_text(" ", strip=True))

        sections[name] = " ".join(content)

    return sections


def extract_field(pattern, text):

    match = re.search(pattern, text, re.IGNORECASE)

    if match:
        return match.group(1).strip()

    return None


def clean_record(name, text):

    season = extract_field(
        r"Season:\s*(.*?)(?=Maturity:|Yield:|Average Yield:|"
        r"Storability:|Bolting:|$)",
        text
    )

    maturity = extract_field(
        r"Maturity:\s*(.*?)(?=Bolting:|Average Yield:|"
        r"Yield:|Highest Yield:|Storability:|$)",
        text
    )

    # Only keep maturity explicitly measured after transplanting.
    if maturity and "after transplanting" not in maturity.lower():
        maturity = None

    yield_value = extract_field(
        r"(?:Average Yield|Yield):\s*(.*?)(?=Highest Yield:|"
        r"Storability:|Total Soluble|Reaction|Uniqueness:|$)",
        text
    )

    storage = extract_field(
        r"Storability:\s*(.*?)(?=Total Soluble|Reaction|"
        r"Uniqueness:|$)",
        text
    )

    # Convert quintals/hectare to tonnes/hectare.
    if yield_value:
        def convert_quintals(match):
            value = float(match.group(1)) / 10
            return f"{value:g} t/ha"

        yield_value = re.sub(
            r"(\d+(?:\.\d+)?)\s*q\s*/\s*ha",
            convert_quintals,
            yield_value,
            flags=re.IGNORECASE
        )

    return {
        "variety_name": name,
        "category": variety_categories[name],
        "season": season,
        "maturity_days_after_transplanting": maturity,
        "yield_t_ha": yield_value,
        "storage_life": storage,
        "source_url": DOGR_URL
    }


def extract_manage_reference():

    pdf_file = RAW_DIR / "manage_onion_garlic.pdf"

    if not pdf_file.exists():
        print("MANAGE PDF not found.")
        return

    try:
        reader = PdfReader(str(pdf_file))

        text = "\n".join(
            page.extract_text() or ""
            for page in reader.pages
        )

        output = RAW_DIR / "manage_reference.txt"
        output.write_text(text, encoding="utf-8")

        print("MANAGE PDF text extracted.")

    except Exception as error:
        print(f"PDF extraction failed: {error}")


def ingest_data():

    html_file = RAW_DIR / "dogr_varieties.html"

    if not html_file.exists():
        print("DOGR HTML not found. Run app.fetch first.")
        return

    html = html_file.read_text(encoding="utf-8")
    sections = extract_sections(html)

    records = []

    for name in variety_categories:

        try:
            if name not in sections:
                print(f"Skipped missing variety: {name}")
                continue

            record = clean_record(name, sections[name])

            records.append(record)

            print(f"Processed: {name}")

        except (ValueError, TypeError, AttributeError) as error:
            print(f"Bad record: {name} - {error}")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT_FILE.write_text(
        json.dumps(records, indent=4, ensure_ascii=False),
        encoding="utf-8"
    )

    print("\nIngestion completed!")
    print("Total records:", len(records))
    print("Saved to:", OUTPUT_FILE)


if __name__ == "__main__":

    extract_manage_reference()
    ingest_data()
