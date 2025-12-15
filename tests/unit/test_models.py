"""Unit tests for data models and schema validation."""
import pytest
from uuid import uuid4
from datetime import datetime
from models import User, Anime, AnimeGenre, Rating


class TestUserModel:
    """Tests for User model."""
    
    def test_user_creation(self, app_context):
        """Test creating a User instance."""
        from models import db
        
        user_id = str(uuid4())
        user = User(
            userId=user_id,
            email='test@example.com',
            username='testuser',
            passwordHash='hashedpwd',
            role='user'
        )
        db.session.add(user)
        db.session.commit()
        
        retrieved = User.query.filter_by(userId=user_id).first()
        assert retrieved is not None
        assert retrieved.email == 'test@example.com'
        assert retrieved.username == 'testuser'


class TestAnimeModel:
    """Tests for Anime model."""
    
    def test_anime_creation(self, app_context):
        """Test creating an Anime instance."""
        from models import db
        
        anime_id = str(uuid4())
        anime = Anime(
            animeId=anime_id,
            title='Test Anime',
            type='TV',
            episodes=12,
            releaseYear=2023,
            imageUrl='https://example.com/img.jpg',
            averageRating=8.5
        )
        db.session.add(anime)
        db.session.commit()
        
        retrieved = Anime.query.filter_by(animeId=anime_id).first()
        assert retrieved is not None
        assert retrieved.title == 'Test Anime'
        assert retrieved.episodes == 12


class TestRatingModel:
    """Tests for Rating model."""
    
    def test_rating_creation(self, app_context, sample_user, sample_anime):
        """Test creating a rating."""
        from models import db
        
        rating = Rating(
            userId=sample_user.userId,
            animeId=sample_anime.animeId,
            score=7,
            createTime=datetime.now()
        )
        db.session.add(rating)
        db.session.commit()
        
        retrieved = Rating.query.filter_by(
            userId=sample_user.userId,
            animeId=sample_anime.animeId
        ).first()
        assert retrieved is not None
        assert retrieved.score == 7
    
    def test_rating_upsert(self, app_context, sample_user, sample_anime):
        """Test updating an existing rating."""
        from models import db
        
        # Create initial rating
        rating1 = Rating(
            userId=sample_user.userId,
            animeId=sample_anime.animeId,
            score=5,
            createTime=datetime.now()
        )
        db.session.add(rating1)
        db.session.commit()
        
        # Update existing row instead of inserting a duplicate (respects unique constraint)
        existing = Rating.query.filter_by(
            userId=sample_user.userId,
            animeId=sample_anime.animeId
        ).first()
        existing.score = 8
        db.session.commit()
        
        # Verify updated
        retrieved = Rating.query.filter_by(
            userId=sample_user.userId,
            animeId=sample_anime.animeId
        ).first()
        assert retrieved.score == 8

