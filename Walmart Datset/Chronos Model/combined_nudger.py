import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import warnings

# Suppress warnings for cleaner output
warnings.simplefilter(action='ignore', category=FutureWarning)

# ================== CONFIG ==================
STORE_ID = 10  # Change this manually for different stores
TRAIN_FILE = 'split3_train.csv'  # Change for different splits
TEST_FILE = 'split3_test.csv'    # Change for different splits
CHRONOS_FORECAST_FILE = 'chronos_12_weeks_demand.csv'  # Change if needed for Chronos forecast file
FORECAST_HORIZON = 12
SEASONALITY = 52
FREQ_ALIAS = 'W-FRI'  # Weekly frequency anchored on Friday
# ===========================================

# ────────────────────────────────────────────────────────────────
# SMI GENERATION FUNCTIONS
# ────────────────────────────────────────────────────────────────
def prepare_for_chronos(df, id_col, date_col, target_col, freq_alias):
    """
    Cleans data, handles date parsing, and applies linear interpolation
    to ensure a consistent time heartbeat.
    """
    # 1. Robust Date Parsing
    df[date_col] = pd.to_datetime(df[date_col], format='mixed', dayfirst=True, errors='coerce')
    
    # 2. Drop invalid dates
    df = df.dropna(subset=[date_col])
    
    def fix_frequency(group):
        group = group.drop_duplicates(subset=date_col).set_index(date_col)
        group = group.resample(freq_alias).asfreq()
        group[target_col] = group[target_col].interpolate(method='linear').ffill().bfill()
        group[id_col] = group[id_col].ffill()
        return group.reset_index()
    
    df = df.sort_values([id_col, date_col])
    return df.groupby(id_col, group_keys=False).apply(fix_frequency)

def generate_smi_variables(df, date_col, target_col, freq_alias):
    """
    Aggregates to global weekly signal and calculates SMI variables
    - Now on ALL available weeks (no forced tail(52))
    """
    print("\n--- Generating SMI Variables (full history) ---")
    
    # Aggregate all stores → total market weekly sales
    df_weekly = df.set_index(date_col).resample(freq_alias)[target_col].sum().reset_index()
    df_weekly = df_weekly.rename(columns={date_col: 'Date', target_col: 'Weekly_Sales'})
    
    print(f"Full weekly series length: {len(df_weekly)} weeks")
    print(f"Date range: {df_weekly['Date'].min().date()} → {df_weekly['Date'].max().date()}")
    
    # Detect spikes (rolling mean)
    df_weekly['Rolling_Mean'] = df_weekly['Weekly_Sales'].rolling(window=4, center=True).mean()
    df_weekly['Is_Spike'] = df_weekly['Weekly_Sales'] > df_weekly['Rolling_Mean']
    
    # Semi-synthetic Hype signal
    smi_signal = np.zeros(len(df_weekly))
    for i in range(len(df_weekly)):
        if df_weekly.iloc[i]['Is_Spike']:
            mag = df_weekly.iloc[i]['Weekly_Sales'] / (df_weekly['Weekly_Sales'].mean() + 1e-5)
            if i - 2 >= 0: smi_signal[i-2] += 0.1 * mag
            if i - 1 >= 0: smi_signal[i-1] += 0.5 * mag
            smi_signal[i] += 0.9 * mag
            if i + 1 < len(df_weekly): smi_signal[i+1] += 0.5 * mag
    
    # Add small random noise + normalize to 0–1
    np.random.seed(42)
    smi_signal += np.random.uniform(0, 0.1, len(smi_signal))
    if smi_signal.max() > smi_signal.min():
        df_weekly['SMI_Hype_Index'] = (smi_signal - smi_signal.min()) / (smi_signal.max() - smi_signal.min())
    else:
        df_weekly['SMI_Hype_Index'] = 0.0
    
    # Momentum and Persistence
    df_weekly['SMI_Momentum'] = df_weekly['SMI_Hype_Index'].diff().fillna(0.0)
    df_weekly['SMI_Persistence'] = df_weekly['SMI_Hype_Index'].ewm(span=4, adjust=False).mean()
    
    return df_weekly

