
import pandas as pd

from app.records import load_records


def explore_data():
    records = load_records()

    if not records:
        print("No records found. Run: python -m app.ingest")
        return

    df = pd.DataFrame(records)

    print("\n===================================")
    print("       KANDAGUIDE DATA ANALYSIS")
    print("===================================")

    # FACT 1: Total records
    print("\nFACT 1: Total agricultural varieties")
    print("Total records:", len(df))

    # FACT 2: Onion and garlic distribution
    print("\nFACT 2: Category distribution")
    print(df["category"].value_counts().to_string())

    # FACT 3: Missing values
    print("\nFACT 3: Missing data report")

    columns = [
        "season",
        "maturity_days_after_transplanting",
        "yield_t_ha",
        "storage_life"
    ]

    print(df[columns].isnull().sum().to_string())

    # Additional analysis: varieties by season
    print("\nADDITIONAL: Variety records by season")

    season_counts = (
        df["season"]
        .fillna("Not specified")
        .value_counts()
    )

    print(season_counts.to_string())

    print("\n===================================")
    print("Analysis completed successfully!")
    print("===================================")


if __name__ == "__main__":
    explore_data()
