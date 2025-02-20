import redis
import threading
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app)

# Connect to Redis
redis_client = redis.Redis(host='redis', port=6379, db=0)

# Global lists to store data from different channels
supply_chain_data = []
health_status_data = []
alerts_data = []
plot_data = []

def update_supply_chain_data():
    global supply_chain_data
    pubsub = redis_client.pubsub()
    pubsub.subscribe('supply_chain_data')
    
    for message in pubsub.listen():
        if message['type'] == 'message':
            data = json.loads(message['data'].decode('utf-8'))
            supply_chain_data.append(data)
            if len(supply_chain_data) > 1000:  # Limit to last 1000 entries
                supply_chain_data.pop(0)
            socketio.emit('supply_chain_update', data)

def update_health_status():
    global health_status_data
    pubsub = redis_client.pubsub()
    pubsub.subscribe('health_status_channel')
    
    for message in pubsub.listen():
        if message['type'] == 'message':
            data = json.loads(message['data'].decode('utf-8'))
            health_status_data.append(data)
            if len(health_status_data) > 1000:
                health_status_data.pop(0)
            socketio.emit('health_status_update', data)

def update_alerts():
    global alerts_data
    pubsub = redis_client.pubsub()
    pubsub.subscribe('alerts_channel')
    
    for message in pubsub.listen():
        if message['type'] == 'message':
            alert = message['data'].decode('utf-8')
            alerts_data.append(alert)
            if len(alerts_data) > 100:
                alerts_data.pop(0)
            socketio.emit('alert_update', alert)

def update_plot():
    global plot_data
    pubsub = redis_client.pubsub()
    pubsub.subscribe('plot_channel')
    
    for message in pubsub.listen():
        if message['type'] == 'message':
            data = json.loads(message['data'].decode('utf-8'))
            plot_data.append(data)
            if len(plot_data) > 100:
                plot_data.pop(0)
            socketio.emit('plot_update', data)

# Start threads for real-time updates
threading.Thread(target=update_supply_chain_data, daemon=True).start()
threading.Thread(target=update_health_status, daemon=True).start()
threading.Thread(target=update_alerts, daemon=True).start()
threading.Thread(target=update_plot, daemon=True).start()

@app.route('/query')
def query():
    return render_template('query.html', 
                          supply_chain_data=supply_chain_data[:100],  # Show recent data
                          health_status_data=health_status_data[:100],
                          alerts_data=alerts_data[:100],
                          plot_data=plot_data[:100])

@app.route('/api/query_data', methods=['GET'])
def query_data():
    channel = request.args.get('channel', 'supply_chain_data')
    query = request.args.get('query', '').lower()
    
    if channel == 'supply_chain_data':
        data = supply_chain_data
    elif channel == 'health_status_channel':
        data = health_status_data
    elif channel == 'alerts_channel':
        data = alerts_data
    elif channel == 'plot_channel':
        data = plot_data
    else:
        return jsonify({'error': 'Invalid channel'}), 400

    # Filter data based on query (e.g., product_id, timestamp, etc.)
    filtered_data = [item for item in data if query in str(item).lower()]
    return jsonify(filtered_data[:100])  # Limit to 100 results for performance

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5002)  # Use port 5002 to avoid conflicts