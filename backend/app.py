from flask import Flask, Response
from flask_cors import CORS
import json
import numpy as np
import pandas as pd
from datetime import datetime
import time
import redis

app = Flask(__name__)
CORS(app)

# Redis client configuration with retry
redis_client = None
attempts = 0
max_attempts = 10
while not redis_client and attempts < max_attempts:
    try:
        redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)
        redis_client.ping()
        print("Successfully connected to Redis!")
    except Exception as e:
        attempts += 1
        print(f"Failed to connect to Redis (attempt {attempts}/{max_attempts}): {e}")
        time.sleep(5)
if not redis_client:
    raise Exception("Could not connect to Redis after maximum attempts")

# Redis key for the data list
REDIS_KEY = "supply_chain_data"

# Define the products
PRODUCTS = ["Product A", "Product B", "Product C", "Product D"]

# Store sales data for each product
sales_data = {product: pd.Series(dtype=float) for product in PRODUCTS}
last_forecast = {product: 25 for product in PRODUCTS}  # Initial fallback forecast
current_inventory = {product: 25 for product in PRODUCTS}  # Initial inventory
forecast_counter = 0  # To control forecasting frequency

# Predictive Analytics: Simple moving average for demand forecasting
def forecast_demand(data):
    try:
        if len(data) < 24:
            return data.iloc[-1] if len(data) > 0 else 25
        return data[-24:].mean()  # Moving average of last 24 hours
    except Exception as e:
        print(f"Forecasting error: {e}")
        return data.iloc[-1] if len(data) > 0 else 25

# Reinforcement Learning: Q-learning for inventory optimization
def q_learning_inventory(demand_forecast, current_inventory, max_inventory=50):
    actions = [-5, 0, 5]  # Decrease, hold, increase inventory (smaller steps for per-product)
    reward = -abs(demand_forecast - current_inventory)  # Negative penalty for mismatch
    best_action = actions[np.argmax([reward + 0.9 * (-abs(demand_forecast - (current_inventory + a))) for a in actions])]
    next_inventory = max(0, min(max_inventory, current_inventory + best_action))
    return next_inventory

# Detect anomalies (threshold-based)
def detect_anomalies(data, threshold=1.5):
    if len(data) < 2:
        print("Not enough data for anomaly detection (len < 2)")
        return False
    mean, std = data.mean(), data.std()
    latest_value = data.iloc[-1]
    upper_bound = mean + threshold * std
    lower_bound = mean - threshold * std
    is_anomaly = latest_value > upper_bound or latest_value < lower_bound
    print(f"Anomaly check: latest={latest_value}, mean={mean}, std={std}, upper={upper_bound}, lower={lower_bound}, is_anomaly={is_anomaly}")
    return is_anomaly

# Streaming endpoint (Server-Sent Events)
@app.route('/stream')
def stream():
    def generate():
        global sales_data, last_forecast, current_inventory, forecast_counter
        last_index = -1  # Keep track of the last processed index
        
        while True:
            # Get the length of the list
            redis_start = time.time()
            list_length = redis_client.llen(REDIS_KEY)
            print(f"Redis LLEN took {time.time() - redis_start:.2f} seconds")
            
            # Process new messages in batches (up to 5 at a time)
            batch_size = 5
            new_messages = min(batch_size, list_length - (last_index + 1))
            if new_messages > 0:
                start_time = time.time()
                latest_timestamp = None
                for i in range(last_index + 1, last_index + 1 + new_messages):
                    redis_fetch_start = time.time()
                    message = json.loads(redis_client.lindex(REDIS_KEY, i))
                    print(f"Redis LINDEX took {time.time() - redis_fetch_start:.2f} seconds")
                    print(f"Consumed message from Redis: {message}")
                    timestamp = datetime.strptime(message['timestamp'], '%Y-%m-%d %H:%M:%S')
                    latest_timestamp = timestamp
                    product_sales = message['sales']
                    
                    # Update sales data for each product
                    for product in PRODUCTS:
                        sale = product_sales[product]
                        new_data = pd.Series([sale], index=[timestamp])
                        sales_data[product] = pd.concat([sales_data[product], new_data])
                        
                        # Convert index to datetime
                        sales_data[product].index = pd.to_datetime(sales_data[product].index)
                        
                        # Handle duplicates by taking the mean of sales for duplicate timestamps
                        if sales_data[product].index.duplicated().any():
                            print(f"Found duplicate timestamps in sales_data for {product}, aggregating...")
                            sales_data[product] = sales_data[product].groupby(sales_data[product].index).mean()
                        
                        # Keep only the last 1000 data points for efficiency
                        if len(sales_data[product]) > 1000:
                            sales_data[product] = sales_data[product][-1000:]
                
                # Process the batch: Forecast, optimize inventory, detect anomalies for each product
                forecast_counter += new_messages
                product_forecasts = {}
                product_inventories = {}
                product_anomalies = {}
                if forecast_counter >= 10:  # Forecast every 10 messages
                    forecast_start = time.time()
                    for product in PRODUCTS:
                        last_forecast[product] = forecast_demand(sales_data[product])
                    print(f"Forecasting took {time.time() - forecast_start:.2f} seconds")
                    forecast_counter = 0
                
                # Inventory optimization and anomaly detection for each product
                for product in PRODUCTS:
                    forecast = last_forecast[product]
                    product_forecasts[product] = forecast
                    
                    inventory_start = time.time()
                    current_inventory[product] = q_learning_inventory(forecast, current_inventory[product])
                    product_inventories[product] = current_inventory[product]
                    print(f"Inventory optimization for {product} took {time.time() - inventory_start:.2f} seconds")
                    
                    anomaly_start = time.time()
                    product_anomalies[product] = detect_anomalies(sales_data[product])
                    print(f"Anomaly detection for {product} took {time.time() - anomaly_start:.2f} seconds")

                # Prepare response for the last message in the batch
                response = {
                    "timestamp": latest_timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    "sales": product_sales,
                    "forecasted_demand": {product: float(product_forecasts[product]) for product in PRODUCTS},
                    "optimal_inventory": {product: int(product_inventories[product]) for product in PRODUCTS},
                    "is_anomaly": {product: bool(product_anomalies[product]) for product in PRODUCTS}
                }
                yield f"data: {json.dumps(response)}\n\n"
                print(f"Total processing time for batch of {new_messages} messages: {time.time() - start_time:.2f} seconds")
            
            # Update the last processed index
            last_index += new_messages
            
            # Wait before checking for new data
            time.sleep(30)  # Process a batch every 30 seconds

    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)