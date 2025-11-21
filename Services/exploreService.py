# services/exploreService.py
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from kafka import KafkaProducer, KafkaConsumer
import threading

# Database connection (you can import from app.py later)
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
                return {"status": "success"}
    except Exception as e:
        print(f"Query error: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

class ExploreService:
    def __init__(self):
        self.bootstrap_servers = 'localhost:9092'
        self.producer = None
        self.consumer = None
    
    def get_producer(self):
        if not self.producer:
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=[self.bootstrap_servers],
                    value_serializer=lambda v: json.dumps(v).encode('utf-8')
                )
            except Exception as e:
                print(f"ExploreService Kafka producer error: {e}")
                self.producer = None
        return self.producer
    
    def send_explore_request(self, user_id, limit=12):
        """Send Kafka event to request explore anime"""
        event = {
            "event_type": "explore_anime_request",
            "user_id": str(user_id),
            "limit": limit,
            "timestamp": "2025-01-19T00:00:00Z"  # You'll need to import datetime
        }
        
        producer = self.get_producer()
        if producer:
            try:
                producer.send('explore-requests', event)
                print(f"Explore request sent for user {user_id}")
                return True
            except Exception as e:
                print(f"Failed to send explore request: {e}")
        return False
    
    def get_random_anime_sync(self, limit=12):
        """Get random anime directly (synchronous fallback)"""
        try:
            anime = execute_query("""
                SELECT 
                    animeid, 
                    corerecord->>'title' as title,
                    corerecord->>'synopsis' as synopsis,
                    corerecord->>'release_year' as release_year,
                    corerecord->>'episodes' as episodes,
                    popularity->>'score' as popularity_score,
                    aboutme->>'genres' as genres
                FROM animecatalog 
                ORDER BY RANDOM()
                LIMIT %s
            """, (limit,), fetch=True)
            
            return anime or []
        except Exception as e:
            print(f"Error getting random anime: {e}")
            return []
    
    def start_explore_consumer(self):
        """Start Kafka consumer to process explore requests"""
        def consume_explore_requests():
            try:
                consumer = KafkaConsumer(
                    'explore-requests',
                    bootstrap_servers=['localhost:9092'],
                    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                    group_id='explore-service'
                )
                
                print("Explore service consumer started...")
                
                for message in consumer:
                    event = message.value
                    print(f"Processing explore request for user {event['user_id']}")
                    
                    # Process the explore request
                    anime_data = self.get_random_anime_sync(event.get('limit', 12))
                    
                    # You could store this in cache or send back via another Kafka topic
                    print(f"Found {len(anime_data)} random anime for explore section")
                    
            except Exception as e:
                print(f"Explore consumer error: {e}")
        
        thread = threading.Thread(target=consume_explore_requests, daemon=True)
        thread.start()

# Global instance
explore_service = ExploreService()