def plot_smi_framework(df_weekly):
    """Triple-axis plot — show last 52 weeks for readability"""
    plot_df = df_weekly.tail(52).copy()
    print(f"Plotting last {len(plot_df)} weeks for visualization")
    
    fig, ax1 = plt.subplots(figsize=(14, 7))
    ax1.plot(plot_df['Date'], plot_df['Weekly_Sales'], color='tab:blue', label='Total Sales', linewidth=2)
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Sales Volume', color='tab:blue')
    ax1.tick_params(axis='y', labelcolor='tab:blue')
    ax1.grid(True, linestyle='--', alpha=0.3)
    
    ax2 = ax1.twinx()
    ax2.plot(plot_df['Date'], plot_df['SMI_Hype_Index'], color='tab:red', label='SMI Hype Index', linestyle='--', alpha=0.4)
    ax2.plot(plot_df['Date'], plot_df['SMI_Persistence'], color='tab:orange', label='SMI Persistence (EMA)', linewidth=2.5)
    ax2.set_ylabel('Intensity / Persistence (0-1)', color='tab:red')
    ax2.tick_params(axis='y', labelcolor='tab:red')
    
    ax3 = ax1.twinx()
    ax3.spines['right'].set_position(('outward', 60))
    ax3.plot(plot_df['Date'], plot_df['SMI_Momentum'], color='tab:green', label='SMI Momentum', linestyle=':', alpha=0.7)
    ax3.set_ylabel('Momentum (Change Rate)', color='tab:green')
    ax3.tick_params(axis='y', labelcolor='tab:green')
    
    lines, labels = [], []
    for ax in [ax1, ax2, ax3]:
        l, lb = ax.get_legend_handles_labels()
        lines.extend(l)
        labels.extend(lb)
    
    ax1.legend(lines, labels, loc='upper left')
    plt.title('SMI Variables (last 52 weeks shown) vs Total Sales')
    plt.tight_layout()
    plt.savefig('smi_synthesis_chart.png', dpi=150)
    print("Chart saved as 'smi_synthesis_chart.png'")
    plt.show()
    plt.close()

# ────────────────────────────────────────────────────────────────
# NUDGER LOGIC (weekly version)
# ────────────────────────────────────────────────────────────────
def get_nudge_multiplier(weeks_ahead: int, smi_last_8: pd.DataFrame) -> float:
    """
    Updated nudger for Classical Models baseline
    """
    if len(smi_last_8) < 8:
        smi_last_8 = smi_last_8.iloc[-8:]
    # ── Inputs ───────────────────────────────────────
    avg_hype = smi_last_8['SMI_Hype_Index'].mean()
    latest_momentum = smi_last_8['SMI_Momentum'].iloc[-1]
    avg_persistence = smi_last_8['SMI_Persistence'].mean()
    latest_persistence = smi_last_8['SMI_Persistence'].iloc[-1]
    # ── Confidence ───────────────────────────────────
    persistence_score = avg_persistence
    momentum_strength = abs(latest_momentum)
    hype_volatility = smi_last_8['SMI_Hype_Index'].std(ddof=0) or 0.01
    confidence = 0.50 + 0.50 * min(1.0,
        (persistence_score / 0.22) +
        (momentum_strength / 0.12) +
        (hype_volatility / 0.10)
    )
    confidence = max(0.50, min(1.0, confidence))
    # ── Base logic ───────────────────────────────────
    weeks = float(weeks_ahead)
    base = 0.0
    if weeks <= 2.0:
        if avg_hype < 0.12 and latest_persistence < 0.18 and latest_momentum < -0.22:
            base = -0.010
        elif avg_hype < 0.22 and latest_persistence < 0.24:
            if latest_persistence < 0.19:
                base = -0.0010
            elif latest_persistence < 0.22:
                base = -0.0020
            else:
                base = -0.0045
        elif latest_momentum < -0.08 and latest_persistence > 0.22:
            base = +0.0140
        elif avg_hype > 0.58 and latest_persistence > 0.48:
            base = +0.0110
    elif weeks <= 4.0:
        if latest_persistence < 0.19:
            base = -0.0015
        elif latest_persistence < 0.27:
            base = -0.0030
        elif latest_momentum < -0.17:
            base = +0.0060
        base = max(base, -0.007)
    elif weeks <= 6.0:
        if latest_persistence < 0.20:
            base = -0.0010
        elif latest_persistence < 0.28:
            base = -0.0025
        elif latest_momentum < -0.14:
            base = +0.0045
        base = max(base, -0.006)
    elif weeks <= 8.0:
        if latest_persistence < 0.22:
            base = -0.0008
        elif latest_persistence < 0.30:
            base = -0.0020
        elif latest_momentum < -0.12:
            base = +0.0035
        base = max(base, -0.005)
    else: # weeks 9-12
        if latest_persistence < 0.32:
            base = -0.0015
        elif latest_momentum < -0.10:
            base = +0.0020
    # ── Apply confidence scaling ─────────────────────
    base *= confidence
    # ── Stronger default upward bias when persistence is low ──
    if latest_persistence < 0.25:
        lift = 0.008 if confidence < 0.72 else 0.0035
        base = max(base, lift)
    # Decay
    decay = max(0.0, 1.0 - (weeks - 0.5) * 0.11)
    multiplier = 1.0 + (base * decay)
    return max(0.978, min(1.095, multiplier))

