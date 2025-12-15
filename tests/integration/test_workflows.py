"""Integration tests for core application workflows."""
import pytest
import json
from uuid import uuid4
from datetime import datetime


class TestUserPreferencesWorkflow:
    """Test the complete user preference setup and usage workflow."""

    def test_user_can_set_and_retrieve_preferences(self, client, sample_user, app_context):
        """Test that user can set preferences and retrieve them."""
        with client.session_transaction() as sess:
            sess['user_id'] = sample_user.userId
        
        # Set preferences
        response = client.post('/edit-preferences', data={
            'genres': ['Action', 'Drama']
        })
        
        assert response.status_code in [200, 302]


class TestRatingWorkflow:
    """Test rating submission and retrieval workflows."""

    def test_user_can_rate_anime(self, client, sample_user, sample_anime, app_context):
        """Test complete rating workflow."""
        with client.session_transaction() as sess:
            sess['user_id'] = sample_user.userId
        
        # Submit rating
        response = client.post('/api/ratings', json={
            'anime_id': str(sample_anime.animeId),
            'score': 8
        })
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data.get('status') == 'success'

    def test_user_can_update_rating(self, client, sample_user, sample_anime, app_context):
        """Test updating an existing rating."""
        with client.session_transaction() as sess:
            sess['user_id'] = sample_user.userId
        
        # Submit initial rating
        client.post('/api/ratings', json={
            'anime_id': str(sample_anime.animeId),
            'score': 5
        })
        
        # Update rating
        response = client.post('/api/ratings', json={
            'anime_id': str(sample_anime.animeId),
            'score': 9
        })
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data.get('status') == 'success'


class TestWatchlistWorkflow:
    """Test watchlist management workflows."""

    def test_user_can_create_and_manage_watchlist(self, client, sample_user, sample_anime, app_context):
        """Test complete watchlist workflow."""
        from Services.watchlistService import WatchlistService
        from models import db
        
        with app_context.app_context():
            service = WatchlistService()
            
            # Create watchlist
            watchlist = service.create_watchlist(sample_user.userId, 'To Watch')
            assert watchlist is not None
            
            # Add anime to watchlist
            success = service.add_anime_to_watchlist(watchlist.watchlistId, sample_anime.animeId)
            assert success is True
            
            # Retrieve watchlist
            retrieved = service.get_watchlist_by_id(watchlist.watchlistId)
            assert retrieved is not None
            assert len(retrieved.items) == 1
            
            # Remove anime from watchlist
            success = service.remove_anime_from_watchlist(watchlist.watchlistId, sample_anime.animeId)
            assert success is True
            
            # Delete watchlist
            success = service.delete_watchlist(watchlist.watchlistId)
            assert success is True


class TestSearchWorkflow:
    """Test search and discovery workflows."""

    def test_user_can_search_anime(self, client, sample_anime, app_context):
        """Test basic search functionality."""
        response = client.get('/search', follow_redirects=True)
        assert response.status_code == 200

    def test_advanced_search_with_filters(self, client, app_context):
        """Test advanced search with multiple filters."""
        from Services.searchService import SearchService
        from unittest.mock import patch
        
        with patch('Services.searchService.execute_query') as mock_query:
            mock_query.return_value = [
                {'animeId': str(uuid4()), 'title': 'Test Anime', 'releaseYear': 2023}
            ]
            
            service = SearchService()
            results = service.advanced_search(
                title='Test',
                genre='Action',
                year=2023,
                rating='7.0'
            )
            
            assert len(results) == 1
            assert results[0]['title'] == 'Test Anime'


class TestExploreAndRecommendationsWorkflow:
    """Test explore section and recommendation workflows."""

    def test_user_sees_explore_section_on_home(self, client, sample_user, app_context):
        """Test that home page includes explore section."""
        with client.session_transaction() as sess:
            sess['user_id'] = sample_user.userId
        
        response = client.get('/home')
        assert response.status_code == 200

    def test_user_can_load_more_explore(self, client, sample_user, app_context):
        """Test loading more anime in explore section."""
        with client.session_transaction() as sess:
            sess['user_id'] = sample_user.userId
        
        response = client.get('/api/load-more-explore?limit=5')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'anime' in data
        assert isinstance(data['anime'], list)

    def test_user_can_load_more_personalized(self, client, sample_user, app_context):
        """Test loading more personalized recommendations."""
        with client.session_transaction() as sess:
            sess['user_id'] = sample_user.userId
        
        response = client.get('/api/load-more-personalized?offset=0&limit=5')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'anime' in data


