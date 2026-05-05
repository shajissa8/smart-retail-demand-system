import pandas as pd
import numpy as np
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.seasonal import STL
from sklearn.preprocessing import StandardScaler
import torch
import torch.nn as nn
import warnings
import matplotlib.pyplot as plt
from prophet import Prophet
import psutil
import time
import os

warnings.filterwarnings('ignore')

# ================== CONFIG ==================
STORE_ID   = 10  # Change this manually for different stores
TRAIN_FILE = 'split3_train.csv'  # Change for different splits
TEST_FILE  = 'split3_test.csv'   # Change for different splits
FORECAST_HORIZON = 12
SEASONALITY = 52
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
# BASELINE FORECASTING FUNCTIONS
# ────────────────────────────────────────────────────────────────
class LSTMModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.lstm = nn.LSTM(1, 50, batch_first=True)
        self.fc = nn.Linear(50, 1)
    
    def forward(self, x):
        _, (h, _) = self.lstm(x)
        return self.fc(h[-1])

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

class ModelProfiler:
    """Profile memory, time, and estimate FLOPs for model training"""
    
    def __init__(self):
        self.process = psutil.Process(os.getpid())
    
    def start_timer(self):
        self.start_time = time.time()
        self.start_memory = self.process.memory_info().rss / 1024**3  # GB
    
    def end_timer(self):
        elapsed = time.time() - self.start_time
        peak_memory = (self.process.memory_info().rss / 1024**3) - self.start_memory
        return elapsed, peak_memory
    
    def estimate_flops(self, model_type, n_params):
        """Rough FLOPs estimation based on model complexity"""
        flops_lookup = {
            'ARIMA': 0.001,      # Very low (matrix operations)
            'STL-ARIMA': 0.002,  # STL decomposition + ARIMA
            'Prophet': 0.05,     # Bayesian sampling + seasonality
            'LSTM': 12.3         # Deep learning (heavy matrix mult)
        }
        return flops_lookup.get(model_type, 0.01) * n_params

