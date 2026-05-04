import pandas as pd
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

def prepare_for_chronos(df):

    id_col = "Store"
    date_col = "Date"
    target_col = "value"
    freq_alias = "W-FRI"

    # ── Handle missing Store column (single-series files) ────────────────
    if id_col not in df.columns:
        #print("No 'Store' column found - treating as single series (adding Store=1)")
        df = df.copy()
        df[id_col] = 1

    # Ensure datetime
    df[date_col] = pd.to_datetime(df[date_col])

    # Remove negative values
    df = df[df[target_col] >= 0]

    df = df.sort_values([id_col, date_col])

    def fix_frequency(group):
        group = group.drop_duplicates(subset=date_col).set_index(date_col)
        group = group.resample(freq_alias).asfreq()

        # Linear interpolation
        group[target_col] = (
            group[target_col]
            .interpolate(method="linear")
            .ffill()
            .bfill()
        )

        group[id_col] = group[id_col].ffill()
        return group.reset_index()

    df_cleaned = df.groupby(id_col, group_keys=False).apply(fix_frequency)

    return df_cleaned
