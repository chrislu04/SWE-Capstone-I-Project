"""Unit tests for data models and schema validation."""
import pytest
from uuid import uuid4
from datetime import datetime
from models import User, Anime, AnimeGenre, RatingSnapshot, FlaggedAnime


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
            synopsis='Test synopsis',
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


class TestRatingSnapshot:
    """Tests for RatingSnapshot model."""
    
    def test_rating_creation(self, app_context, sample_user, sample_anime):
        """Test creating a rating."""
        from models import db
        
        rating = RatingSnapshot(
            userId=sample_user.userId,
            animeId=sample_anime.animeId,
            score=7,
            createTime=datetime.now()
        )
        db.session.add(rating)
        db.session.commit()
        
        retrieved = RatingSnapshot.query.filter_by(
            userId=sample_user.userId,
            animeId=sample_anime.animeId
        ).first()
        assert retrieved is not None
        assert retrieved.score == 7
    
    def test_rating_upsert(self, app_context, sample_user, sample_anime):
        """Test updating an existing rating."""
        from models import db
        
        # Create initial rating
        rating1 = RatingSnapshot(
            userId=sample_user.userId,
            animeId=sample_anime.animeId,
            score=5,
            createTime=datetime.now()
        )
        db.session.add(rating1)
        db.session.commit()
        
        # Update it
        rating2 = RatingSnapshot(
            userId=sample_user.userId,
            animeId=sample_anime.animeId,
            score=8,
            createTime=datetime.now()
        )
        db.session.merge(rating2)
        db.session.commit()
        
        # Verify updated
        retrieved = RatingSnapshot.query.filter_by(
            userId=sample_user.userId,
            animeId=sample_anime.animeId
        ).first()
        assert retrieved.score == 8


class TestFlaggedAnimeModel:
    """Tests for FlaggedAnime model."""
    
    def test_flag_creation(self, app_context, sample_user, sample_anime):
        """Test creating a flagged anime record."""
        from models import db, FlaggedAnime
        
        flag = FlaggedAnime(
            flagId=str(uuid4()),
            animeId=sample_anime.animeId,
            userId=sample_user.userId,
            reason='Title is incorrect',
            status='pending',
            createdTime=datetime.now()
        )
        db.session.add(flag)
        db.session.commit()
        
        retrieved = FlaggedAnime.query.filter_by(status='pending').first()
        assert retrieved is not None
        assert retrieved.reason == 'Title is incorrect'
    
    def test_flag_status_update(self, app_context, sample_user, sample_anime):
        """Test updating flag status."""
        from models import db, FlaggedAnime
        
        flag_id = str(uuid4())
        flag = FlaggedAnime(
            flagId=flag_id,
            animeId=sample_anime.animeId,
            userId=sample_user.userId,
            reason='Bad data',
            status='pending',
            createdTime=datetime.now()
        )
        db.session.add(flag)
        db.session.commit()
        
        # Update status
        retrieved = FlaggedAnime.query.filter_by(flagId=flag_id).first()
        retrieved.status = 'resolved'
        db.session.commit()
        
        # Verify
        final = FlaggedAnime.query.filter_by(flagId=flag_id).first()
        assert final.status == 'resolved'
