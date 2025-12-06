# app.py
from flask import Flask, request, jsonify, session, render_template, redirect
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from datetime import datetime
import json

# SQLAlchemy setup
from models import db
from Services.db_utils import execute_query, execute_query_one
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


#importing services 
from Services.exploreService import explore_service
from Services.searchService import SearchService
from Services.recommendationService import RecommendationService
from Services.watchlistService import WatchlistService

search_service = SearchService()
watchlist_service = WatchlistService()
recommendation_service = RecommendationService()

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
        SELECT ac."animeId", ac.title 
        FROM "animeCatalog" ac
        WHERE NOT EXISTS (
            SELECT 1 FROM "animeGenres" ag, unnest(string_to_array(ag.genres, ',')) AS g
            WHERE ag."animeId" = ac."animeId" AND LOWER(trim(g)) = 'hentai'
        )
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




@app.route('/anime/<anime_id>')
def show_anime(anime_id):
    anime = execute_query_one(
        'SELECT * FROM "animeCatalog" WHERE "animeId" = :anime_id',
        {"anime_id": anime_id}
    )
    
    user_rating = None
    if 'user_id' in session:
        user_id = session['user_id']
        rating_result = execute_query_one(
            'SELECT score FROM "ratingSnapshots" WHERE "animeId" = :anime_id AND "userId" = :user_id',
            {"anime_id": anime_id, "user_id": user_id}
        )
        if rating_result:
            user_rating = rating_result['score']
            
    return render_template('showSelectedAnime.html', anime=anime, user_rating=user_rating)

@app.route('/search', methods=['GET', 'POST'])
def advanced_search():
    if request.method == 'POST':
        title = request.form.get('title')
        genre = request.form.get('genre')
        year = request.form.get('year')
        rating = request.form.get('rating')
        
        results = search_service.advanced_search(title, genre, year, rating)
        return render_template('advancedSearch.html', results=results)
    
    return render_template('advancedSearch.html', results=[])

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

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    
    # Fetch user data (replace with a proper service call)
    user = execute_query_one('SELECT * FROM "users" WHERE "userId" = :user_id', {"user_id": user_id})
    
    # Fetch user stats (replace with a proper service call)
    anime_rated_count = execute_query_one('SELECT COUNT(*) as count FROM "ratingSnapshots" WHERE "userId" = :user_id', {"user_id": user_id})
    avg_rating = execute_query_one('SELECT AVG(score) as avg FROM "ratingSnapshots" WHERE "userId" = :user_id', {"user_id": user_id})
    reviews_written_count = execute_query_one('SELECT COUNT(*) as count FROM "userNotes" WHERE "userId" = :user_id', {"user_id": user_id})
    
    # Fetch watchlists and calculate total items
    watchlists = watchlist_service.get_watchlists_for_user(user_id)
    watchlist_count = sum(len(w.items) for w in watchlists)

    user_stats = {
        "anime_rated": anime_rated_count['count'] if anime_rated_count else 0,
        "avg_rating": round(avg_rating['avg'], 1) if avg_rating and avg_rating['avg'] else 0.0,
        "watchlist_count": watchlist_count,
        "reviews_written": reviews_written_count['count'] if reviews_written_count else 0
    }

    return render_template('userPage.html', user=user, stats=user_stats)