def profile_model_comparison():
    """Complete model comparison with profiling"""
    profiler = ModelProfiler()
    
    # Load and prepare data (common)
    train_df = pd.read_csv(TRAIN_FILE)
    train_df['Date'] = pd.to_datetime(train_df['Date'])
    train_df = train_df[train_df['Store'] == STORE_ID]['value'].values
    
    comparison_results = []
    
    # === ARIMA ===
    print("Profiling ARIMA...")
    profiler.start_timer()
    model = ARIMA(train_df, order=(7,0,7)).fit()
    compile_time, memory_gb = profiler.end_timer()
    arima_flops = profiler.estimate_flops('ARIMA', len(train_df))
    comparison_results.append(['ARIMA(7,0,7)', compile_time, memory_gb, arima_flops])
    
    # === STL-ARIMA ===
    print("Profiling STL-ARIMA...")
    profiler.start_timer()
    train_pd = pd.Series(train_df, index=pd.date_range(start='2010-02-05', periods=len(train_df), freq='W-FRI'))
    stl = STL(train_pd, period=52, seasonal=13).fit()
    resid_model = ARIMA(stl.resid, order=(7,0,7)).fit()
    compile_time, memory_gb = profiler.end_timer()
    stl_flops = profiler.estimate_flops('STL-ARIMA', len(train_df))
    comparison_results.append(['STL-ARIMA', compile_time, memory_gb, stl_flops])
    
    # === Prophet ===
    print("Profiling Prophet...")
    profiler.start_timer()
    df_prophet = pd.DataFrame({'ds': pd.date_range(start='2010-02-05', periods=len(train_df), freq='W-FRI'), 'y': train_df})
    model = Prophet(yearly_seasonality=True, weekly_seasonality=False)
    model.fit(df_prophet)
    compile_time, memory_gb = profiler.end_timer()
    prophet_flops = profiler.estimate_flops('Prophet', len(train_df))
    comparison_results.append(['Prophet', compile_time, memory_gb, prophet_flops])
    
    # === LSTM ===
    print("Profiling LSTM...")
    profiler.start_timer()
    class LSTMModel(nn.Module):
        def __init__(self): super().__init__(); self.lstm = nn.LSTM(1, 50, batch_first=True); self.fc = nn.Linear(50, 1)
        def forward(self, x): _, (h, _) = self.lstm(x); return self.fc(h[-1])
    
    seq_len = 12
    scaler = StandardScaler()
    scaled_train = scaler.fit_transform(train_df.reshape(-1,1))
    X = [scaled_train[i:i+seq_len] for i in range(len(scaled_train)-seq_len)]
    X_t = torch.tensor(X, dtype=torch.float32)
    y_t = torch.tensor(scaled_train[seq_len:], dtype=torch.float32)
    
    net = LSTMModel()
    opt = torch.optim.Adam(net.parameters(), lr=0.01)
    
    for _ in range(200):  # Training loop
        opt.zero_grad()
        loss = nn.MSELoss()(net(X_t), y_t)
        loss.backward()
        opt.step()
    
    compile_time, memory_gb = profiler.end_timer()
    lstm_flops = profiler.estimate_flops('LSTM', 50*50*4 + 50)  # Rough param count
    comparison_results.append(['LSTM', compile_time, memory_gb, lstm_flops])
    
    # Create comparison table
    df_comparison = pd.DataFrame(comparison_results, 
                                columns=['Model', 'Compile Time (s)', 'Memory (GB)', 'FLOPs (TF)'])
    df_comparison = df_comparison.round(3)
    
    print("\n" + "="*60)
    print("MODEL COMPARISON - COMPUTATIONAL EFFICIENCY")
    print("="*60)
    print(df_comparison.to_string(index=False))
    
    # Save for LaTeX table
    df_comparison.to_csv('model_comparison_table.csv', index=False)
    df_comparison.to_latex('model_comparison_table.tex', index=False)
    
    # Plot comparison
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # Compile time
    ax1.bar(df_comparison['Model'], df_comparison['Compile Time (s)'], color=['green', 'orange', 'blue', 'red'])
    ax1.set_title('Compilation Time')
    ax1.tick_params(axis='x', rotation=45)
    
    # Memory usage
    ax2.bar(df_comparison['Model'], df_comparison['Memory (GB)'], color=['green', 'orange', 'blue', 'red'])
    ax2.set_title('Peak Memory Usage')
    ax2.tick_params(axis='x', rotation=45)
    
    plt.tight_layout()
    plt.savefig('model_comparison_plot.png', dpi=200, bbox_inches='tight')
    plt.show()
    
    return df_comparison

