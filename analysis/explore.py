
import pandas as pd

from app.records import load_records


def explore_data():

    records = load_records()

    if not records:
        print("No records found. Run ingestion first.")
        return

    df = pd.DataFrame(records)

    print("\n===== KANDAGUIDE DATA ANALYSIS =====")

    # FACT 1
    print("\nFACT 1: Total varieties")

    print("Total records:", len(df))

    # FACT 2
    print("\nFACT 2: Category distribution")

    print(
        df["category"].value_counts()
    )

    # FACT 3
    print("\nFACT 3: Missing data")

    columns = [
        "season",
        "maturity_days_after_transplanting",
        "yield_t_ha",
        "storage_life"
    ]

    print(
        df[columns].isnull().sum()
    )

    print("\nAnalysis completed!")


if __name__ == "__main__":
    explore_data()