@app.route('/anime/<anime_id>/recommendations')
def get_similar_anime(anime_id):
    """Get recommendations for a specific anime."""
    recommendations = recommendation_service.get_recommendations(anime_id)
    return jsonify(recommendations)
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
            # Ensure Flask app context for SQLAlchemy engine access
            with app.app_context():
                Session = sessionmaker(bind=db.engine)
                worker_session = Session()
                try:
                    # update job status to running
                    try:
                        jb = worker_session.get(ImportJob, uuid.UUID(job_id))
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
                        jb = worker_session.get(ImportJob, uuid.UUID(job_id))
                        if jb:
                            current_payload = jb.payload or {}
                            # Merge to keep progress stats while adding final result
                            merged = {**current_payload, **(result or {})}
                            jb.payload = merged
                            jb.status = 'completed' if result.get('success') else 'failed'
                            jb.completedAt = db.func.now()
                            worker_session.add(jb)
                            worker_session.commit()
                    except Exception:
                        worker_session.rollback()

                except Exception as e:
                    try:
                        jb = worker_session.get(ImportJob, uuid.UUID(job_id))
                        if jb:
                            current_payload = jb.payload or {}
                            current_payload.update({"error": str(e)})
                            jb.status = 'failed'
                            jb.payload = current_payload
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
    if 'user_id' not in session:
        return redirect('/login')
    
    if request.method == "POST":
        # Process the form data
        user_id = session['user_id']
        age = request.form.get("age")
        region = request.form.get("region")
        bio = request.form.get("bio")
        genres = request.form.getlist("genres")
        studios = request.form.get("studios")
        themes = request.form.get("themes")

        # Store preferences in profilePreferences table
        try:
            pref_data = {
                "age": int(age) if age else None,
                "region": region,
                "bio": bio
            }
            
            prefs_studios = [s.strip() for s in studios.split(',') if s.strip()] if studios else []
            prefs_themes = [t.strip() for t in themes.split(',') if t.strip()] if themes else []
            
            result = execute_query("""
                INSERT INTO "profilePreferences" ("userId", "demographic", "preferredGenres", "preferredStudios", "preferredThemes")
                VALUES (:user_id, :demographic, :genres, :studios, :themes)
                ON CONFLICT ("userId") DO UPDATE SET 
                    "demographic" = :demographic,
                    "preferredGenres" = :genres,
                    "preferredStudios" = :studios,
                    "preferredThemes" = :themes
            """, {
                "user_id": user_id,
                "demographic": json.dumps(pref_data),
                "genres": json.dumps(genres),
                "studios": json.dumps(prefs_studios),
                "themes": json.dumps(prefs_themes)
            })
        except Exception as e:
            print(f"Error saving preferences: {e}")
        
        return redirect('/home')
    
    return render_template('onboarding.html')

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
        
        # Expire session to force fresh DB query
        db.session.expire_all()
        jb = db.session.get(ImportJob, job_uuid)
        if not jb:
            return jsonify({"error": "Job not found"}), 404
        
        # Refresh object from database to get latest payload
        db.session.refresh(jb)
        
        payload = jb.payload or {}
        progress = payload.get("progress") if isinstance(payload, dict) else None
        total = payload.get("total") if isinstance(payload, dict) else None
        percent = payload.get("percent") if isinstance(payload, dict) else None
        if progress is not None and total:
            percent = percent if percent is not None else round((progress / total) * 100, 2)
        
        return jsonify({
            "jobId": str(jb.jobId),
            "status": jb.status,
            "payload": payload,
            "percent": percent,
            "progress": progress,
            "total": total
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/watchlists', methods=['GET'])
def get_watchlists():
    if 'user_id' not in session:
        return redirect('/login')
    
    user_id = session['user_id']
    watchlists = watchlist_service.get_watchlists_for_user(user_id)
    
    return render_template('watchlists.html', watchlists=watchlists)

@app.route('/watchlists', methods=['POST'])
def create_watchlist():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    user_id = session['user_id']
    data = request.get_json()
    name = data.get('name')
    
    if not name:
        return jsonify({"error": "Missing name"}), 400
    
    new_watchlist = watchlist_service.create_watchlist(user_id, name)
    
    return jsonify({
        "status": "success",
        "message": "Watchlist created",
        "watchlist_id": str(new_watchlist.watchlistId)
    })

@app.route('/watchlists/<watchlist_id>', methods=['DELETE'])
def delete_watchlist(watchlist_id):
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    if watchlist_service.delete_watchlist(watchlist_id):
        return jsonify({"status": "success", "message": "Watchlist deleted"})
    
    return jsonify({"error": "Watchlist not found"}), 404

@app.route('/watchlists/<watchlist_id>/animes', methods=['POST'])
def add_anime_to_watchlist(watchlist_id):
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    anime_id = data.get('anime_id')
    
    if not anime_id:
        return jsonify({"error": "Missing anime_id"}), 400
    
    if watchlist_service.add_anime_to_watchlist(watchlist_id, anime_id):
        return jsonify({"status": "success", "message": "Anime added to watchlist"})
    
    return jsonify({"error": "Watchlist or anime not found"}), 404

@app.route('/watchlists/<watchlist_id>/animes/<anime_id>', methods=['DELETE'])
def remove_anime_from_watchlist(watchlist_id, anime_id):
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    if watchlist_service.remove_anime_from_watchlist(watchlist_id, anime_id):
        return jsonify({"status": "success", "message": "Anime removed from watchlist"})
    
    return jsonify({"error": "Watchlist or anime not found"}), 404


# start
print("Starting AniFlow")
start_recommendation_consumer()
#consumer for home page explorer
explore_service.start_explore_consumer()

if __name__ == '__main__':
    print("Flask running on http://localhost:5000")
    app.run(debug=True, port=5000)