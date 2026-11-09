
import json
from pathlib import Path

DATA_FILE = Path("data/records.json")


def load_records():

    if not DATA_FILE.exists():
        return []

    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def search(keyword):

    records = load_records()
    keyword = keyword.lower()

    results = []

    for item in records:

        searchable = " ".join(
            str(value or "")
            for value in item.values()
        )

        if keyword in searchable.lower():
            results.append(item)

    return results


def count_by(category):

    records = load_records()

    return sum(
        1 for item in records
        if item.get("category", "").lower() == category.lower()
    )


def get_by_id(record_id):

    records = load_records()

    if 1 <= record_id <= len(records):
        return records[record_id - 1]

    return None
