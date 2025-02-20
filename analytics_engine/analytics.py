import redis
import json
import time
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from collections import deque
from datetime import datetime, timedelta
import statsmodels.api as sm

# Connect to Redis
redis_client = redis.Redis(host='redis', port=6379, db=0)

# Initialize models and data structures
models = {}
scalers = {}
historical_data = {}  # {product_id: deque of readings}
anomaly_history = {}  # {product_id: [timestamps]}
false_positives = []  # Store false positive reports: [{'alert': str, 'timestamp': datetime}]
WINDOW_SIZE = 24  # 24 hours of data for forecasting

def fit_initial_models():
    initial_data = []
    for _ in range(100):  # Collect 100 initial readings
        reading = redis_client.blpop('supply_chain_data')[1].decode('utf-8')
        reading = json.loads(reading)
        initial_data.append([reading['sales'], reading['inventory']])
    
    for product_id in set(reading['product_id'] for reading in initial_data):
        mask = [r['product_id'] == product_id for r in initial_data]
        product_data = np.array([initial_data[i] for i in range(len(initial_data)) if mask[i]])
        scalers[product_id] = StandardScaler().fit(product_data)
        models[product_id] = IsolationForest(contamination=0.1, random_state=42).fit(scalers[product_id].transform(product_data))
        historical_data[product_id] = deque(maxlen=WINDOW_SIZE)
        anomaly_history[product_id] = []

def process_reading(reading):
    product_id = reading['product_id']
    timestamp = datetime.fromisoformat(reading['timestamp'].replace('Z', '+00:00'))
    sales = reading['sales']
    inventory = reading['inventory']
    market_trend = reading['market_trend']
    supplier_delay = reading['supplier_delay']

    # Store historical data
    historical_data[product_id].append({'timestamp': timestamp, 'sales': sales, 'inventory': inventory})

    # Scale the reading
    scaled_reading = scalers[product_id].transform([[sales, inventory]])[0]

    # Predict anomaly (e.g., stockouts or excess inventory)
    anomaly_score = models[product_id].decision_function([scaled_reading])[0]
    is_anomaly = anomaly_score < 0  # Negative score indicates anomaly

    # Demand forecasting using simple moving average (SMA)
    if len(historical_data[product_id]) >= WINDOW_SIZE:
        sales_history = [d['sales'] for d in historical_data[product_id]]
        forecast = np.mean(sales_history[-WINDOW_SIZE:]) * market_trend  # Adjusted by market trend
    else:
        forecast = sales * market_trend  # Initial estimate

    # Inventory optimization (simplified reinforcement learning: rule-based)
    optimal_inventory = forecast * 1.2  # Buffer for 20% safety stock
    inventory_alert = False
    if inventory < 0.1 * optimal_inventory:  # Stockout risk
        inventory_alert = True
    elif inventory > 2 * optimal_inventory:  # Excess inventory
        inventory_alert = True

    # Calculate health score (0-100, higher is better)
    health_score = 100 - (abs(inventory - optimal_inventory) / optimal_inventory * 100)
    health_score = max(0, min(100, health_score))

    # Refine anomaly: only flag if significant deviation or alert
    significant_deviation = (inventory < 10 or inventory > 500)  # Example thresholds
    is_anomaly = is_anomaly and (inventory_alert or significant_deviation)

    # Track anomalies
    if is_anomaly:
        anomaly_history[product_id].append(timestamp)

    # Publish health status for real-time updates
    health_status = {
        'product_id': product_id,
        'timestamp': timestamp.isoformat(),
        'sales': sales,
        'inventory': inventory,
        'forecast': forecast,
        'health_score': health_score,
        'is_anomaly': is_anomaly,
        'market_trend': market_trend,
        'supplier_delay': supplier_delay
    }
    redis_client.publish('health_status_channel', json.dumps(health_status))

    # Publish alerts for anomalies
    if is_anomaly:
        alert = f"ALERT at {timestamp.isoformat()}: Product {product_id} - Health Score: {health_score:.2f}, Anomaly: {inventory_alert}, Sales: {sales:.2f}, Inventory: {inventory:.2f}"
        redis_client.publish('alerts_channel', alert)
        with open('/app/alerts.log', 'a') as f:
            f.write(alert + '\n')

    # Real-time plot: demand forecast and anomalies over time
    update_realtime_plot(product_id, timestamp, sales, forecast, is_anomaly)

