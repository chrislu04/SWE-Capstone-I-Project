# app.py
from flask import Flask, request, jsonify, session, render_template, redirect
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from datetime import datetime
import json

# SQLAlchemy setup
from models import db
app = Flask(__name__)
app.secret_key = 'aniflow_secret_key_123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres.tjrbxmwippcvwpkclxwd:animeftw@aws-1-us-east-2.pooler.supabase.com:5432/postgres'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Kafka integration
from kafka import KafkaProducer, KafkaConsumer
import threading
import tempfile
import os
from sqlalchemy.orm import sessionmaker
from models import ImportJob

def execute_query(query, params=None, fetch=False):
    """Execute raw SQL query using SQLAlchemy connection"""
    try:
        from sqlalchemy import text
        # SQLAlchemy uses named parameters like :param_name, not %s
        result = db.session.execute(text(query), params or {})
        if fetch and query.strip().upper().startswith('SELECT'):
            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]
        else:
            db.session.commit()
            return {"status": "success", "rowcount": result.rowcount}
    except Exception as e:
        print(f"Query error: {e}")
        db.session.rollback()
        return None

def execute_query_one(query, params=None):
    """Execute SQL query and return single result"""
    try:
        from sqlalchemy import text
        # SQLAlchemy uses named parameters like :param_name, not %s
        result = db.session.execute(text(query), params or {})
        if query.strip().upper().startswith('SELECT'):
            row = result.fetchone()
            return dict(row._mapping) if row else None
        else:
            db.session.commit()
            return {"status": "success", "rowcount": result.rowcount}
    except Exception as e:
        print(f"Query error: {e}")
        db.session.rollback()
        return None

#importing services 
from Services.exploreService import explore_service

# Kafka ==========
class KafkaManager:
    def __init__(self):
        self.bootstrap_servers = 'localhost:9092'
        self.producer = None
    
    def get_producer(self):
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

# routing

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
            "SELECT \"userId\", \"passwordHash\" FROM \"users\" WHERE email = :email AND \"isActive\" = TRUE",
            {"email": email}
        )
        
        if user and check_password_hash(user['passwordHash'], password):
            session['user_id'] = str(user['userId'])
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
            "SELECT \"userId\" FROM \"users\" WHERE email = :email OR username = :username",
            {"email": email, "username": username}
        )
        
        if existing_user:
            return render_template('signup.html', error="User already exists")
        
        user_id = str(uuid.uuid4())
        hashed_pw = generate_password_hash(password)
         # we would move this to a service later and call it here
        result = execute_query(
            "INSERT INTO \"users\" (\"userId\", username, email, \"passwordHash\") VALUES (:user_id, :username, :email, :hashed_pw)",
            {"user_id": user_id, "username": username, "email": email, "hashed_pw": hashed_pw}
        )
        
        if result:
            session['user_id'] = user_id
            return redirect('/onboarding')
        else:
            return render_template('signup.html', error="Failed to create account")
    
    return render_template('signup.html')

