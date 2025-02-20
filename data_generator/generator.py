import redis
import json
import random
import time
from datetime import datetime, timedelta

# Connect to Redis
redis_client = redis.Redis(host='redis', port=6379, db=0)

def generate_supply_chain_data():
    while True:
        timestamp = datetime.now().isoformat()
        # Simulate data for 3 products (e.g., MACH-1, MACH-2, MACH-3 as products)
        for product_id in ['PROD-1', 'PROD-2', 'PROD-3']:
            # Historical sales (random walk with noise)
            historical_sales = random.uniform(50, 150) * (1 + random.uniform(-0.1, 0.1))
            # Current inventory (decreasing with sales, random restocks)
            inventory = max(0, random.uniform(100, 300) - historical_sales * random.uniform(0.5, 1.5))
            # Market trend (e.g., demand increase/decrease)
            market_trend = random.uniform(0.9, 1.1)  # Slight variation in demand
            # Supplier delay (in hours, simulating logistics)
            supplier_delay = random.uniform(1, 48)  # Hours

            data = {
                'timestamp': timestamp,
                'product_id': product_id,
                'sales': historical_sales,
                'inventory': inventory,
                'market_trend': market_trend,
                'supplier_delay': supplier_delay
            }
            redis_client.publish('supply_chain_data', json.dumps(data))
        time.sleep(1)  # Simulate real-time data every second

if __name__ == '__main__':
    generate_supply_chain_data()