def update_realtime_plot(product_id, timestamp, sales, forecast, is_anomaly):
    # Track demand and anomalies for plotting
    if 'demand_history' not in globals():
        global demand_history
        demand_history = {pid: {'timestamps': [], 'sales': [], 'forecast': [], 'anomalies': []} for pid in ['PROD-1', 'PROD-2', 'PROD-3']}
    
    demand_history[product_id]['timestamps'].append(timestamp)
    demand_history[product_id]['sales'].append(sales)
    demand_history[product_id]['forecast'].append(forecast)
    demand_history[product_id]['anomalies'].append(1 if is_anomaly else 0)

    # Limit history to last 7 days for performance
    cutoff = timestamp - timedelta(days=7)
    for key in ['timestamps', 'sales', 'forecast', 'anomalies']:
        demand_history[product_id][key] = [val for val, ts in zip(demand_history[product_id][key], demand_history[product_id]['timestamps']) if ts > cutoff]
        demand_history[product_id]['timestamps'] = [ts for ts in demand_history[product_id]['timestamps'] if ts > cutoff]

    # Prepare plot data for Chart.js (demand trends and anomalies)
    plot_data = {
        'labels': [t.strftime('%Y-%m-%d %H:%M') for t in demand_history[product_id]['timestamps']],
        'datasets': [
            {
                'label': f'{product_id} - Actual Sales',
                'data': demand_history[product_id]['sales'],
                'borderColor': 'blue',
                'fill': False
            },
            {
                'label': f'{product_id} - Forecast',
                'data': demand_history[product_id]['forecast'],
                'borderColor': 'green',
                'fill': False,
                'borderDash': [5, 5]  # Dashed line for forecast
            },
            {
                'label': f'{product_id} - Anomalies',
                'data': demand_history[product_id]['anomalies'],
                'borderColor': 'red',
                'fill': False,
                'type': 'scatter',  # Use scatter for anomalies (points)
                'pointBackgroundColor': 'red',
                'pointRadius': 5
            }
        ]
    }
    redis_client.publish('plot_channel', json.dumps(plot_data))

def handle_false_positives():
    pubsub = redis_client.pubsub()
    pubsub.subscribe('false_positive_channel')
    
    while True:
        message = pubsub.get_message()
        if message and message['type'] == 'message':
            false_positive = json.loads(message['data'].decode('utf-8'))
            alert = false_positive['alert']
            timestamp_str = false_positive['timestamp']
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            
            # Parse alert to extract product_id and reading details
            try:
                # Example alert format: "ALERT at 2025-02-19T15:30:00: Product PROD-1 - Health Score: 65.43, Anomaly: True, Sales: 120.50, Inventory: 50.20"
                parts = alert.split(' - ')
                product_id = parts[1].split()[1]  # Extract product_id (e.g., PROD-1)
                sales = float(parts[3].split(': ')[1])  # Extract sales
                inventory = float(parts[4].split(': ')[1])  # Extract inventory
                
                # Add to false_positives list with reading data
                false_positives.append({
                    'product_id': product_id,
                    'timestamp': timestamp,
                    'sales': sales,
                    'inventory': inventory
                })
                
                # Retrain model excluding false positives
                retrain_model(product_id)
            except (IndexError, ValueError) as e:
                print(f"Error parsing false positive alert: {e}")
        time.sleep(0.1)  # Small delay to prevent CPU overuse

def retrain_model(product_id):
    # Collect historical data excluding false positives
    valid_data = []
    for reading in historical_data[product_id]:
        reading_ts = reading['timestamp']
        if not any(fp['timestamp'] == reading_ts and fp['product_id'] == product_id for fp in false_positives):
            valid_data.append([reading['sales'], reading['inventory']])
    
    if valid_data:
        valid_data = np.array(valid_data)
        scalers[product_id] = StandardScaler().fit(valid_data)
        models[product_id] = IsolationForest(contamination=0.1, random_state=42).fit(scalers[product_id].transform(valid_data))
        print(f"Model for {product_id} retrained after false positive report")
        
        # Publish updated model performance (simplified metric)
        accuracy = 0.95  # Placeholder, replace with actual metric calculation
        redis_client.publish('model_update_channel', json.dumps({
            'product_id': product_id,
            'accuracy': accuracy
        }))

# ... (previous imports and setup remain the same)

def process_reading(reading):
    # ... (existing logic for processing supply chain data)
    redis_client.publish('supply_chain_data', json.dumps(reading))  # Store raw data
    redis_client.publish('health_status_channel', json.dumps(health_status))
    if is_anomaly:
        redis_client.publish('alerts_channel', alert)
    update_realtime_plot(product_id, timestamp, sales, forecast, is_anomaly)

def update_realtime_plot(product_id, timestamp, sales, forecast, is_anomaly):
    # ... (existing plot data preparation)
    redis_client.publish('plot_channel', json.dumps(plot_data))

# ... (handle_false_positives and retrain_model remain the same for false positives)

if __name__ == '__main__':
    fit_initial_models()
    
    # Start thread for false positive handling
    threading.Thread(target=handle_false_positives, daemon=True).start()
    
    pubsub = redis_client.pubsub()
    pubsub.subscribe('supply_chain_data')
    for message in pubsub.listen():
        if message['type'] == 'message':
            reading = json.loads(message['data'].decode('utf-8'))
            process_reading(reading)