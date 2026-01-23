import pandas as pd
import numpy as np
import time
import os

# Configuration
output_dir = 'data'
output_file = os.path.join(output_dir, 'btc_usdt_30d_synthetic.csv')
num_rows = 86400  # Number of candles, matching other tests
start_price = 50000
volatility = 0.02
volume_mean = 100

# Create directory if it doesn't exist
os.makedirs(output_dir, exist_ok=True)

# Generate timestamps (1-minute intervals)
now = int(time.time())
timestamps = np.arange(now - (num_rows * 60), now, 60)

# Generate price data
# Use a more realistic price walk
price_changes = 1 + np.random.normal(0, volatility / np.sqrt(24*60), num_rows)
prices = start_price * np.cumprod(price_changes)

# Generate ohlc data
open_prices = prices[:-1]
close_prices = prices[1:]

# Ensure high is the highest and low is the lowest
price_min = np.minimum(open_prices, close_prices)
price_max = np.maximum(open_prices, close_prices)
high_prices = price_max + np.random.uniform(0, volatility * 50, num_rows - 1)
low_prices = price_min - np.random.uniform(0, volatility * 50, num_rows - 1)


# Generate volume
volumes = np.random.poisson(volume_mean, num_rows - 1).astype(float)

# Create DataFrame
df = pd.DataFrame({
    'timestamp': timestamps[1:],
    'open': open_prices,
    'high': high_prices,
    'low': low_prices,
    'close': close_prices,
    'volume': volumes,
})

# Save to CSV
df.to_csv(output_file, index=False)

print(f"Successfully generated test data with {len(df)} rows into {output_file}")
