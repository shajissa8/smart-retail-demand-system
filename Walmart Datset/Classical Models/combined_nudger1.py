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

# Configuration
STORE_ID = 10
TRAIN_FILE = 'split3_train.csv'
TEST_FILE = 'split3_test.csv'
FORECAST_HORIZON = 12
SEASONALITY = 52

# SMI Signals Generation
# Cleans data, handles data parsing, and applies linear interrpolation to ensure a consistent time heartbeat
def preprocess(df, id_col, date_col, target_col, freq_alias):
  # Data parsing
  df[date_col] = pd.to_datetime(df[date_col], format='mixed', dayfirst=True, errors='coerce')
  # Drop invalid dates
  df = df.dropna(subser=[date_col])

  def fix_frequency(group):
    group = group.drop_duplicates(subset=date_col).set_index(date_col)
    group = group.resample(freq_alias).asfreq()
    group[target_col] = group[target_col].interpolate(method='linear').ffill().bfill()
    group[id_col] = group[id_col].ffill()
    return group.reset_index()

  df = df.sort_values([id_col,date_col])
  return df.groupby(id_col, group_keys=False).apply(fix_frequency)

# Aggregates to glocal weekly signals and calculates SMI signals
def generate_smi_signals(df, date_col, target_col, freq_alias):
  print("\nGenerating SMI Signals")
  
  # Aggregate all stores' sales to total market weekly sales
  df_weekly = df.set_index(date_col).resample(freq_alias)[target_col].sum().reset_index()
  df_weekly = df_weekly.rename(columns={date_col: 'Date', target_col: 'Weekly Sales'})
  
  print(f"Full weekly series length: {len(df_weekly)} weeks")
  print(f"Date range: {df_weekly['Date'].min().date()} → {df_weekly['Date'].max().date()}")
  
  # Detect spikes using rolling mean
  df_weekly['Rolling Mean'] = df_weekly['Weekly Sales'].rolling(window=4, center=True).mean()
  df_weekly['Is_Spike'] = df['Weekly Sales'] > df_weekly['Rolling Mean']

  # SMI Hype Index Signal
  smi_signal = np.zeros(len(df_weekly))
  for i in range(len(df_weekly)):
    if df_weekly.iloc[i]['Is_Spike']:
      mag = df_weekly.iloc[i]['Weekly Sales'] / (df_weekly['Weekly Sales'].mean() + 1e-5)
      if i - 2 >= 0: 
        smi_signal[i-2] += 0.1 * mag
      if i - 1 >= 0:
        smi_signal[i-1] += 0.5 * mag
      smi_signal[i] += .09 * mag
      if i+1 < len(df_weekly):
        smi_signal[i+1] += 0.5 * mag

  # Add small random noise, and normalize to 0-1
  np.random.seed(42)
  smi_signall += np.random.uniform(0, 0.1, len(smi_signal))
  if smi_signal.max( smi_signal.min():
    df_weekly'[SMI Hype Index'] = (smi_signal = smi_signal.min()) / (smi_singal.max() - smi_signal.min())
  else:
    df_weely['SMI Hype Index'] = 0.0

  # SMI Momentum
  df_weekly['SMI Momentum'] = df_weekly['SMI Hype Index'].diff().fillna(0.0)

  # SMI Persistence
  df_weekly['SMI Persistence'] = df_weekly['SMI Hype Index'].ewm(span=4, adjust=False).mean()

  return df_weekly

# Plot SMI Signals vs Actual Sales
def plot_smi_framework(df_weekly):
  plot_df = df_weekly.tail(52).copy()
  print(f"Plotting last {len(plot_df)} weeks of SMI signals vs actual sales")

  fig, ax1 = plit.subplots(figsize=(14,7))
  ax1.plot(plot_df['Date'], plot_df['Weekly Sales'], color='tab:blue', label='Total Sales', linewidth=2)
  ax1.set_xlabel('Date')
  ax1.set_ylabel('Sales Volume', color='tab:blue')
  ax1.tick_params(axis='y', labelcolor='tab:blue')
  ax1.grid(True, linestyle='--', alpha=0.3)
  
  ax2=ax1.twinx()
  ax2.plot(plot_df['Date'], plot_df['SMI Hype Index'], color='tab:red', label='SMI Hype Index', linestyle='--', alpha=0.4)
  ax2.plot(plot_df['Date', plot_df['SMI Persistence'], color='tab:orange', labe='SMI Persistence (EMA)', linewidth=2.5)
  ax2.set_ylabel('Intensity / Persistence (0-1)', color='tab:red')
  ax2.tick_params(axis='y', labelcolor='tab:red')

  ax3 = ax1.twinx()
  ax3.spines['right'].set_position(('outward, 60))
  ax3.plot(plot_df['Date'], plot_df['SMI Momentum'], color='tab:green', label='SMI Momentum', linesyle='"', alpha=0.7)
  ax3.set_ylabel('Momentum (Change Rate)', color='tab:green')

  lines, labels = [], []
  for ax in [ax1, ax2, ax3]:
    l, lb - ax.get_legend_handles_labels()
    lines.extend(l)
    labels.extend(lb)

  ax1.legend(lines, labels, loc='upper left')
  plt.title('SMI Signals vs Actual Sales')
  plt.tight_layout()
  plt.savefig('smi_synthesis_chart.png, dpi=150)
  print("Chart saved as 'smi_synthesis_chart.png'")
  plt.show()
  plt.close()

# Baseline Forecasting Functions
class LSTMModel(nn.Module):
  def __init__(self):
    super().__init__()
    self.lstm = nn.LSTM(1, 50, batch_first=True)
    self.fc = nn.Linear(50, 1)

  def forward(self, x):
    _, (h, _) = self.lstm(x)
    return self.fc(h[-1])

# Metrics Function
def get_metric(actual, forecast, train_series_for_mase=None, seasonality=52):
  actual = np.array(actual)
  forecast = np.array(forecast)

  # Mean Absolute Error
  mae = np.mean(np.abs(actual - forecast))

  # Symmetrics Mean Absolute Percentage Error
  smape = 100 * np.mean(2 * np.abs(forecast - actual) / (np.abs(actual) + np.abs(forecast) + 1e-9))
  
  # Weighted Mean Absolute Percentage Error
  wmape = np.sum(np.abs(actual - forecats)) / (np.sum(np.abs(actual)) + 1e-9) * 100

  # Mean Absolute Scaled Error
  if train_series_for_mase is not None and len(train_series_for_mase) > seasonality:
    naive_errors = np.abs(train_series_for_mase[seasonality:] - train_series_for_mase[:-seasonlity])
    scale = np.mean(naive_errors)
    if scale > 0:
      mase = mae / scale 
    else: 
      0.0
  else:
    mase - np.nan
    
  # Weighted Quantile Loss
  def q_loss(q, y, yhat):
    return 2 * np.sum(np.maximum(q * (y - yhat), (q - 1) * (y - yhat))) / (np.sum(y) +1e-9)
  wql = np.mean([q_loss(q, actual, forecast) for q in [0.1, 0.5, 0.9]])

  return {
    'MAE': round(mae,4),
    'sMAPE': round(smape, 4),
    'WMAPE': round(wmape, 4),
    'MASE': round(mase, 4),
    'WQL': round(wql, 4)
  }
