import os
import json
from flask import Flask, request, jsonify, render_template_string
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from pymongo import MongoClient

app = Flask(__name__)
socketio = SocketIO(app)

DATA_FILE = 'user_log.json'

load_dotenv()
MONGO = os.getenv('MONGODB_URI')
client = MongoClient(MONGO)
db = client.get_database('test')
collection = db['cfg2025']

def load_user_log():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as file:
            return json.load(file)
    return []

def save_user_log(log):
    with open(DATA_FILE, 'w') as file:
        json.dump(log, file)

user_log = load_user_log()

@app.route('/')
def index():
    return app.send_static_file('index.html')

def resolve_name(user_id):
    try:
        user = collection.find_one({'userId': user_id})
        return user['name'] if user else None
    except Exception as e:
        print(f"Error resolving name: {e}")
        return None

@app.route('/log_user', methods=['POST'])
def log_user():
    try:
        data = request.json
        if not data or 'qrCode' not in data:
            # Emit notification for invalid request
            socketio.emit('notification', {
                'success': False,
                'message': 'Invalid request'
            })
            return jsonify({'error': 'Invalid request'}), 400

        user_id = data['qrCode']
        name = resolve_name(user_id)
        if not name:
            # Emit notification for user not found
            socketio.emit('notification', {
                'success': False,
                'message': 'User not found in DB'
            })
            return jsonify({'error': 'User not found in DB'}), 400

        # Successfully resolved user:
        if not any(entry['user_id'] == user_id for entry in user_log):
            user_log.insert(0, {'user_id': user_id, 'name': name})
            save_user_log(user_log)
            # Notify all connected clients to update log
            socketio.emit('update_log', {
                'log': user_log,
                'total_users': len(user_log)
            })
            # Emit success notification
            socketio.emit('notification', {
                'success': True,
                'message': 'Check-in successful'
            })
        return jsonify({'message': 'User logged successfully'}), 200

    except Exception as e:
        socketio.emit('notification', {
            'success': False,
            'message': f'Error: {str(e)}'
        })
        return jsonify({'error': str(e)}), 500

@app.route('/log', methods=['GET'])
def display_log():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>User Log</title>
        <style>
        /* Container for notifications */
        #notification-container {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            display: flex;
            flex-direction: column;
            align-items: flex-end;
        }
        .notification {
            padding: 10px 15px;
            margin-bottom: 10px;
            border-radius: 4px;
            color: #fff;
            transition: opacity 1s; /* fade out transition [3][5] */
            opacity: 1;
        }
        .success {
            background-color: #4CAF50;
        }
        .error {
            background-color: #f44336;
        }
        .fade-out {
            opacity: 0;
        }
        </style>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.6.1/socket.io.min.js"></script>
        <script>
            document.addEventListener('DOMContentLoaded', () => {
                const socket = io();
                const notificationContainer = document.createElement('div');
                notificationContainer.id = 'notification-container';
                document.body.appendChild(notificationContainer);

                // Request initial log data on connection
                socket.on('connect', () => {
                    socket.emit('request_initial_log');
                });

                // Update log display
                socket.on('update_log', (data) => {
                    document.getElementById('total-users').textContent = data.total_users;
                    const logDiv = document.getElementById('log');
                    logDiv.innerHTML = '';
                    data.log.forEach(entry => {
                        const p = document.createElement('p');
                        p.textContent = entry.name;
                        logDiv.appendChild(p);
                    });
                });

                // Show notifications
                socket.on('notification', (data) => {
                    const div = document.createElement('div');
                    div.classList.add('notification');
                    if (data.success) {
                        div.classList.add('success');
                    } else {
                        div.classList.add('error');
                    }
                    div.textContent = data.message;
                    notificationContainer.appendChild(div);

                    // Fade out after 3s, then remove [3][5]
                    setTimeout(() => {
                        div.classList.add('fade-out');
                    }, 3000);
                    setTimeout(() => {
                        notificationContainer.removeChild(div);
                    }, 4000);
                });
            });
        </script>
    </head>
    <body>
        <h1>Checked-In Users</h1>
        <p><strong>Total Users:</strong> <span id="total-users">0</span></p>
        <p><strong>Log (Most Recent to Oldest):</strong></p>
        <div id="log">No users checked in yet.</div>
    </body>
    </html>
    """
    return render_template_string(html)

@socketio.on('request_initial_log')
def handle_initial_log_request():
    emit('update_log', {'log': user_log, 'total_users': len(user_log)})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8000)
