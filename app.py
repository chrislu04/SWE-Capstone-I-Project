# app.py
from flask import Flask, request, jsonify, session, render_template, redirect
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from datetime import datetime, timedelta
import json
from functools import wraps
import os

# SQLAlchemy setup
from models import db, Anime, AnimeGenre
from Services.db_utils import execute_query, execute_query_one

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'aniflow_secret_key_123')

# Database configuration (use test DB if in test mode, else production)
if os.environ.get('FLASK_ENV') == 'test' or os.environ.get('TESTING') == 'true':
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL',
        'postgresql://postgres.tjrbxmwippcvwpkclxwd:animeftw@aws-1-us-east-2.pooler.supabase.com:5432/postgres'
    )

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Seed admin user once at startup (Flask 3 removed before_first_request)

# Simple cache
cache = {}

def cache_response(ttl_seconds=300):
    """Cache decorator with TTL"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            cache_key = f"browse_sections"
            now = datetime.now()
            
            if cache_key in cache:
                cached_value, timestamp = cache[cache_key]
                if (now - timestamp).total_seconds() < ttl_seconds:
                    print(f"DEBUG: Returning cached sections (age: {(now - timestamp).total_seconds()}s)")
                    return cached_value
            
            result = f(*args, **kwargs)
            cache[cache_key] = (result, now)
            return result
        return decorated_function
    return decorator

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
from Services.flaggingService import flag_anime, get_flagged_anime, update_flag_status

search_service = SearchService()
watchlist_service = WatchlistService()
recommendation_service = RecommendationService()

# Kafka ==========
class KafkaManager:
    def __init__(self):
        self.bootstrap_servers = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        self.producer = None
        self.enabled = os.environ.get('KAFKA_ENABLED', 'true').lower() == 'true'
    
    def get_producer(self):
        if not self.enabled:
            return None
        if not self.producer:
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=[self.bootstrap_servers],
                    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                    request_timeout_ms=5000
                )
            except Exception as e:
                print(f"[WARN] Kafka producer error: {e}. Continuing without Kafka.")
                self.producer = None
        return self.producer
    
    def send_event(self, topic, event_data):
        if not self.enabled:
            return False
        producer = self.get_producer()
        if producer:
            try:
                producer.send(topic, event_data)
                print(f"Sent event to {topic}: {event_data.get('event_type')}")
                return True
            except Exception as e:
                print(f"[WARN] Failed to send event: {e}")
        return False

kafka_manager = KafkaManager()
# --- Roles & Admin utilities ---
def get_user_role(user_id):
    try:
        row = execute_query_one('SELECT role FROM "users" WHERE "userId" = :user_id', {"user_id": user_id})
        return row.get('role') if row else None
    except Exception:
        return None


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        role = get_user_role(session['user_id'])
        if role != 'admin':
            # JSON/API requests get 403, pages redirect home
            if request.accept_mimetypes.best == 'application/json' or request.is_json:
                return jsonify({"error": "Forbidden", "message": "Admin only"}), 403
            return redirect('/home')
        return fn(*args, **kwargs)
    return wrapper


def seed_admin_user():
    """Ensure designated user is set as admin by email."""
    if os.environ.get('FLASK_ENV') == 'test' or app.config.get('TESTING'):
        # Skip in test mode
        return
    try:
        execute_query(
            'UPDATE "users" SET role = :role WHERE LOWER(email) = LOWER(:email) AND (role IS NULL OR role != :role)',
            {"role": "admin", "email": "cklh3r@umsystem.edu"},
            fetch=False,
        )
        print("[INFO] Seeded admin role for cklh3r@umsystem.edu")
    except Exception as e:
        print(f"[WARN] Could not seed admin user: {e}")

# Seed admin user once at startup (Flask 3 removed before_first_request)
# Skip in test mode to avoid DB connection errors
if os.environ.get('FLASK_ENV') != 'test' and os.environ.get('TESTING') != 'true':
    with app.app_context():
        try:
            seed_admin_user()
        except Exception as e:
            print(f"[WARN] Admin seeding skipped (expected in CI/test): {e}")


@app.context_processor
def inject_is_admin():
    try:
        uid = session.get('user_id')
        role = get_user_role(uid) if uid else None
        return {"is_admin": role == 'admin'}
    except Exception:
        return {"is_admin": False}


@app.route('/admin')
@admin_required
def admin_dashboard():
    # Aggregate useful stats
    total_anime = execute_query_one('SELECT COUNT(*) AS c FROM "animeCatalog"', {})
    total_users = execute_query_one('SELECT COUNT(*) AS c FROM "users"', {})
    total_ratings = execute_query_one('SELECT COUNT(*) AS c FROM "ratingSnapshots"', {})
    ratings_last7 = execute_query_one("SELECT COUNT(*) AS c FROM \"ratingSnapshots\" WHERE \"createTime\" > NOW() - INTERVAL '7 days'", {})
    watchlists_count = execute_query_one('SELECT COUNT(*) AS c FROM "watchlistDocuments"', {})
    flagged_pending = execute_query_one('SELECT COUNT(*) AS c FROM "flagged_anime" WHERE "status" = \'pending\'', {})
    flagged_total = execute_query_one('SELECT COUNT(*) AS c FROM "flagged_anime"', {})

    # Recent import jobs
    try:
        recent_imports = db.session.query(ImportJob).order_by(ImportJob.startedAt.desc()).limit(5).all()
    except Exception:
        recent_imports = []

    stats = {
        'anime_total': (total_anime or {}).get('c', 0),
        'users_total': (total_users or {}).get('c', 0),
        'ratings_total': (total_ratings or {}).get('c', 0),
        'ratings_last7': (ratings_last7 or {}).get('c', 0),
        'watchlists_total': (watchlists_count or {}).get('c', 0),
        'flagged_pending': (flagged_pending or {}).get('c', 0),
        'flagged_total': (flagged_total or {}).get('c', 0),
    }

    return render_template('admin/dashboard.html', stats=stats, recent_imports=recent_imports)


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
    
    # Fetch recent ratings for the user
    recent_ratings = execute_query("""
        SELECT rs.score, ac."animeId", ac.title, ac."imageUrl", ac."releaseYear", 
               ac.type, ac.episodes, ag.genres
        FROM "ratingSnapshots" rs
        JOIN "animeCatalog" ac ON rs."animeId" = ac."animeId"
        LEFT JOIN "animeGenres" ag ON ac."animeId" = ag."animeId"
        WHERE rs."userId" = :user_id
        ORDER BY rs."createTime" DESC
        LIMIT 10
    """, {"user_id": user_id}, fetch=True) or []
    
    #first example of calling service for query
    # Get random anime for explore section using the service
    explore_anime = explore_service.get_random_anime_sync(limit=8)
    
    # Send async Kafka event for explore (optional - for background processing)
    explore_service.send_explore_request(user_id)
    
    # Get personalized recommendations and prefill cache with a larger set (for Load More)
    personalized_all = recommendation_service.get_personalized_recommendations(user_id, limit=60)
    
    # Create feed structure
    feed_data = {
        'personalized_recommendations': {'recommended_anime': (personalized_all[:12] if personalized_all else [])},
        'recent_ratings': recent_ratings,
        'sample_anime': sample_anime,
        'explore_anime': explore_anime,  # Add explore anime to feed
        'user_preferences': {}
    }
    
    return render_template('homePage.html', feed=feed_data)


@app.route('/api/load-more-personalized')
def load_more_personalized():
    """API endpoint to load more personalized recommendations"""
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    user_id = session['user_id']
    offset = int(request.args.get('offset', 0))
    limit = int(request.args.get('limit', 12))
    
    # Get personalized recommendations with offset
    personalized_anime = recommendation_service.get_personalized_recommendations(user_id, limit=limit, offset=offset)
    
    return jsonify({"anime": personalized_anime, "count": len(personalized_anime)})


@app.route('/api/load-more-explore')
def load_more_explore():
    """API endpoint to load more explore anime"""
    limit = int(request.args.get('limit', 12))
    
    # Get random anime for explore section
    explore_anime = explore_service.get_random_anime_sync(limit=limit)
    
    return jsonify({"anime": explore_anime, "count": len(explore_anime)})


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
            
    return render_template('ShowSelectedAnime.html', anime=anime, user_rating=user_rating)

@app.route('/search', methods=['GET', 'POST'])
def advanced_search():
    if request.method == 'POST':
        title = request.form.get('title')
        genre = request.form.get('genre')
        year = request.form.get('year')
        rating = request.form.get('rating')
        
        results = search_service.advanced_search(title, genre, year, rating)
        return render_template('advancedSearch.html', results=results[:60])  # Limit to 60 per page
    
    return render_template('advancedSearch.html', results=[])

@app.route('/api/search/advanced', methods=['GET'])
def api_advanced_search():
    """API endpoint for advanced search with pagination"""
    title = request.args.get('title', '')
    genre = request.args.get('genre', '')
    year = request.args.get('year', '')
    rating = request.args.get('rating', '')
    offset = int(request.args.get('offset', 0))
    limit = int(request.args.get('limit', 60))
    
    results = search_service.advanced_search(title, genre, year, rating)
    
    # Apply pagination
    paginated_results = results[offset:offset + limit]
    
    return jsonify({
        'results': paginated_results,
        'total': len(results),
        'offset': offset,
        'limit': limit,
        'has_more': offset + limit < len(results)
    })

@app.route('/browse')
def browse_anime():
    """Browse anime by genre, highly rated, and recent releases"""
    if 'user_id' not in session:
        return redirect('/login')
    
    return render_template('browseAnime.html')

@app.route('/api/browse/sections')
@cache_response(ttl_seconds=600)  # Cache for 10 minutes
def get_browse_sections():
    """Get list of all sections with anime counts"""
    current_year = datetime.now().year
    sections = []
    
    try:
        # In SQLite/test mode, return an empty list instead of executing PG-only functions
        from models import db
        if db.engine.url.get_backend_name() == 'sqlite':
            return jsonify({"sections": sections})

        results = execute_query("""
            SELECT 
                'highly_rated' as type,
                COUNT(DISTINCT CASE WHEN a."averageRating" >= 7.5 THEN a."animeId" END) as count
            FROM "animeCatalog" a
            UNION ALL
            SELECT 
                'recent' as type,
                COUNT(DISTINCT CASE WHEN a."releaseYear" = :year THEN a."animeId" END) as count
            FROM "animeCatalog" a
        """, {"year": current_year}, fetch=True)
        
        if results:
            for row in results:
                if row['type'] == 'highly_rated' and row['count'] > 0:
                    sections.append({"id": "highly_rated", "name": "⭐ Highly Rated Anime", "count": row['count']})
                elif row['type'] == 'recent' and row['count'] > 0:
                    sections.append({"id": "recent", "name": "🆕 Anime Released This Year", "count": row['count']})
        
        genre_results = execute_query("""
            SELECT 
                TRIM(BOTH ' ' FROM g.genre) as genre,
                COUNT(DISTINCT ag."animeId") as count
            FROM "animeGenres" ag,
            LATERAL unnest(string_to_array(ag."genres", ',')) as g(genre)
            WHERE ag."genres" IS NOT NULL AND ag."genres" != ''
            GROUP BY TRIM(BOTH ' ' FROM g.genre)
            ORDER BY count DESC, genre
        """, fetch=True)
        
        if genre_results:
            for genre_row in genre_results:
                genre = genre_row.get('genre', '').strip()
                count = genre_row.get('count', 0)
                if not genre or genre.lower() == 'hentai' or count == 0:
                    continue
                sections.append({"id": f"genre_{genre}", "name": f"🎭 {genre}", "count": count})
        
        print(f"DEBUG: Loaded {len(sections)} sections")
        return jsonify({"sections": sections})
    
    except Exception as e:
        print(f"Error in get_browse_sections: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "sections": []}), 500

@app.route('/api/browse/anime/<section_id>')
def get_anime_for_section(section_id):
    """Get anime for a specific section with pagination"""
    offset = request.args.get('offset', 0, type=int)
    limit = request.args.get('limit', 12, type=int)
    current_year = datetime.now().year
    
    anime_list = []
    
    try:
        from models import db
        if db.engine.url.get_backend_name() == 'sqlite':
            return jsonify({"anime": []})

        if section_id == 'highly_rated':
            anime_list = execute_query("""
                SELECT a."animeId", a."title", a."averageRating", a."releaseYear", 
                       a."imageUrl", a."type", a."episodes", ag."genres"
                FROM "animeCatalog" a
                LEFT JOIN "animeGenres" ag ON a."animeId" = ag."animeId"
                WHERE a."averageRating" IS NOT NULL AND a."averageRating" >= 7.5
                ORDER BY a."averageRating" DESC
                LIMIT :limit OFFSET :offset
            """, {"limit": limit, "offset": offset}, fetch=True)
        
        elif section_id == 'recent':
            anime_list = execute_query("""
                SELECT a."animeId", a."title", a."averageRating", a."releaseYear", 
                       a."imageUrl", a."type", a."episodes", ag."genres"
                FROM "animeCatalog" a
                LEFT JOIN "animeGenres" ag ON a."animeId" = ag."animeId"
                WHERE a."releaseYear" = :year
                ORDER BY a."averageRating" DESC
                LIMIT :limit OFFSET :offset
            """, {"year": current_year, "limit": limit, "offset": offset}, fetch=True)
        
        elif section_id.startswith('genre_'):
            genre = section_id.replace('genre_', '')
            anime_list = execute_query("""
                SELECT DISTINCT a."animeId", a."title", a."averageRating", a."releaseYear", 
                       a."imageUrl", a."type", a."episodes", ag."genres"
                FROM "animeCatalog" a
                INNER JOIN "animeGenres" ag ON a."animeId" = ag."animeId"
                WHERE POSITION(:genre IN ag."genres") > 0
                ORDER BY a."averageRating" DESC
                LIMIT :limit OFFSET :offset
            """, {"genre": genre, "limit": limit, "offset": offset}, fetch=True)
        
        return jsonify({"anime": anime_list or []})
    
    except Exception as e:
        print(f"Error in get_anime_for_section: {e}")
        return jsonify({"error": str(e), "anime": []}), 500

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

    # Ensure the anime exists
    anime_exists = execute_query_one(
        'SELECT 1 FROM "animeCatalog" WHERE "animeId" = :anime_id',
        {"anime_id": anime_id}
    )
    if not anime_exists:
        return jsonify({"error": "Anime not found"}), 404
    
    try:
        score_val = int(score)
    except Exception:
        return jsonify({"error": "Score must be an integer"}), 400
    if score_val < 1 or score_val > 10:
        return jsonify({"error": "Score must be between 1 and 10"}), 400
    
    rating_id = str(uuid.uuid4())
    result = execute_query("""
        INSERT INTO "ratingSnapshots" ("ratingId", "userId", "animeId", score, "createTime")
        VALUES (:rating_id, :user_id, :anime_id, :score, NOW())
        ON CONFLICT ("userId", "animeId") DO UPDATE SET score = EXCLUDED.score, "createTime" = NOW()
    """, {"rating_id": rating_id, "user_id": user_id, "anime_id": anime_id, "score": score_val})
    
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

@app.route('/api/recommendations/refresh', methods=['POST'])
def refresh_recommendations():
    """Clear cache and recompute personalized recommendations"""
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    user_id = session['user_id']
    
    try:
        # Delete cached recommendations
        execute_query(
            'DELETE FROM "recommendationCache" WHERE "userId" = :user_id',
            {"user_id": user_id}
        )
        
        # Force recompute by calling the service with limit=60 to prefill cache
        personalized_anime = recommendation_service.get_personalized_recommendations(user_id, limit=60)
        
        return jsonify({
            "status": "success",
            "message": "Recommendations refreshed",
            "count": len(personalized_anime) if personalized_anime else 0
        })
    except Exception as e:
        print(f"Error refreshing recommendations: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/anime/<anime_id>/flag', methods=['POST'])
def flag_anime_route(anime_id):
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    # Validate anime id
    if not anime_id or str(anime_id).lower() == 'null':
        return jsonify({"error": "Invalid anime id"}), 400

    anime_exists = execute_query_one(
        'SELECT 1 FROM "animeCatalog" WHERE "animeId" = :anime_id',
        {"anime_id": anime_id}
    )
    if not anime_exists:
        return jsonify({"error": "Anime not found"}), 404

    user_id = session['user_id']
    data = request.get_json()
    reason = data.get('reason')
    
    if not reason:
        return jsonify({"error": "Reason is required"}), 400
    
    if flag_anime(anime_id, user_id, reason):
        return jsonify({"status": "success", "message": "Anime flagged successfully"})
    
    return jsonify({"error": "Failed to flag anime"}), 500


@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    
    # Fetch user data
    user = execute_query_one('SELECT * FROM "users" WHERE "userId" = :user_id', {"user_id": user_id})
    
    # Fetch rated anime details
    print(f"[DEBUG] Fetching rated anime for user_id: {user_id}")
    rated_anime_details = execute_query(
        """
        SELECT rs.score, ac."animeId", ac.title, ac."imageUrl"
        FROM "ratingSnapshots" rs
        JOIN "animeCatalog" ac ON rs."animeId" = ac."animeId"
        WHERE rs."userId" = :user_id
        ORDER BY rs."createTime" DESC
        """,
        {"user_id": user_id},
        fetch=True
    )
    print(f"[DEBUG] Query returned: {rated_anime_details}")
    print(f"[DEBUG] Found {len(rated_anime_details) if rated_anime_details else 0} rated anime")
    if rated_anime_details and len(rated_anime_details) > 0:
        print(f"[DEBUG] First rating keys: {rated_anime_details[0].keys() if rated_anime_details else 'None'}")
        print(f"[DEBUG] First rating data: {rated_anime_details[0] if rated_anime_details else 'None'}")
    
    # Fetch user's watchlists and their anime details
    user_watchlists = watchlist_service.get_watchlists_for_user(user_id)
    user_watchlists_with_anime = []

    for wl in user_watchlists:
        anime_ids_in_watchlist = [item['animeId'] for item in wl.items if 'animeId' in item]
        if anime_ids_in_watchlist:
            # Fetch details for all anime in the current watchlist
            # Using IN clause with a list of UUIDs
            # Convert UUIDs to strings for the query
            anime_ids_str = [str(uuid.UUID(aid)) for aid in anime_ids_in_watchlist]
            
            # Constructing a dynamic IN clause
            # Create placeholders like :anime_id_0, :anime_id_1, etc.
            # and map them to the actual UUID strings in the params dictionary
            param_names = {f"anime_id_{i}": aid for i, aid in enumerate(anime_ids_str)}
            in_clause = ", ".join([f":anime_id_{i}" for i in range(len(anime_ids_str))])
            
            watchlist_anime_details = execute_query(
                f"""
                SELECT "animeId", title, "imageUrl"
                FROM "animeCatalog"
                WHERE "animeId" IN ({in_clause})
                """,
                param_names,
                fetch=True
            )
            # Ensure the order of anime in the watchlist is preserved if needed,
            # but for now, just adding them as a list
            user_watchlists_with_anime.append({
                "watchlistId": str(wl.watchlistId),
                "name": wl.name,
                "anime": watchlist_anime_details
            })
        else:
            user_watchlists_with_anime.append({
                "watchlistId": str(wl.watchlistId),
                "name": wl.name,
                "anime": []
            })
            
    # Fetch user stats
    anime_rated_count = len(rated_anime_details) if rated_anime_details else 0
    avg_rating_result = execute_query_one('SELECT AVG(score) as avg FROM "ratingSnapshots" WHERE "userId" = :user_id', {"user_id": user_id})
    avg_rating = round(avg_rating_result['avg'], 1) if avg_rating_result and avg_rating_result['avg'] else 0.0
    reviews_written_count = execute_query_one('SELECT COUNT(*) as count FROM "userNotes" WHERE "userId" = :user_id', {"user_id": user_id})
    
    total_watchlist_anime_count = sum(len(wl['anime']) for wl in user_watchlists_with_anime)

    user_stats = {
        "anime_rated": anime_rated_count,
        "avg_rating": avg_rating,
        "watchlist_count": total_watchlist_anime_count,
        "reviews_written": reviews_written_count['count'] if reviews_written_count else 0
    }
    
    # Fetch user preferences (demographic info and preferred genres)
    user_prefs = execute_query_one('SELECT * FROM "profilePreferences" WHERE "userId" = :user_id', {"user_id": user_id})
    user_demographic = {}
    user_preferred_genres = []
    user_preferred_studios = []
    user_preferred_themes = []
    
    if user_prefs:
        if user_prefs.get('demographic'):
            user_demographic = user_prefs['demographic'] if isinstance(user_prefs['demographic'], dict) else {}
        if user_prefs.get('preferredGenres'):
            user_preferred_genres = user_prefs['preferredGenres'] if isinstance(user_prefs['preferredGenres'], list) else []
        if user_prefs.get('preferredStudios'):
            user_preferred_studios = user_prefs['preferredStudios'] if isinstance(user_prefs['preferredStudios'], list) else []
        if user_prefs.get('preferredThemes'):
            user_preferred_themes = user_prefs['preferredThemes'] if isinstance(user_prefs['preferredThemes'], list) else []

    return render_template(
        'userPage.html', 
        user=user, 
        stats=user_stats,
        rated_anime=rated_anime_details,
        user_watchlists=user_watchlists_with_anime,
        user_demographic=user_demographic,
        user_preferred_genres=user_preferred_genres,
        user_preferred_studios=user_preferred_studios,
        user_preferred_themes=user_preferred_themes
    )

@app.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect('/login')
    
    user_id = session['user_id']
    user = execute_query_one('SELECT * FROM "users" WHERE "userId" = :user_id', {"user_id": user_id})
    
    if request.method == 'POST':
        new_username = request.form.get('username', '').strip()
        new_email = request.form.get('email', '').strip()
        
        if not new_username or not new_email:
            return render_template('editProfile.html', user=user, error='Username and email are required')
        
        try:
            execute_query("""
                UPDATE "users" 
                SET username = :username, email = :email 
                WHERE "userId" = :user_id
            """, {"username": new_username, "email": new_email, "user_id": user_id})
            return redirect('/profile')
        except Exception as e:
            return render_template('editProfile.html', user=user, error=str(e))
    
    return render_template('editProfile.html', user=user)

@app.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        return redirect('/login')
    
    user_id = session['user_id']
    
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not new_password or not confirm_password:
            return render_template('changePassword.html', error='New password and confirmation are required')
        
        if new_password != confirm_password:
            return render_template('changePassword.html', error='Passwords do not match')
        
        user = execute_query_one('SELECT * FROM "users" WHERE "userId" = :user_id', {"user_id": user_id})
        if not user or not check_password_hash(user['passwordHash'], current_password):
            return render_template('changePassword.html', error='Current password is incorrect')
        
        try:
            new_hash = generate_password_hash(new_password)
            execute_query("""
                UPDATE "users" 
                SET "passwordHash" = :password_hash 
                WHERE "userId" = :user_id
            """, {"password_hash": new_hash, "user_id": user_id})
            return redirect('/profile')
        except Exception as e:
            return render_template('changePassword.html', error=str(e))
    
    return render_template('changePassword.html')

@app.route('/edit-demographic', methods=['GET', 'POST'])
def edit_demographic():
    if 'user_id' not in session:
        return redirect('/login')
    
    user_id = session['user_id']
    pref = execute_query_one('SELECT * FROM "profilePreferences" WHERE "userId" = :user_id', {"user_id": user_id})
    demographic = pref.get('demographic', {}) if pref else {}
    
    if request.method == 'POST':
        demographic = {
            'age': request.form.get('age', ''),
            'region': request.form.get('region', ''),
            'bio': request.form.get('bio', '')
        }
        
        try:
            if pref:
                execute_query("""
                    UPDATE "profilePreferences" 
                    SET demographic = :demographic 
                    WHERE "userId" = :user_id
                """, {"demographic": json.dumps(demographic), "user_id": user_id})
            else:
                execute_query("""
                    INSERT INTO "profilePreferences" ("userId", demographic)
                    VALUES (:user_id, :demographic)
                """, {"user_id": user_id, "demographic": json.dumps(demographic)})
            return redirect('/profile')
        except Exception as e:
            return render_template('editDemographic.html', demographic=demographic, error=str(e))
    
    return render_template('editDemographic.html', demographic=demographic)

@app.route('/edit-preferences', methods=['GET', 'POST'])
def edit_preferences():
    if 'user_id' not in session:
        return redirect('/login')
    
    user_id = session['user_id']
    
    # Fetch all available genres with their popularity count
    all_genres_result = execute_query(
        'SELECT DISTINCT genres FROM "animeGenres" WHERE genres IS NOT NULL',
        {},
        fetch=True
    )
    
    genre_counts = {}
    if all_genres_result:
        for row in all_genres_result:
            genre_str = row.get('genres', '')
            if genre_str:
                # Split by comma and clean up
                genres_list = [g.strip() for g in genre_str.split(',') if g.strip()]
                for genre in genres_list:
                    genre_counts[genre] = genre_counts.get(genre, 0) + 1
    
    # Sort genres by popularity (count), then alphabetically
    all_genres = sorted(genre_counts.keys(), key=lambda x: (-genre_counts[x], x))
    
    pref = execute_query_one('SELECT * FROM "profilePreferences" WHERE "userId" = :user_id', {"user_id": user_id})
    preferred_genres = pref.get('preferredGenres', []) if pref else []
    
    if request.method == 'POST':
        # Get selected genres from checkboxes
        selected_genres = request.form.getlist('genres')
        
        try:
            if pref:
                execute_query("""
                    UPDATE "profilePreferences" 
                    SET "preferredGenres" = :genres 
                    WHERE "userId" = :user_id
                """, {"genres": json.dumps(selected_genres), "user_id": user_id})
            else:
                execute_query("""
                    INSERT INTO "profilePreferences" ("userId", "preferredGenres")
                    VALUES (:user_id, :genres)
                """, {"user_id": user_id, "genres": json.dumps(selected_genres)})
            return redirect('/profile')
        except Exception as e:
            return render_template('editPreferences.html', preferred_genres=preferred_genres, all_genres=all_genres, genre_counts=genre_counts, error=str(e))
    
    return render_template('editPreferences.html', preferred_genres=preferred_genres, all_genres=all_genres, genre_counts=genre_counts)

@app.route('/anime/<anime_id>/recommendations')
def get_similar_anime(anime_id):
    """Get recommendations for a specific anime."""
    try:
        recommendations = recommendation_service.get_recommendations(anime_id)
        
        # Check if it's an API request (JSON) or a page request (HTML)
        if request.accept_mimetypes.best == 'application/json' or 'application/json' in request.headers.get('Accept', ''):
            return jsonify({"recommendations": recommendations or []})
        else:
            # Return the rendered HTML page with the anime ID as a query parameter
            return render_template('relatedAnime.html')
    except Exception as e:
        print(f"Error getting recommendations: {e}")
        if request.accept_mimetypes.best == 'application/json' or 'application/json' in request.headers.get('Accept', ''):
            return jsonify({"recommendations": [], "error": str(e)}), 500
        else:
            return render_template('relatedAnime.html')

@app.route('/api/anime/<anime_id>/recommendations', methods=['GET'])
def api_get_recommendations(anime_id):
    """API endpoint for getting anime recommendations"""
    try:
        print(f"[DEBUG] api_get_recommendations route called with anime_id: {anime_id} (type: {type(anime_id)})")
        recommendations = recommendation_service.get_recommendations(anime_id)
        print(f"[DEBUG] get_recommendations returned {len(recommendations) if recommendations else 0} results")
        return jsonify({"recommendations": recommendations or []})
    except Exception as e:
        print(f"Error getting recommendations: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"recommendations": [], "error": str(e)}), 500
    
@app.route('/admin/flagged-anime')
@admin_required
def admin_flagged_anime():
    flagged_anime = get_flagged_anime()
    return render_template('admin/flagged.html', flagged_anime=flagged_anime)

@app.route('/admin/flagged-anime/<flag_id>/update', methods=['POST'])
@admin_required
def admin_update_flagged_anime(flag_id):
    data = request.get_json()
    status = data.get('status')
    
    if status not in ['resolved', 'dismissed']:
        return jsonify({"error": "Invalid status"}), 400
    
    if update_flag_status(flag_id, status):
        return jsonify({"status": "success", "message": "Flag status updated"})
    
    return jsonify({"error": "Failed to update flag status"}), 500

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
@admin_required
def admin_import_anime():
    if request.method == 'GET':
        return render_template('importAnime.html')
    try:
        if 'file' not in request.files:
            return render_template('importAnime.html', result={"error": "No file provided"}), 400
        file = request.files['file']
        if file.filename == '':
            return render_template('importAnime.html', result={"error": "No file selected"}), 400
        if not file.filename.endswith('.csv'):
            return render_template('importAnime.html', result={"error": "File must be CSV"}), 400
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
@admin_required
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
    
    # Enrich watchlist items with anime details
    for watchlist in watchlists:
        if isinstance(watchlist.items, list):
            enriched_items = []
            for item in watchlist.items:
                anime_id = item.get('animeId')
                if anime_id:
                    anime = db.session.get(Anime, anime_id)
                    if anime:
                        # Get genres from AnimeGenre table
                        anime_genre = AnimeGenre.query.filter_by(animeId=anime_id).first()
                        genres = anime_genre.genres if anime_genre else ''
                        
                        enriched_items.append({
                            'animeId': str(anime.animeId),
                            'title': anime.title,
                            'imageUrl': anime.imageUrl,
                            'averageRating': anime.averageRating,
                            'releaseYear': anime.releaseYear,
                            'type': anime.type,
                            'episodes': anime.episodes,
                            'genres': genres
                        })
            watchlist.items = enriched_items
    
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

@app.route('/api/watchlists', methods=['GET'])
def api_get_watchlists():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    user_id = session['user_id']
    watchlists = watchlist_service.get_watchlists_for_user(user_id)
    
    return jsonify([{
        "watchlistId": str(w.watchlistId),
        "name": w.name
    } for w in watchlists])

@app.route('/api/anime/<anime_id>', methods=['GET'])
def get_anime_details(anime_id):
    """Get detailed anime information by ID"""
    try:
        anime = execute_query_one("""
            SELECT a."animeId", a.title, a."averageRating", a."releaseYear", 
                   a."imageUrl", a.type, a.episodes, ag.genres
            FROM "animeCatalog" a
            LEFT JOIN "animeGenres" ag ON a."animeId" = ag."animeId"
            WHERE a."animeId" = :anime_id
        """, {"anime_id": anime_id})
        
        if not anime:
            return jsonify({"error": "Anime not found"}), 404
        
        return jsonify(anime)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/anime/search', methods=['GET'])
def search_anime():
    """Search anime by title for autocomplete"""
    query = request.args.get('q', '').strip()
    
    if not query or len(query) < 2:
        return jsonify([])
    
    try:
        results = execute_query("""
            SELECT a."animeId", a.title, a."releaseYear"
            FROM "animeCatalog" a
            WHERE LOWER(a.title) LIKE LOWER(:query)
            ORDER BY a."averageRating" DESC NULLS LAST
            LIMIT 10
        """, {"query": f"%{query}%"}, fetch=True)
        
        return jsonify(results or [])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# start
print("Starting AniFlow")
# Start Kafka consumers only when enabled
if os.environ.get('KAFKA_ENABLED', 'true').lower() == 'true':
    start_recommendation_consumer()
    # consumer for home page explorer
    explore_service.start_explore_consumer()

if __name__ == '__main__':
    print("Flask running on http://localhost:5000")
    app.run(debug=True, port=5000)