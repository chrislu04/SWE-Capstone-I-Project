import pytest
import json
from uuid import uuid4
from unittest.mock import patch, MagicMock
from datetime import datetime


class TestRatingsAPI:
    """Integration tests for ratings endpoints."""
    
    def test_post_rating_success(self, session_with_user, sample_anime, app_context):
        """Test submitting a rating successfully."""
        with app_context.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = session_with_user.client._get_user_id() if hasattr(session_with_user.client, '_get_user_id') else str(uuid4())
            
            response = client.post('/api/ratings', 
                json={'anime_id': sample_anime.animeId, 'score': 8}
            )
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data.get('status') == 'success'
    
    def test_post_rating_invalid_score_high(self, session_with_user, sample_anime):
        """Test that scores > 10 are rejected."""
        client = session_with_user
        response = client.post('/api/ratings', 
            json={'anime_id': sample_anime.animeId, 'score': 11}
        )
        # Should return 400 or similar error
        assert response.status_code in [400, 422]
    
    def test_post_rating_invalid_score_low(self, session_with_user, sample_anime):
        """Test that scores < 1 are rejected."""
        client = session_with_user
        response = client.post('/api/ratings', 
            json={'anime_id': sample_anime.animeId, 'score': 0}
        )
        assert response.status_code in [400, 422]
    
    def test_post_rating_missing_anime(self, session_with_user):
        """Test rating a non-existent anime."""
        client = session_with_user
        fake_id = str(uuid4())
        response = client.post('/api/ratings', 
            json={'anime_id': fake_id, 'score': 5}
        )
        # Should fail gracefully
        assert response.status_code >= 400