def apply_nudger_to_12weeks(chronos_df: pd.DataFrame, smi_df: pd.DataFrame) -> pd.DataFrame:
    df = chronos_df.copy()
    
    # Take last 8 weeks of SMI
    last_8_smi = smi_df[['SMI_Hype_Index', 'SMI_Momentum', 'SMI_Persistence']].tail(8)
    
    if 'Period' in df.columns:
        df['weeks_ahead'] = df['Period'].astype(str).str.extract(r'(\d+)').astype(int)
    else:
        df['weeks_ahead'] = np.arange(1, len(df) + 1)
    
    df['multiplier'] = df['weeks_ahead'].apply(
        lambda w: get_nudge_multiplier(w, last_8_smi)
    )
    
    df['nudged_demand'] = df['Demand'] * df['multiplier']
    return df

# ────────────────────────────────────────────────────────────────
# METRICS (from combined_nudger.py – seasonal MASE + proper WQL)
# ────────────────────────────────────────────────────────────────
def get_metrics(actual, forecast, train_series_for_mase=None, seasonality=52):
    actual = np.array(actual)
    forecast = np.array(forecast)
    
    mae = np.mean(np.abs(actual - forecast))
    smape = 100 * np.mean(2 * np.abs(forecast - actual) / (np.abs(actual) + np.abs(forecast) + 1e-9))
    wmape = np.sum(np.abs(actual - forecast)) / (np.sum(np.abs(actual)) + 1e-9) * 100
    
    # MASE - Seasonal Naive (needs full training series)
    if train_series_for_mase is not None and len(train_series_for_mase) > seasonality:
        naive_errors = np.abs(train_series_for_mase[seasonality:] - train_series_for_mase[:-seasonality])
        scale = np.mean(naive_errors)
        mase = mae / scale if scale > 0 else 0.0
    else:
        mase = np.nan
    
    def q_loss(q, y, yhat):
        return 2 * np.sum(np.maximum(q * (y - yhat), (q - 1) * (y - yhat))) / (np.sum(y) + 1e-9)
    wql = np.mean([q_loss(q, actual, forecast) for q in [0.1, 0.5, 0.9]])
    
    return {
        'MAE': round(mae, 2),
        'sMAPE': round(smape, 4),
        'WMAPE': round(wmape, 4),
        'MASE': round(mase, 4),
        'WQL': round(wql, 4)
    }

