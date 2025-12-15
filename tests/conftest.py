import pytest
import sys
import os
from uuid import uuid4
from datetime import datetime
from unittest.mock import MagicMock, patch

# Set test environment
os.environ['FLASK_ENV'] = 'test'
os.environ['TESTING'] = 'true'
os.environ['KAFKA_ENABLED'] = 'false'

# Add parent directory to path so we can import app and services
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db
from models import User, Anime, AnimeGenre, Rating


@pytest.fixture
def test_app():
    """Create and configure a test Flask app."""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['PRESERVE_CONTEXT_ON_EXCEPTION'] = False
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(test_app):
    """Test client for making requests."""
    return test_app.test_client()


@pytest.fixture
def app_context(test_app):
    """App context for direct DB operations."""
    with test_app.app_context():
        yield test_app


@pytest.fixture
def sample_user(app_context):
    """Create a sample user for tests."""
    user_id = str(uuid4())
    user = User(
        userId=user_id,
        email='test@example.com',
        username='testuser',
        passwordHash='hashed_password',
        role='user'
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def sample_anime(app_context):
    """Create sample anime for tests."""
    anime_id = str(uuid4())
    anime = Anime(
        animeId=anime_id,
        title='Test Anime',
        type='TV',
        episodes=12,
        releaseYear=2023,
        imageUrl='https://example.com/image.jpg',
        averageRating=8.0
    )
    db.session.add(anime)
    db.session.commit()
    return anime


@pytest.fixture
def session_with_user(client, sample_user):
    """Create a session for a logged-in user."""
    with client.session_transaction() as sess:
        sess['user_id'] = sample_user.userId
    return client
