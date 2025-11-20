# app.py
from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from datetime import datetime
import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor

# Kafka integration
from kafka import KafkaProducer, KafkaConsumer
import threading

app = Flask(__name__)
app.secret_key = 'aniflow_secret_key_123'

# Supabase Configuration
# Use this EXACT format:
SUPABASE_DB_URL = 'postgresql://postgres.tjrbxmwippcvwpkclxwd:animeftw@aws-1-us-east-2.pooler.supabase.com:5432/postgres'
def get_db_connection():
    """Create and return a database connection"""
    try:
        conn = psycopg2.connect(SUPABASE_DB_URL)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

# Kafka Configuration
class KafkaManager:
    def __init__(self):
        self.bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        self.producer = None
    
    def get_producer(self):
        if not self.producer:
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=[self.bootstrap_servers],
                    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                    retries=3
                )
            except Exception as e:
                print(f"Kafka producer error: {e}. Using mock producer.")
                self.producer = MockProducer()
        return self.producer
    
    def send_event(self, topic, event_data):
        try:
            producer = self.get_producer()
            future = producer.send(topic, event_data)
            print(f"📨 Sent event to {topic}: {event_data.get('event_type')}")
            return True
        except Exception as e:
            print(f"Failed to send event: {e}")
            return False
#==========================

if __name__ == '__main__':
    print("Starting Flask server on http://localhost:5000")
    print("Testing database connection...")
    
    app.run(debug=True, port=5000)