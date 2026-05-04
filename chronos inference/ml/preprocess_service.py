import sys
import json
import pandas as pd
from data_preprocessing_chronos import prepare_for_chronos

def preprocess(csv_path):
    """
    Reads the CSV, preprocesses it, detects the actual store ID from the file,
    and returns the series for that store.
    """
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(json.dumps({"error": f"Failed to read CSV: {str(e)}"}))
        return

    # Preprocess the full dataset
    df_cleaned = prepare_for_chronos(df)

    # Automatically detect the store ID(s) present in the file
    unique_stores = df_cleaned["Store"].unique()

    if len(unique_stores) == 0:
        print(json.dumps({"error": "No Store column or no data after preprocessing"}))
        return

    # If multiple stores → take the first one (or the only one)
    store_id = int(unique_stores[0])
    #print(f"Detected store ID: {store_id} (found {len(unique_stores)} unique stores)")

    # Filter for this store
    store_df = df_cleaned[df_cleaned["Store"] == store_id]

    if store_df.empty:
        print(json.dumps({"error": f"No data found for detected Store {store_id}"}))
        return

    series = store_df["value"].astype(float).tolist()

    # Output format expected by your frontend / app
    print(json.dumps({str(store_id): series}))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "CSV path required as argument"}))
        sys.exit(1)

    csv_path = sys.argv[1]
    preprocess(csv_path)
