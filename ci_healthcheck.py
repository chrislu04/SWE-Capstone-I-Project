#!/usr/bin/env python
"""Quick script to validate app startup in test mode without external deps."""
import os
import sys

os.environ['FLASK_ENV'] = 'test'
os.environ['TESTING'] = 'true'
os.environ['KAFKA_ENABLED'] = 'false'

try:
    from app import app, db
    print("[✓] App imported successfully in test mode")
    
    with app.app_context():
        print("[✓] App context created")
        db.create_all()
        print("[✓] DB tables created (in-memory SQLite)")
    
    print("[✓] All startup checks passed")
    sys.exit(0)
except Exception as e:
    print(f"[✗] Startup failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