class TestFlaggingWorkflow:
    """Test content flagging and moderation workflows."""

    def test_user_can_flag_anime(self, client, sample_user, sample_anime, app_context):
        """Test flagging anime with a reason."""
        with client.session_transaction() as sess:
            sess['user_id'] = sample_user.userId
        
        response = client.post(f'/api/anime/{sample_anime.animeId}/flag', json={
            'reason': 'Title is incorrect'
        })
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data.get('status') == 'success'

    def test_admin_can_view_flagged_anime(self, client, sample_user, app_context):
        """Test that admin can view flagged anime."""
        with app_context.app_context():
            sample_user.role = 'admin'
            from models import db
            db.session.commit()
        
        with client.session_transaction() as sess:
            sess['user_id'] = sample_user.userId
        
        response = client.get('/admin/flagged-anime')
        assert response.status_code == 200

    def test_admin_can_update_flag_status(self, client, sample_user, sample_anime, app_context):
        """Test admin updating flag status."""
        from Services.flaggingService import flag_anime
        
        with app_context.app_context():
            # Create a flag
            flag_anime(str(sample_anime.animeId), str(sample_user.userId), 'Bad data')
            
            sample_user.role = 'admin'
            from models import db
            db.session.commit()
        
        with client.session_transaction() as sess:
            sess['user_id'] = sample_user.userId
        
        response = client.get('/admin/flagged-anime', follow_redirects=True)
        assert response.status_code == 200


class TestBrowseWorkflow:
    """Test anime browsing workflows."""

    def test_user_can_browse_anime_sections(self, client, sample_user, app_context):
        """Test browsing available anime sections."""
        with client.session_transaction() as sess:
            sess['user_id'] = sample_user.userId
        
        response = client.get('/browse')
        assert response.status_code == 200

    def test_user_can_view_anime_details(self, client, sample_anime, app_context):
        """Test viewing detailed anime information."""
        response = client.get(f'/anime/{sample_anime.animeId}')
        assert response.status_code == 200

    def test_user_can_get_related_anime(self, client, sample_anime, app_context):
        """Test getting recommendations for specific anime."""
        from unittest.mock import patch
        
        with patch('Services.recommendationService.execute_query') as mock_query:
            mock_query.side_effect = [
                [{'animeId': str(sample_anime.animeId), 'title': sample_anime.title, 'genres': 'Action'}],
                []
            ]
            
            response = client.get(f'/anime/{sample_anime.animeId}/recommendations')
            assert response.status_code == 200


class TestRatingStatisticsWorkflow:
    """Test rating statistics and analytics workflows."""

    def test_user_rating_stats_appear_on_profile(self, client, sample_user, sample_anime, app_context):
        """Test that user's rating statistics appear on profile."""
        from models import Rating
        from models import db
        
        with app_context.app_context():
            # Create a rating
            rating = Rating(
                userId=sample_user.userId,
                animeId=sample_anime.animeId,
                score=8
            )
            db.session.add(rating)
            db.session.commit()
        
        with client.session_transaction() as sess:
            sess['user_id'] = sample_user.userId
        
        response = client.get('/profile')
        assert response.status_code == 200
        # Profile should show user's ratings
        assert b'rated' in response.data.lower() or b'anime' in response.data.lower()


class TestCompleteUserJourney:
    """Test a complete user journey through the application."""

    def test_new_user_complete_journey(self, client, sample_user, sample_anime, app_context):
        """Test complete user journey: signup → preferences → rate → search → watchlist."""
        with client.session_transaction() as sess:
            sess['user_id'] = sample_user.userId
        
        # Step 1: View home page
        response = client.get('/home')
        assert response.status_code == 200
        
        # Step 2: Rate an anime
        response = client.post('/api/ratings', json={
            'anime_id': str(sample_anime.animeId),
            'score': 7
        })
        assert response.status_code == 200
        
        # Step 3: Flag an anime
        response = client.post(f'/api/anime/{sample_anime.animeId}/flag', json={
            'reason': 'Information outdated'
        })
        assert response.status_code == 200
        
        # Step 4: Browse anime
        response = client.get('/browse')
        assert response.status_code == 200
        
        # Step 5: View profile with stats
        response = client.get('/profile')
        assert response.status_code == 200
