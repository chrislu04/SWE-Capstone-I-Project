# app.py - MINIMAL WITH KAFKA, FLASK & HTML TEMPLATES
from flask import Flask, request, jsonify, session, render_template, redirect
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from datetime import datetime
import json
import psycopg2
from psycopg2.extras import RealDictCursor

# Kafka integration
from kafka import KafkaProducer, KafkaConsumer
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

# ===== DATABASE =====
SUPABASE_DB_URL = 'postgresql://postgres.tjrbxmwippcvwpkclxwd:animeftw@aws-1-us-east-2.pooler.supabase.com:5432/postgres'

def get_db_connection():
    try:
        return psycopg2.connect(SUPABASE_DB_URL)
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def execute_query(query, params=None, fetch=False):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            if fetch:
                if query.strip().upper().startswith('SELECT'):
                    result = cursor.fetchall()
                    return [dict(row) for row in result]
                else:
                    return None
            else:
                conn.commit()
                return {"status": "success", "rowcount": cursor.rowcount}
    except Exception as e:
        print(f"Query error: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

def execute_query_one(query, params=None):
    """Execute SQL query and return single result"""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            if query.strip().upper().startswith('SELECT'):
                result = cursor.fetchone()
                return dict(result) if result else None
            else:
                conn.commit()
                return {"status": "success", "rowcount": cursor.rowcount}
    except Exception as e:
        print(f"Query error: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

# Kafka ==========
class KafkaManager:
    def __init__(self):
        self.bootstrap_servers = 'localhost:9092'
        self.producer = None
    
    def get_producer(self):
        if not KAFKA_AVAILABLE:
            return None
        if not self.producer:
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=[self.bootstrap_servers],
                    value_serializer=lambda v: json.dumps(v).encode('utf-8')
                )
            except Exception as e:
                print(f"Kafka producer error: {e}")
                self.producer = None
        return self.producer
    
    def send_event(self, topic, event_data):
        producer = self.get_producer()
        if producer:
            try:
                producer.send(topic, event_data)
                print(f"Sent event to {topic}: {event_data.get('event_type')}")
                return True
            except Exception as e:
                print(f"Failed to send event: {e}")
        return False

kafka_manager = KafkaManager()

def publish_user_rated_anime(user_id, anime_id, score):
    event = {
        "event_type": "user_rated_anime",
        "user_id": str(user_id),
        "anime_id": str(anime_id),
        "score": score,
        "timestamp": datetime.utcnow().isoformat()
    }
    return kafka_manager.send_event("user-behavior-events", event)

# Kafka 
def start_recommendation_consumer():
    def consume_events():
        try:
            consumer = KafkaConsumer(
                'user-behavior-events',
                bootstrap_servers=['localhost:9092'],
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                group_id='aniflow-recommendation-service'
            )
            
            print("Kafka consumer started")
            
            for message in consumer:
                event = message.value
                print(f"Processing: {event['event_type']} for user {event['user_id']}")
                # In real implementation: generate recommendations here
                
        except Exception as e:
            print(f"Kafka consumer error: {e}")
    
    thread = threading.Thread(target=consume_events, daemon=True)
    thread.start()

# ===== Routing =====

@app.route('/')
def welcome():
    return render_template('welcomePage.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
         # we would move this to a service later and call it here
        user = execute_query_one(
            "SELECT userid, passwordhash FROM users WHERE email = %s AND isactive = TRUE",
            (email,)
        )
        
        if user and check_password_hash(user['passwordhash'], password):
            session['user_id'] = str(user['userid'])
            return redirect('/home')
        
        return render_template('login.html', error="Invalid credentials")
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
         # we would move this to a service later and call it here
        existing_user = execute_query_one(
            "SELECT userid FROM users WHERE email = %s OR username = %s",
            (email, username)
        )
        
        if existing_user:
            return render_template('signup.html', error="User already exists")
        
        user_id = str(uuid.uuid4())
        hashed_pw = generate_password_hash(password)
         # we would move this to a service later and call it here
        result = execute_query(
            "INSERT INTO users (userid, username, email, passwordhash) VALUES (%s, %s, %s, %s)",
            (user_id, username, email, hashed_pw)
        )
        
        if result:
            session['user_id'] = user_id
            return redirect('/home')
        else:
            return render_template('signup.html', error="Failed to create account")
    
    return render_template('signup.html')

@app.route('/home')
def home_feed():
    if 'user_id' not in session:
        return redirect('/login')
    
    # Get some sample anime to display
    sample_anime = execute_query("""
        SELECT animeid, corerecord->>'title' as title 
        FROM animecatalog 
        LIMIT 6
    """, fetch=True) or []
    
    # Create minimal feed structure
    feed_data = {
        'personalized_recommendations': {'recommended_anime': []},
        'recent_ratings': [],
        'sample_anime': sample_anime,
        'user_preferences': {}
    }
    
    return render_template('homePage.html', feed=feed_data)



@app.route('/api/ratings', methods=['POST'])
def rate_anime():
    """CQRS + EDA: User rates anime (Command + Event)"""
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    user_id = session['user_id']
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No JSON data"}), 400
        
    anime_id = data.get('anime_id')
    score = data.get('score')
    
    if not anime_id or score is None:
        return jsonify({"error": "Missing anime_id or score"}), 400
    
    # we would move this to a service later and call it here
    # 1. COMMAND: Write 
    rating_id = str(uuid.uuid4())
    result = execute_query("""
        INSERT INTO ratingsnapshots (ratingid, userid, animeid, score)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (userid, animeid) DO UPDATE SET score = EXCLUDED.score
    """, (rating_id, user_id, anime_id, score))
    
    if not result:
        return jsonify({"error": "Database error"}), 500
    
    # we would move this to a service later and call it here
    # 2. EVENT: Publish
    publish_user_rated_anime(user_id, anime_id, score)
    
    return jsonify({
        "status": "success", 
        "message": "Rating saved + event published",
        "rating_id": rating_id
    })

@app.route('/api/recommendations')
def get_recommendations():
    """CQRS: Read recommendations (Query)"""
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    user_id = session['user_id']
    
    recommendations = execute_query_one(
        "SELECT payload FROM recommendationcache WHERE userid = %s",
        (user_id,)
    )
    
    return jsonify(recommendations or {"recommendations": []})

@app.route('/test-db')
def test_db():
    try:
        result = execute_query_one("SELECT version()")
        return jsonify({"status": "success", "version": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ===== START SERVICES =====
print("Starting AniFlow")
start_recommendation_consumer()

if __name__ == '__main__':
    print("Flask running on http://localhost:5000")
    app.run(debug=True, port=5000)