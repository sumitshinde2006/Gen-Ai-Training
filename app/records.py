
# app/records.py

from data.sample_records import records


def load_records():
    return records


def search(keyword):
    results = []

    for item in records:
        if keyword.lower() in item["variety_name"].lower():
            results.append(item)

    return results


def count_by(category):
    count = 0

    for item in records:
        if item["category"] == category.lower():
            count += 1

    return count


def get_by_id(record_id):
    if 1 <= record_id <= len(records):
        return records[record_id - 1]

    return None
