import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
import torch
import torch.nn as nn
import warnings
import matplotlib.pyplot as plt

warnings.filterwarnings('ignore')

# ================== CONFIG ==================
STORE_ID   = 1  
TRAIN_FILE = 'split4_train.csv'  
TEST_FILE  = 'split4_test.csv'
CHRONOS_FORECAST_FILE = 'chronos_12_weeks_demand.csv'
FORECAST_HORIZON = 12
SEASONALITY = 52
# ===========================================
class LSTMModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.lstm = nn.LSTM(1, 50, batch_first=True)
        self.fc = nn.Linear(50, 1)
    
    def forward(self, x):
        _, (h, _) = self.lstm(x)
        return self.fc(h[-1])
# ────────────────────────────────────────────────────────────────
# SMI GENERATION FUNCTIONS
# ────────────────────────────────────────────────────────────────
def prepare_for_chronos(df, id_col, date_col, target_col, freq_alias):
    df = df.copy()
    
    # ── If there's no ID column → treat as single series ────────────────
    if id_col not in df.columns:
        print(f"→ Column '{id_col}' not found in input file → adding dummy {id_col} = {STORE_ID}")
        df[id_col] = STORE_ID
    
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
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
    print("\n--- Generating SMI Variables ---")
    df_weekly = df.set_index(date_col).resample(freq_alias)[target_col].sum().reset_index()
    df_weekly = df_weekly.rename(columns={date_col: 'Date', target_col: 'Weekly_Sales'})
    
    df_weekly['Rolling_Mean'] = df_weekly['Weekly_Sales'].rolling(window=4, center=True).mean()
    df_weekly['Is_Spike'] = df_weekly['Weekly_Sales'] > df_weekly['Rolling_Mean']
    
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


# METRICS FUNCTION (Fixed)
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
        'MAE':   round(mae, 2),
        'sMAPE': round(smape, 4),
        'WMAPE': round(wmape, 4),
        'MASE':  round(mase, 4),
        'WQL':   round(wql, 4)
    }

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
   
    # Take last 8 weeks of SMI (as per your latest function)
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
# MAIN EXECUTION FLOW – NOW USING CHRONOS AS BASELINE
# ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Chronos + SMI Nudger Pipeline ===\n")
    
    # 1. Load training data → generate SMI features
    print("Loading training data...")
    df_train = pd.read_csv(TRAIN_FILE)
    df_clean = prepare_for_chronos(df_train, id_col="Store", date_col="Date", target_col="value", freq_alias="W-FRI")
    smi_df = generate_smi_variables(df_clean, "Date", "value", "W-FRI")
    
    smi_output_file = f"smi_features_store{STORE_ID}.csv"
    smi_df.to_csv(smi_output_file, index=False)
    print(f"SMI features saved → {smi_output_file}")

    plot_smi_framework(smi_df)
    
    # 2. Load Chronos forecast as baseline
    print(f"\nLoading Chronos 12-week forecast from: {CHRONOS_FORECAST_FILE}")
    chronos_df = pd.read_csv(CHRONOS_FORECAST_FILE)
    
    # Standardize column names
    chronos_df = chronos_df.rename(columns={
        'Demand': 'Demand',           # already good
        'Period': 'Period'
    }).head(FORECAST_HORIZON)
    
    print(f"Chronos forecast loaded: {len(chronos_df)} weeks, "
          f"avg {chronos_df['Demand'].mean():,.1f}/week")
    
    # 3. Load actual test values for evaluation
    print("Loading test data...")
    df_test = pd.read_csv(TEST_FILE)
    df_test["Date"] = pd.to_datetime(df_test["Date"])
    df_test = df_test.sort_values("Date").head(FORECAST_HORIZON)
    test_series = df_test["value"].values
    test_dates = df_test["Date"].values
    
    print(f"Test actuals loaded: {len(test_series)} weeks, "
          f"avg {test_series.mean():,.1f}")
    
    # 4. Apply nudger on Chronos baseline
    print("\n=== SMI Nudger on Chronos Baseline ===\n")
    
    nudged_df = apply_nudger_to_12weeks(chronos_df, smi_df)
    
    # 5. Evaluation
    baseline_weekly = chronos_df['Demand'].values
    nudged_weekly   = nudged_df['nudged_demand'].values
    
    history_weekly = smi_df['Weekly_Sales'].values
    
    metrics_baseline = get_metrics(test_series, baseline_weekly,
                                 train_series_for_mase=history_weekly,
                                 seasonality=SEASONALITY)
    
    metrics_nudged = get_metrics(test_series, nudged_weekly,
                               train_series_for_mase=history_weekly,
                               seasonality=SEASONALITY)
    
    # 6. Save results
    nudged_df.to_csv('Chronos_nudged_12weeks.csv', index=False)
    print("Saved nudged forecast → Chronos_nudged_12weeks.csv")
    
    metrics_df = pd.DataFrame([
        {"Model": "Chronos_Baseline", **{f"Test_{k}": v for k, v in metrics_baseline.items()}},
        {"Model": "SMI_Nudged_Chronos", **{f"Test_{k}": v for k, v in metrics_nudged.items()}}
    ])
    metrics_df.to_csv('nudged_vs_chronos_metrics_weekly.csv', index=False)
    
    # 7. Plot
    plot_dates = test_dates if len(test_dates) == 12 else range(1, 13)
    
    plt.figure(figsize=(12, 6))
    plt.plot(plot_dates, test_series, label='Actual', color='black', marker='o', linewidth=2.5)
    plt.plot(plot_dates, baseline_weekly, label='Chronos Baseline', color='gray', marker='s', linewidth=2)
    plt.plot(plot_dates, nudged_weekly, label='SMI Nudged (Chronos)', color='blue', marker='^', linewidth=2.2)
    
    plt.title("12-Week Actual vs Chronos vs SMI-Nudged Chronos")
    plt.xlabel("Week")
    plt.ylabel("Weekly Demand")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("nudged_vs_actual_chronos.png", dpi=150)
    plt.show()
    plt.close()
    
    print("\n=== 12-WEEK TEST METRICS ===\n")
    print(metrics_df.round(4))
    print("\nDone.")
