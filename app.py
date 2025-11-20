# app.py
from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from datetime import datetime
import json
import os
import threading

# Kafka integration (optional)
try:
    from kafka import KafkaProducer, KafkaConsumer
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    print("⚠ Kafka not available - event streaming disabled")

app = Flask(__name__)
app.secret_key = 'aniflow_secret_key_123'

# Supabase Configuration with SQLAlchemy
SUPABASE_DB_URL = 'postgresql://postgres.tjrbxmwippcvwpkclxwd:animeftw@aws-1-us-east-2.pooler.supabase.com:5432/postgres'
app.config['SQLALCHEMY_DATABASE_URI'] = SUPABASE_DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy with app
from models import db
db.init_app(app)

# Kafka Configuration
class KafkaManager:
    def __init__(self):
        self.bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        self.producer = None
    
    def get_producer(self):
        if not KAFKA_AVAILABLE:
            return None
        if not self.producer:
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=[self.bootstrap_servers],
                    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                    retries=3
                )
            except Exception as e:
                print(f"Kafka producer error: {e}. Event streaming disabled.")
                return None
        return self.producer
    
    def send_event(self, topic, event_data):
        try:
            producer = self.get_producer()
            if not producer:
                print(f"⚠ Event not sent (Kafka unavailable): {topic}")
                return False
            future = producer.send(topic, event_data)
            print(f"📨 Sent event to {topic}: {event_data.get('event_type')}")
            return True
        except Exception as e:
            print(f"Failed to send event: {e}")
            return False


# Database initialization helper
def init_db():
    """Initialize the database with schema"""
    with app.app_context():
        try:
            db.create_all()
            print("✓ Database tables created/verified")
            return True
        except Exception as e:
            print(f"✗ Database initialization error: {e}")
            return False


# Admin routes blueprint
@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "app": "AniFlow",
        "status": "running",
        "endpoints": {
            "import": "POST /admin/import-anime"
        }
    })


@app.route('/admin/import-anime', methods=['POST'])
def admin_import_anime():
    """Import anime data from CSV file"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        if not file.filename.endswith('.csv'):
            return jsonify({"error": "File must be CSV"}), 400
        
        # Import with the service
        from Services.animeImportService import import_anime_csv
        result = import_anime_csv(file, db.session)
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 400


if __name__ == '__main__':
    print("Starting AniFlow Flask server on http://localhost:5000")
    print("Initializing database...")
    
    if init_db():
        print("✓ Ready to serve requests")
    else:
        print("✗ Database initialization failed")
    
    app.run(debug=True, port=5000)