import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import time
import redis

# Redis client configuration with retry
redis_client = None
attempts = 0
max_attempts = 10
while not redis_client and attempts < max_attempts:
    try:
        redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)
        redis_client.ping()  # Test connection
        print("Successfully connected to Redis!")
    except Exception as e:
        attempts += 1
        print(f"Failed to connect to Redis (attempt {attempts}/{max_attempts}): {e}")
        time.sleep(5)
if not redis_client:
    raise Exception("Could not connect to Redis after maximum attempts")

# Redis key for the data list
REDIS_KEY = "supply_chain_data"

# Define four random products
PRODUCTS = ["Product A", "Product B", "Product C", "Product D"]

# Track the last used timestamp to avoid duplicates
last_timestamp = None

# Simulate initial 1,000 hours of sales data for each product (for testing)
np.random.seed(42)
start_date = datetime(2023, 1, 1)
dates = [start_date + timedelta(hours=i) for i in range(1000)]

# Generate sales data for each product
sales_data = {}
for product in PRODUCTS:
    sales = np.random.normal(loc=25, scale=5, size=1000).astype(int)  # Mean 25 units per product (total ~100)
    sales[500] = 75  # Anomaly: Spike for each product
    sales[750] = 2   # Anomaly: Drop for each product
    sales_data[product] = pd.Series(sales, index=dates)

# Send initial data to Redis
for i, date in enumerate(dates):
    product_sales = {product: int(sales_data[product][date]) for product in PRODUCTS}
    message = {
        "timestamp": date.strftime('%Y-%m-%d %H:%M:%S'),
        "sales": product_sales  # Dictionary with sales for each product
    }
    redis_client.rpush(REDIS_KEY, json.dumps(message))
    redis_client.ltrim(REDIS_KEY, -2000, -1)  # Keep only the last 2000 messages
    print(f"Sent initial data to Redis: {message}")
    last_timestamp = date

# Simulate streaming data (new data every hour)
current_date = dates[-1] + timedelta(hours=1)
hour_counter = 1000  # Start from the last hour of initial data
while True:
    # Ensure unique timestamp
    while current_date <= last_timestamp:
        current_date += timedelta(seconds=1)  # Increment by 1 second if duplicate
        print(f"Adjusted timestamp to avoid duplicate: {current_date}")
    last_timestamp = current_date

    # Generate sales for each product
    product_sales = {}
    for product in PRODUCTS:
        new_sale = np.random.normal(loc=25, scale=5)  # Simulate new hourly sale for each product
        # Introduce anomalies every 10th hour for testing
        hour_counter += 1
        if hour_counter % 10 == 0:  # Simplified anomaly condition
            new_sale = 75 if np.random.rand() > 0.5 else 2  # Random spike or drop
            print(f"Anomaly introduced for {product} at hour {hour_counter} ({current_date}): {new_sale}")
        product_sales[product] = int(new_sale)

    message = {
        "timestamp": current_date.strftime('%Y-%m-%d %H:%M:%S'),
        "sales": product_sales
    }
    redis_client.rpush(REDIS_KEY, json.dumps(message))
    redis_client.ltrim(REDIS_KEY, -2000, -1)  # Keep only the last 2000 messages
    print(f"Sent streaming data to Redis: {message}")
    current_date += timedelta(hours=1)
    time.sleep(10)  # Delay of 10 seconds