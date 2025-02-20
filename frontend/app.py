import redis
import threading
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app)

# Connect to Redis
redis_client = redis.Redis(host='redis', port=6379, db=0)

# Global list to store alerts
alerts = []

def update_alerts():
    global alerts
    pubsub = redis_client.pubsub()
    pubsub.subscribe('alerts_channel')
    
    for message in pubsub.listen():
        if message['type'] == 'message':
            alert = message['data'].decode('utf-8')
            alerts.append(alert)
            socketio.emit('alert_update', alert)  # Emit to all connected clients
            if len(alerts) > 100:
                alerts.pop(0)

def update_health_status():
    pubsub = redis_client.pubsub()
    pubsub.subscribe('health_status_channel')
    
    for message in pubsub.listen():
        if message['type'] == 'message':
            health_status = json.loads(message['data'].decode('utf-8'))
            socketio.emit('health_status_update', health_status)

def update_plot():
    pubsub = redis_client.pubsub()
    pubsub.subscribe('plot_channel')
    
    for message in pubsub.listen():
        if message['type'] == 'message':
            plot_data = json.loads(message['data'].decode('utf-8'))
            socketio.emit('plot_update', plot_data)

# Start threads for alerts, health status, and plot updates
threading.Thread(target=update_alerts, daemon=True).start()
threading.Thread(target=update_health_status, daemon=True).start()
threading.Thread(target=update_plot, daemon=True).start()

@app.route('/')
def index():
    return render_template('index.html', alerts=alerts)

@app.route('/latest_plot')
def get_latest_plot():
    plot_filename = redis_client.get('latest_plot')
    if plot_filename:
        plot_filename = plot_filename.decode('utf-8')
        plot_path = f'/static/plots/{plot_filename}'
        return plot_path
    return jsonify({'error': 'No plot available'}), 404  # Return a JSON error with 404 status if no plot exists

@app.route('/report_false_positive', methods=['POST'])
def report_false_positive():
    data = request.json
    if not data or 'alert' not in data:
        return jsonify({'error': 'Missing alert data'}), 400
    
    alert = data['alert']
    redis_client.publish('false_positive_channel', json.dumps({'alert': alert, 'timestamp': datetime.now().isoformat()}))
    return jsonify({'message': 'False positive reported successfully'}), 200

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)