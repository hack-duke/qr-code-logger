import os
import json
from flask import Flask, request, jsonify, render_template
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
            return jsonify({'error': 'Invalid request'}), 400

        user_id = data['qrCode']
        name = resolve_name(user_id)

        if not name: 
            print("User not found in DB", user_id)
            return jsonify({'error': 'Could not resolve name for user ID'}), 400

        if not any(entry['user_id'] == user_id for entry in user_log):
            user_log.insert(0, {'user_id': user_id, 'name': name})
            save_user_log(user_log) 
            socketio.emit('update_log', {
                'log': user_log, 
                'total_users': len(user_log)
            })
            print("logged user", name)
        return jsonify({'message': 'User logged successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/log', methods=['GET'])
def display_log():
    return render_template('log_with_search.html')

@socketio.on('request_initial_log')
def handle_initial_log_request():
    emit('update_log', {'log': user_log, 'total_users': len(user_log)})

@socketio.on('search_log')
def handle_search_log(data):
    try:
        query = data.get('query', '').lower()  # Get the query and convert to lowercase for case-insensitive search
        if not query:
            emit('search_results', {'log': user_log})  # Return the full log if the query is empty
            return

        # Filter the log for matching entries
        filtered_log = [entry for entry in user_log if query in entry['name'].lower()]

        # Emit the filtered results
        emit('search_results', {'log': filtered_log})
    except Exception as e:
        print(f"Error in search_log: {e}")
        emit('search_results', {'log': []})  # Return an empty log on error

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8000)