# ────────────────────────────────────────────────────────────────
# MAIN COMBINED LOGIC
# ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # ── Hardcoded settings for SMI ──
    id_col = 'Store'
    date_col = 'Date'
    target_col = 'value'
    
    # 1. LOAD TRAIN & TEST DATA
    print("Loading files...")
    train_df = pd.read_csv(TRAIN_FILE)
    test_df = pd.read_csv(TEST_FILE)
    
    train_df['Date'] = pd.to_datetime(train_df['Date'], format='mixed', dayfirst=True, errors='coerce')
    test_df['Date'] = pd.to_datetime(test_df['Date'], format='mixed', dayfirst=True, errors='coerce')
    
    train_df = train_df.dropna(subset=['Date'])
    test_df = test_df.dropna(subset=['Date'])
    
    train_df = train_df[train_df['Store'] == STORE_ID].sort_values('Date').reset_index(drop=True)
    test_df = test_df[test_df['Store'] == STORE_ID].sort_values('Date').reset_index(drop=True)
    
    train_series = train_df['value'].values.astype(float)
    test_series = test_df['value'].values.astype(float)
    train_dates = pd.to_datetime(train_df['Date'].values)
    test_dates = pd.to_datetime(test_df['Date'].values)
    
    print(f"Store {STORE_ID} → Train: {len(train_series)} weeks | Test: {len(test_series)} weeks")
    
    # ── SMI Generation ──
    print("\nPreprocessing data for SMI (weekly, anchored on Friday)...")
    df_cleaned = prepare_for_chronos(train_df, id_col, date_col, target_col, FREQ_ALIAS)
    
    # Optional: save cleaned version (per store)
    df_cleaned[[id_col, date_col, target_col]].to_csv(f"preprocessed_chronos_store{STORE_ID}_split.csv", index=False)
    print(f"Saved preprocessed per-store data → preprocessed_chronos_store{STORE_ID}_split.csv")
    
    print("\nGenerating SMI variables on full history...")
    df_smi = generate_smi_variables(df_cleaned, date_col, target_col, FREQ_ALIAS)
    
    # Save full SMI series
    smi_output_file = f"smi_variables_store{STORE_ID}_train.csv"
    df_smi.to_csv(smi_output_file, index=False, float_format='%.4f')
    print(f"Saved full SMI variables → {smi_output_file} ({len(df_smi)} weeks)")
    
    plot_smi_framework(df_smi)
    
    # ── Nudger ──
    print("=== SMI Nudger on Chronos Baseline ===\n")
    
    # Load SMI (full, but nudger uses tail(8))
    smi_df = pd.read_csv(smi_output_file)
    
    # Load Chronos forecast
    chronos_df = pd.read_csv(CHRONOS_FORECAST_FILE)
    chronos_df = chronos_df.rename(columns={'Chronos': 'Demand'})  # Adjust column name if needed
    
    print(f"Loaded Chronos forecast: {len(chronos_df)} weeks, "
          f"avg {chronos_df['Demand'].mean():,.0f}/week")
    
    # Apply nudger
    nudged_df = apply_nudger_to_12weeks(chronos_df, smi_df)
    
    # Actual test values
    actual_weekly_values = test_df['value'].head(12).values
    plot_dates = test_df['Date'].head(12)
    
    print(f"Test actuals (first 12 weeks): {len(actual_weekly_values)} weeks, "
          f"avg {actual_weekly_values.mean():,.2f}")
    
    # Extract predictions
    baseline_weekly = chronos_df['Demand'].head(12).values
    nudged_weekly = nudged_df['nudged_demand'].head(12).values
    
    # Metrics (using combined_nudger.py logic)
    history_weekly = smi_df['Weekly_Sales'].values  # Full history for MASE
    metrics_baseline = get_metrics(actual_weekly_values, baseline_weekly, train_series_for_mase=history_weekly, seasonality=52)
    metrics_nudged = get_metrics(actual_weekly_values, nudged_weekly, train_series_for_mase=history_weekly, seasonality=52)
    
    # Save nudged forecast
    nudged_df.to_csv(f'Chronos_nudged_12weeks_store{STORE_ID}.csv', index=False)
    
    # Metrics table
    metrics_df = pd.DataFrame([
        {"Model": "Chronos_Baseline", **{f"Test_{k}": v for k, v in metrics_baseline.items()}},
        {"Model": "SMI_Nudged", **{f"Test_{k}": v for k, v in metrics_nudged.items()}}
    ])
    metrics_df.to_csv(f'nudged_vs_chronos_metrics_weekly_store{STORE_ID}.csv', index=False)
    
    # Plot
    plt.figure(figsize=(12, 6))
    plt.plot(plot_dates, actual_weekly_values, label='Actual', color='black', marker='o', linewidth=2)
    plt.plot(plot_dates, baseline_weekly, label='Chronos Baseline', color='gray', marker='s', linewidth=2)
    plt.plot(plot_dates, nudged_weekly, label='SMI Nudged', color='blue', marker='^', linewidth=2)
    plt.title(f"12-Week Actual vs Chronos Baseline vs SMI-Nudged (Store {STORE_ID})")
    plt.xlabel("Week")
    plt.ylabel("Weekly Demand")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(f"nudged_vs_actual_chronos_store{STORE_ID}.png", dpi=150)
    plt.show()
    plt.close()
    
    print("\n=== 12-WEEK TEST METRICS ===")
    print(metrics_df.round(4))
    print("\nFiles saved:")
    print(f" - Chronos_nudged_12weeks_store{STORE_ID}.csv")
    print(f" - nudged_vs_chronos_metrics_weekly_store{STORE_ID}.csv")
    print(f" - nudged_vs_actual_chronos_store{STORE_ID}.png")
    print("\nAll files saved successfully!")
