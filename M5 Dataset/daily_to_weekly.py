import pandas as pd

# 1. Load the dataset
# Replace the file path if necessary
df = pd.read_csv('m5_FOODS_3_090_CA_3_evaluation.csv')

# 2. Convert 'date' to datetime format (based on the DD-MM-YYYY format in your CSV)
df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y')

# 3. Set 'date' as index for easier manipulation
df.set_index('date', inplace=True)

# 4. Fill gaps in dates with 0 sales
# Create a continuous date range from the first to the last available date
full_range = pd.date_range(start=df.index.min(), end=df.index.max(), freq='D')
# Reindex the DataFrame to include all dates, filling gaps with 0
df_reindexed = df.reindex(full_range, fill_value=0)

# 5. Aggregate daily sales, anchored to FRIDAY ('W-FRI')
# This sums up the sales for the week ending on each Friday
df_weekly = df_reindexed.resample('W-FRI').sum()

# Reset index for the final output
df_weekly.index.name = 'week_ending_friday'
df_weekly.reset_index(inplace=True)

# 6. Save the results
df_weekly.to_csv('aggregated_weekly_sales.csv', index=False)

# Display the first few rows of the aggregated results
print(df_weekly.head())