@app.route('/home')
def home_feed():
    if 'user_id' not in session:
        return redirect('/login')
    
    user_id = session['user_id']

    # we would move this to a service later and call it here
    # Get sample anime for personalized section
    sample_anime = execute_query("""
        SELECT "animeId", title 
        FROM "animeCatalog" 
        LIMIT 6
    """, fetch=True) or []
    
    #first example of calling service for query
    # Get random anime for explore section using the service
    explore_anime = explore_service.get_random_anime_sync(limit=12)
    
    # Send async Kafka event for explore (optional - for background processing)
    explore_service.send_explore_request(user_id)
    
    # Create feed structure
    feed_data = {
        'personalized_recommendations': {'recommended_anime': []},
        'recent_ratings': [],
        'sample_anime': sample_anime,
        'explore_anime': explore_anime,  # Add explore anime to feed
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
        INSERT INTO "ratingSnapshots" ("ratingId", "userId", "animeId", score)
        VALUES (:rating_id, :user_id, :anime_id, :score)
        ON CONFLICT ("userId", "animeId") DO UPDATE SET score = EXCLUDED.score
    """, {"rating_id": rating_id, "user_id": user_id, "anime_id": anime_id, "score": score})
    
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
        "SELECT payload FROM \"recommendationCache\" WHERE \"userId\" = :user_id",
        {"user_id": user_id}
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


# GET: Render upload form, POST: Handle upload
@app.route('/admin/import-anime', methods=['GET', 'POST'])
def admin_import_anime():
    if request.method == 'GET':
        return render_template('importAnime.html')
    try:
        if 'file' not in request.files:
            return render_template('importAnime.html', result={"error": "No file provided"})
        file = request.files['file']
        if file.filename == '':
            return render_template('importAnime.html', result={"error": "No file selected"})
        if not file.filename.endswith('.csv'):
            return render_template('importAnime.html', result={"error": "File must be CSV"})
        from Services.animeImportService import import_anime_csv
        from models import db
        # Dispose SQLAlchemy engine to clear pooled connections/schema cache
        try:
            db.engine.dispose()
        except Exception:
            pass

        # Save uploaded file to a temporary path so background thread can open it
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
        try:
            file.stream.seek(0)
        except Exception:
            pass
        tmp.write(file.read())
        tmp.flush()
        tmp.close()

        # Create ImportJob record with denormalized admin username
        admin_user_id = session.get('user_id') if 'user_id' in session else None
        admin_username = None
        if admin_user_id:
            admin_user = execute_query_one(
                "SELECT username FROM \"users\" WHERE \"userId\" = :user_id",
                {"user_id": admin_user_id}
            )
            admin_username = admin_user['username'] if admin_user else None
        
        job = ImportJob(adminUserId=admin_user_id,
                        adminUsername=admin_username,
                        status='pending', payload={})
        try:
            db.session.add(job)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            os.unlink(tmp.name)
            return render_template('importAnime.html', result={"error": f"Failed to create import job: {str(e)}"})

        job_id = str(job.jobId)

        # Background worker
        def _run_import(path, job_id):
            Session = sessionmaker(bind=db.engine)
            worker_session = Session()
            try:
                # update job status to running
                try:
                    jb = worker_session.query(ImportJob).get(uuid.UUID(job_id))
                    if jb:
                        jb.status = 'running'
                        jb.payload = jb.payload or {}
                        jb.payload.update({"progress": 0})
                        worker_session.add(jb)
                        worker_session.commit()
                except Exception:
                    worker_session.rollback()

                # open the temp file and create a file-like wrapper with .stream
                class _FileWrapper:
                    def __init__(self, fp):
                        self.stream = fp

                f = open(path, 'rb')
                wrapped = _FileWrapper(f)
                try:
                    # pass job_id so the import service can update progress
                    result = import_anime_csv(wrapped, worker_session, job_id=job_id)
                finally:
                    try:
                        f.close()
                    except Exception:
                        pass

                # store result into job.payload and mark complete
                try:
                    jb = worker_session.query(ImportJob).get(uuid.UUID(job_id))
                    if jb:
                        jb.payload = result
                        jb.status = 'completed' if result.get('success') else 'failed'
                        jb.completedAt = db.func.now()
                        worker_session.add(jb)
                        worker_session.commit()
                except Exception:
                    worker_session.rollback()

            except Exception as e:
                try:
                    jb = worker_session.query(ImportJob).get(uuid.UUID(job_id))
                    if jb:
                        jb.status = 'failed'
                        jb.payload = {"error": str(e)}
                        worker_session.add(jb)
                        worker_session.commit()
                except Exception:
                    worker_session.rollback()
            finally:
                try:
                    worker_session.close()
                except Exception:
                    pass
                # cleanup temporary file
                try:
                    os.unlink(path)
                except Exception:
                    pass

        t = threading.Thread(target=_run_import, args=(tmp.name, job_id), daemon=True)
        t.start()
        # If the client submitted via AJAX, return JSON immediately with the job id
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({"message": "Import started", "job_id": job_id})
        return render_template('importAnime.html', result={"message": "Import started", "job_id": job_id})
    except Exception as e:
        return render_template('importAnime.html', result={"error": str(e)})

@app.route("/onboarding", methods=["GET", "POST"])
def onboarding():
    #update the entire process below into a onBoardingService.py
    if request.method == "POST":
        # Process the form data
        age = request.form.get("age")
        region = request.form.get("region")
        bio = request.form.get("bio")
        genres = request.form.getlist("genres")
        studios = request.form.get("studios")
        themes = request.form.get("themes")

        # For now, just return the collected data
        #update to return to homepage
        
        # return jsonify({
        #     "age": age,
        #     "region": region,
        #     "bio": bio,
        #     "genres": genres,
        #     "studios": studios,
        #     "themes": themes
        # })
    return redirect('/home')

@app.route("/recommendations/beginner")
def beginner_recommendations():
    recommendations = [
        {
            "title": "Death Note",
            "description": "A high school student discovers a supernatural notebook that allows him to kill anyone by writing their name in it."
        },
        {
            "title": "Attack on Titan",
            "description": "In a world where humanity resides within enormous walled cities to protect themselves from giant man-eating humanoids known as Titans, a young man vows to exterminate the Titans after they breach his hometown's wall."
        },
        {
            "title": "Fullmetal Alchemist: Brotherhood",
            "description": "Two brothers search for the Philosopher's Stone after an attempt to revive their deceased mother goes awry and leaves them with damaged bodies."
        },
        {
            "title": "My Hero Academia",
            "description": "In a world where most people have superpowers, a young boy without any enrolls in a prestigious hero academy to learn what it really means to be a hero."
        },
        {
            "title": "Demon Slayer: Kimetsu no Yaiba",
            "description": "A young man becomes a demon slayer to find a cure for his sister, who has been turned into a demon."
        }
    ]
    return render_template("beginnerRecommendations.html", recommendations=recommendations)

@app.route('/admin/import-status/<job_id>')
def import_status(job_id):
    try:
        from models import db
        # Convert job_id string to UUID for query
        try:
            job_uuid = uuid.UUID(job_id)
        except ValueError:
            return jsonify({"error": "Invalid job ID format"}), 400
        
        jb = db.session.query(ImportJob).get(job_uuid)
        if not jb:
            return jsonify({"error": "Job not found"}), 404
        payload = jb.payload or {}
        return jsonify({"jobId": str(jb.jobId), "status": jb.status, "payload": payload})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# start
print("Starting AniFlow")
start_recommendation_consumer()
#consumer for home page explorer
explore_service.start_explore_consumer()

if __name__ == '__main__':
    print("Flask running on http://localhost:5000")
    app.run(debug=True, port=5000)