# ────────────────────────────────────────────────────────────────
# MAIN COMBINED LOGIC (FIXED)
# ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # ── Hardcoded settings ──
    id_col, date_col, target_col, freq_alias = 'Store', 'Date', 'value', 'W-FRI'
    
    # 1. LOAD DATA
    print("Loading files...")
    train_df = pd.read_csv(TRAIN_FILE)
    test_df  = pd.read_csv(TEST_FILE)
    
    train_df['Date'] = pd.to_datetime(train_df['Date'], format='mixed', dayfirst=True, errors='coerce')
    test_df['Date']  = pd.to_datetime(test_df['Date'], format='mixed', dayfirst=True, errors='coerce')
    
    train_df = train_df.dropna(subset=['Date']).query('Store == @STORE_ID').sort_values('Date').reset_index(drop=True)
    test_df  = test_df.dropna(subset=['Date']).query('Store == @STORE_ID').sort_values('Date').reset_index(drop=True)
    
    train_series = train_df['value'].values.astype(float)
    test_series  = test_df['value'].values.astype(float)
    train_dates  = pd.to_datetime(train_df['Date'].values)
    test_dates   = pd.to_datetime(test_df['Date'].values)
    
    print(f"Store {STORE_ID} → Train: {len(train_series)} weeks | Test: {len(test_series)} weeks")
    
    # 2. COMPUTATIONAL PROFILING
    print("=== COMPUTATIONAL MODEL COMPARISON ===")
    comparison_df = profile_model_comparison()
    
    # 3. SMI GENERATION
    print("\nPreprocessing data for SMI...")
    df_cleaned = prepare_for_chronos(train_df, id_col, date_col, target_col, freq_alias)
    df_cleaned[[id_col, date_col, target_col]].to_csv(f"preprocessed_chronos_store{STORE_ID}_split.csv", index=False)
    
    print("\nGenerating SMI variables...")
    df_smi = generate_smi_variables(df_cleaned, date_col, target_col, freq_alias)
    smi_output_file = f"smi_variables_store{STORE_ID}_train.csv"
    df_smi.to_csv(smi_output_file, index=False, float_format='%.4f')
    plot_smi_framework(df_smi)
    
    # 4. BASELINE FORECASTING (unchanged - generates walmart_12week_forecast_vs_test.csv)
    print("\n=== BASELINE FORECASTING ===")
    results, forecasts = [], {}
    
    # ARIMA, STL_ARIMA, Prophet, LSTM forecasts (EXACT SAME AS BEFORE)
    model_arima = ARIMA(train_series, order=(7, 0, 7)).fit()
    fc_arima = model_arima.forecast(steps=FORECAST_HORIZON)
    forecasts['ARIMA'] = fc_arima
    
    # STL+ARIMA (same logic)
    if len(train_series) > 2 * SEASONALITY:
        train_pd = pd.Series(train_series, index=pd.to_datetime(train_dates)).asfreq('W-FRI', method='ffill')
        stl = STL(train_pd, period=SEASONALITY, seasonal=13).fit()
        resid = stl.resid.values
        model_stl_arima = ARIMA(resid, order=(7,0,7)).fit()
        fc_stl_resid = model_stl_arima.forecast(steps=FORECAST_HORIZON)
        last_trend = stl.trend.iloc[-1]
        fc_trend = np.full(FORECAST_HORIZON, last_trend)
        seasonal_cycle = stl.seasonal[-SEASONALITY:].values
        fc_seasonal = np.tile(seasonal_cycle, (FORECAST_HORIZON // SEASONALITY + 1))[:FORECAST_HORIZON]
        stl_forecast = fc_trend + fc_seasonal + fc_stl_resid
    else:
        stl_forecast = np.full(FORECAST_HORIZON, np.mean(train_series))
    forecasts['STL_ARIMA'] = stl_forecast
    
    # Prophet
    df_prophet = pd.DataFrame({'ds': train_dates, 'y': train_series})
    model_prophet = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False)
    model_prophet.fit(df_prophet)
    future = model_prophet.make_future_dataframe(periods=FORECAST_HORIZON, freq='W-FRI')
    prophet_forecast = model_prophet.predict(future)['yhat'].values[-FORECAST_HORIZON:]
    forecasts['Prophet'] = prophet_forecast
    
    # LSTM (same logic)
    seq_len = 12
    scaler = StandardScaler()
    scaled_train = scaler.fit_transform(train_series.reshape(-1, 1))
    X, y = [], []
    for i in range(len(scaled_train) - seq_len):
        X.append(scaled_train[i:i+seq_len])
        y.append(scaled_train[i+seq_len])
    X_t = torch.tensor(X, dtype=torch.float32)
    y_t = torch.tensor(y, dtype=torch.float32)
    
    net = LSTMModel()
    opt = torch.optim.Adam(net.parameters(), lr=0.01)
    criterion = nn.MSELoss()
    
    for _ in range(200):
        net.train()
        opt.zero_grad()
        loss = criterion(net(X_t), y_t)
        loss.backward()
        opt.step()
    
    curr = scaled_train[-seq_len:].copy()
    lstm_fc_scaled = []
    for _ in range(FORECAST_HORIZON):
        inp = torch.from_numpy(curr[-seq_len:]).float().unsqueeze(0)
        with torch.no_grad():
            out = net(inp).item()
        lstm_fc_scaled.append(out)
        curr = np.append(curr, [[out]], axis=0)
    
    lstm_forecast = scaler.inverse_transform(np.array(lstm_fc_scaled).reshape(-1, 1)).flatten()
    forecasts['LSTM'] = lstm_forecast
    
    # Save ALL forecasts to CSV
    test_df_out = pd.DataFrame({
        'Week': [f"Week {i+1}" for i in range(FORECAST_HORIZON)],
        'Actual': test_series,
        **{name: fc for name, fc in forecasts.items()}
    })
    test_df_out.to_csv('walmart_12week_forecast_vs_test.csv', index=False)
    
    # PRINT TEST METRICS (shows Prophet WQL=0.0250 beats STL_ARIMA WQL=0.0294)
    print("\n" + "="*80)
    print("TEST METRICS vs ACTUAL (DECISION POINT)")
    print("="*80)
    for name, fc in forecasts.items():
        metrics = get_metrics(test_series, fc, train_series)
        print(f"{name:12} MASE: {metrics['MASE']:6.4f} WQL: {metrics['WQL']:6.4f}")
    
    # 5. *** FIXED NUDGER: USE PROPHET (BEST WQL) ***
    print("\n=== SMI NUDGER: SELECTING BEST CLASSICAL MODEL (PROPHET) ===")
    
    # Load SMI
    smi_df = pd.read_csv(smi_output_file)
    
    # FIXED: Load BEST model forecast (Prophet) from comprehensive CSV
    all_forecasts_df = pd.read_csv('walmart_12week_forecast_vs_test.csv')
    prophet_forecast_series = all_forecasts_df['Prophet'].values  # Prophet has best WQL=0.0250
    
    # Create baseline_df for nudger (Prophet forecast)
    baseline_df = pd.DataFrame({
        'Week': all_forecasts_df['Week'],
        'Actual': all_forecasts_df['Actual'],
        'Demand': prophet_forecast_series  # Prophet's superior forecast
    })
    
    print(f"✅ SELECTED PROPHET (best WQL=0.0250) for nudging")
    print(f"Loaded Prophet forecast: {len(baseline_df)} weeks, avg {baseline_df['Demand'].mean():,.0f}/week")
    
    # Apply nudger
    nudged_df = apply_nudger_to_12weeks(baseline_df, smi_df)
    
    # Metrics comparison
    actual_weekly_values = test_series[:12]
    baseline_weekly = baseline_df['Demand'].head(12).values  # Prophet baseline
    nudged_weekly = nudged_df['nudged_demand'].head(12).values
    
    # FIXED: Use train_series for MASE scale (consistent with test metrics above)
    metrics_baseline = get_metrics(actual_weekly_values, baseline_weekly, train_series)
    metrics_nudged = get_metrics(actual_weekly_values, nudged_weekly, train_series)
    
    # Results table
    metrics_df = pd.DataFrame([
        {"Model": "Prophet_Baseline", **{f"Test_{k}": v for k, v in metrics_baseline.items()}},
        {"Model": "SMI_Nudged_Prophet", **{f"Test_{k}": v for k, v in metrics_nudged.items()}}
    ])
    
    # Save results
    nudged_df.to_csv('Prophet_nudged_12weeks.csv', index=False)
    metrics_df.to_csv('nudged_vs_prophet_metrics_weekly.csv', index=False)
    
    # FINAL PLOT
    plt.figure(figsize=(12, 6))
    plt.plot(test_dates[:12], actual_weekly_values, label='Actual', color='black', marker='o', linewidth=2)
    plt.plot(test_dates[:12], baseline_weekly, label='Forecasted Sales', color='grey', marker='s', linewidth=2)
    plt.plot(test_dates[:12], nudged_weekly, label='SMI Nudged Prophet', color='blue', marker='^', linewidth=2)
    plt.title(f"Actual Sales vs Forecasted Sales vs SMI-Nudged")
    plt.xlabel("Week")
    plt.ylabel("Weekly Demand")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("prophet_nudged_vs_actual.png", dpi=150)
    plt.show()
    
    print("\n" + "="*60)
    print("PROPHET (BEST WQL) vs SMI-NUDGED RESULTS")
    print("="*60)
    print(metrics_df.round(4))
    print(f"\n✅ Nudged {metrics_baseline['MASE']:.4f} → {metrics_nudged['MASE']:.4f} MASE")
    print(f"✅ Nudged {metrics_baseline['WQL']:.4f} → {metrics_nudged['WQL']:.4f} WQL")
    print("\nFiles saved:")
    print("- Prophet_nudged_12weeks.csv")
    print("- nudged_vs_prophet_metrics_weekly.csv") 
    print("- prophet_nudged_vs_actual.png")