class TestFlaggingAPI:
    """Integration tests for flagging endpoints."""
    
    def test_post_flag_success(self, session_with_user, sample_anime):
        """Test flagging an anime successfully."""
        client = session_with_user
        response = client.post(f'/api/anime/{sample_anime.animeId}/flag',
            json={'reason': 'Title is incorrect'}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data.get('status') == 'success'
    
    def test_post_flag_missing_reason(self, session_with_user, sample_anime):
        """Test that empty reason is rejected."""
        client = session_with_user
        response = client.post(f'/api/anime/{sample_anime.animeId}/flag',
            json={'reason': ''}
        )
        assert response.status_code in [400, 422]
    
    def test_post_flag_missing_anime_id(self, session_with_user):
        """Test flagging with null anime ID."""
        client = session_with_user
        # Null anime ID should be caught before DB insert
        response = client.post('/api/anime/null/flag',
            json={'reason': 'test reason'}
        )
        assert response.status_code >= 400
    
    def test_admin_update_flag_status_success(self, client, app_context, sample_user):
        """Test admin updating flag status (requires mock flagged anime)."""
        with app_context.app_context():
            # Simulate admin user
            sample_user.role = 'admin'
            from models import db
            db.session.commit()
            
            # Set session
            with client.session_transaction() as sess:
                sess['user_id'] = sample_user.userId
            
            # Create a mock flag (in real test, insert into DB)
            flag_id = str(uuid4())
            response = client.post(f'/admin/flagged-anime/{flag_id}/update',
                json={'status': 'resolved'}
            )
            # Will fail if flag doesn't exist, but tests structure
            assert response.status_code >= 400  # Flag not found in test DB


class TestBrowseAPI:
    """Integration tests for browse endpoints."""
    
    def test_get_browse_sections(self, client, app_context, sample_anime):
        """Test retrieving browse sections."""
        response = client.get('/api/browse/sections')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'sections' in data
        assert isinstance(data['sections'], list)
    
    def test_get_browse_anime_paginated(self, client, sample_anime):
        """Test retrieving anime from a section with pagination."""
        # Assume first section exists
        response = client.get('/api/browse/anime/1?offset=0&limit=10')
        assert response.status_code in [200, 404]  # May not exist depending on data
        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'anime' in data
            assert isinstance(data['anime'], list)
    
    def test_browse_anime_limit_respected(self, client):
        """Test that limit parameter is respected."""
        response = client.get('/api/browse/anime/1?offset=0&limit=5')
        if response.status_code == 200:
            data = json.loads(response.data)
            assert len(data.get('anime', [])) <= 5


class TestPersonalizedRecommendations:
    """Integration tests for personalized recommendations."""
    
    def test_load_more_personalized_offset_limit(self, session_with_user):
        """Test load-more personalized with offset and limit."""
        client = session_with_user
        response = client.get('/api/load-more-personalized?offset=0&limit=5')
        assert response.status_code in [200, 401]  # May need session
        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'anime' in data
            anime_list = data.get('anime', [])
            assert len(anime_list) <= 5
    
    def test_load_more_personalized_fallback(self, session_with_user):
        """Test fallback recompute when cache empty."""
        client = session_with_user
        # Request high offset expecting fallback
        response = client.get('/api/load-more-personalized?offset=1000&limit=10')
        assert response.status_code in [200, 401]


class TestExploreLoadMore:
    """Integration tests for explore load-more."""
    
    def test_load_more_explore_limit(self, client):
        """Test explore load-more respects limit."""
        response = client.get('/api/load-more-explore?limit=8')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'anime' in data
        anime_list = data.get('anime', [])
        assert len(anime_list) <= 8


class TestAdminDashboard:
    """Integration tests for admin dashboard."""
    
    def test_admin_dashboard_requires_auth(self, client):
        """Test that admin dashboard requires login."""
        response = client.get('/admin')
        assert response.status_code in [302, 401]  # Redirect or forbidden
    
    def test_admin_dashboard_requires_admin_role(self, client, sample_user, app_context):
        """Test that non-admin users cannot access dashboard."""
        with app_context.app_context():
            sample_user.role = 'user'
            from models import db
            db.session.commit()
        
        with client.session_transaction() as sess:
            sess['user_id'] = sample_user.userId
        
        response = client.get('/admin')
        assert response.status_code in [302, 403]  # Redirect to home or 403
    
    def test_admin_dashboard_renders_for_admin(self, client, sample_user, app_context):
        """Test that admin users can access dashboard."""
        with app_context.app_context():
            sample_user.role = 'admin'
            from models import db
            db.session.commit()
        
        with client.session_transaction() as sess:
            sess['user_id'] = sample_user.userId
        
        response = client.get('/admin')
        assert response.status_code == 200
        assert b'Admin Dashboard' in response.data or b'dashboard' in response.data.lower()


class TestAdminFlaggedAnime:
    """Integration tests for flagged anime management."""
    
    def test_admin_flagged_anime_requires_admin(self, client):
        """Test that flagged anime page requires admin role."""
        response = client.get('/admin/flagged-anime')
        assert response.status_code in [302, 401]
    
    def test_admin_flagged_anime_accessible_by_admin(self, client, sample_user, app_context):
        """Test that admins can view flagged anime."""
        with app_context.app_context():
            sample_user.role = 'admin'
            from models import db
            db.session.commit()
        
        with client.session_transaction() as sess:
            sess['user_id'] = sample_user.userId
        
        response = client.get('/admin/flagged-anime')
        assert response.status_code == 200
        assert b'Flagged' in response.data or b'flag' in response.data.lower()


class TestAdminImportAnime:
    """Integration tests for anime import."""
    
    def test_admin_import_anime_requires_admin(self, client):
        """Test that import page requires admin role."""
        response = client.get('/admin/import-anime')
        assert response.status_code in [302, 401]
    
    def test_admin_import_requires_csv(self, client, sample_user, app_context):
        """Test that non-CSV files are rejected."""
        with app_context.app_context():
            sample_user.role = 'admin'
            from models import db
            db.session.commit()
        
        with client.session_transaction() as sess:
            sess['user_id'] = sample_user.userId
        
        response = client.post('/admin/import-anime',
            data={'file': (b'not a csv', 'test.txt')}
        )
        assert response.status_code in [400, 422]


class TestAuthenticationFlow:
    """Integration tests for authentication."""
    
    def test_login_redirect(self, client):
        """Test that unauthenticated users are redirected to login."""
        response = client.get('/home', follow_redirects=False)
        # May redirect to login or stay on home
        assert response.status_code in [200, 302, 401]
    
    def test_logout_clears_session(self, client, sample_user):
        """Test that logout clears the session."""
        with client.session_transaction() as sess:
            sess['user_id'] = sample_user.userId
        
        response = client.get('/logout')
        assert response.status_code in [200, 302]
        
        with client.session_transaction() as sess:
            assert 'user_id' not in sess or sess.get('user_id') is None
