from app.records import count_by, load_records


def test_records_load_and_include_variety_fields():
    records = load_records()

    assert records
    assert {"variety_name", "category", "season", "source_url"} <= records[0].keys()


def test_onion_and_garlic_records_are_both_available():
    records = load_records()
    categories = {record["category"] for record in records}

    assert {"onion", "garlic"} <= categories
    assert count_by("onion") > 0
    assert count_by("garlic") > 0

