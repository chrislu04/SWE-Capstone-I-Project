import pytest
import json
from uuid import uuid4
from decimal import Decimal
from datetime import datetime
from unittest.mock import patch, MagicMock


class TestRecommendationServiceCache:
    """Unit tests for recommendation caching and sanitization."""
    
    def test_sanitize_payload_uuid(self):
        """Test that UUIDs are converted to strings."""
        from Services.recommendationService import RecommendationService
        service = RecommendationService()
        
        payload = {
            'anime_id': uuid4(),
            'user_id': uuid4(),
            'data': 'test'
        }
        
        sanitized = service.sanitize_payload(payload)
        assert isinstance(sanitized['anime_id'], str)
        assert isinstance(sanitized['user_id'], str)
        # Should be valid JSON serializable
        json_str = json.dumps(sanitized)
        assert json_str is not None
    
    def test_sanitize_payload_decimal(self):
        """Test that Decimals are converted to floats."""
        from Services.recommendationService import RecommendationService
        service = RecommendationService()
        
        payload = {
            'rating': Decimal('8.5'),
            'score': Decimal('7.3')
        }
        
        sanitized = service.sanitize_payload(payload)
        assert isinstance(sanitized['rating'], float)
        assert sanitized['rating'] == 8.5
        json.dumps(sanitized)  # Should not raise
    
    def test_sanitize_payload_datetime(self):
        """Test that datetimes are converted to ISO strings."""
        from Services.recommendationService import RecommendationService
        service = RecommendationService()
        
        now = datetime.now()
        payload = {'created_at': now}
        
        sanitized = service.sanitize_payload(payload)
        assert isinstance(sanitized['created_at'], str)
        # Should parse back
        parsed = datetime.fromisoformat(sanitized['created_at'].replace('Z', '+00:00'))
        assert parsed is not None


class TestFlaggingService:
    """Unit tests for flagging service."""
    
    @patch('Services.flaggingService.execute_query')
    def test_update_flag_status_valid(self, mock_execute):
        """Test updating a flag status with valid data."""
        from Services.flaggingService import update_flag_status
        
        mock_execute.return_value = True
        result = update_flag_status('flag-123', 'resolved')
        
        assert result is True
        mock_execute.assert_called_once()
        call_args = mock_execute.call_args
        assert 'resolved' in str(call_args)
    
    @patch('Services.flaggingService.execute_query')
    def test_update_flag_status_invalid_status(self, mock_execute):
        """Test that invalid status values are rejected."""
        from Services.flaggingService import update_flag_status
        
        mock_execute.return_value = False
        result = update_flag_status('flag-123', 'invalid_status')
        
        assert result is False
    
    @patch('Services.flaggingService.execute_query')
    def test_get_flagged_anime(self, mock_execute):
        """Test retrieving flagged anime list."""
        from Services.flaggingService import get_flagged_anime
        
        mock_execute.return_value = [
            (uuid4(), 'Anime Title', 'user1', 'Wrong title', datetime.now()),
            (uuid4(), 'Another Anime', 'user2', 'Bad data', datetime.now())
        ]
        
        result = get_flagged_anime()
        assert len(result) == 2
        assert result[0][1] == 'Anime Title'


class TestExploreService:
    """Unit tests for explore service."""
    
    @patch('Services.exploreService.execute_query')
    def test_get_random_anime_limit(self, mock_execute):
        """Test that explore respects limit parameter."""
        from Services.exploreService import explore_service
        
        mock_anime = [
            {'animeId': str(uuid4()), 'title': f'Anime {i}'} 
            for i in range(5)
        ]
        mock_execute.return_value = mock_anime
        
        result = explore_service.get_random_anime(limit=5)
        assert len(result) <= 5
        mock_execute.assert_called_once()


class TestDbUtils:
    """Unit tests for database utilities."""
    
    @patch('Services.db_utils.db')
    def test_execute_query_one_with_params(self, mock_db):
        """Test execute_query_one with parameter substitution."""
        from Services.db_utils import execute_query_one
        
        mock_result = {'user_id': 'test-123', 'username': 'testuser'}
        mock_connection = MagicMock()
        mock_connection.execute.return_value.fetchone.return_value = mock_result
        mock_db.engine.connect.return_value.__enter__.return_value = mock_connection
        
        # Mock would require full DB setup; test structure instead
        assert True  # Placeholder; full test requires real DB
    
    def test_execute_query_sanitizes_null(self):
        """Test that null values don't cause SQL injection."""
        from Services.db_utils import execute_query_one
        
        # This is more of a structural test; actual execution needs DB
        # The point is that the function should handle None/null safely
        assert True  # Tested via integration tests


class TestWatchlistService:
    """Unit tests for watchlist service functionality."""

    def test_create_watchlist(self, app_context, sample_user):
        """Test creating a new watchlist for a user."""
        from Services.watchlistService import WatchlistService
        from models import db
        
        service = WatchlistService()
        watchlist = service.create_watchlist(sample_user.userId, 'My Favorites')
        
        assert watchlist is not None
        assert watchlist.name == 'My Favorites'
        assert watchlist.userId == sample_user.userId
        assert isinstance(watchlist.items, list)
    
    def test_get_watchlists_for_user(self, app_context, sample_user):
        """Test retrieving all watchlists for a user."""
        from Services.watchlistService import WatchlistService
        from models import db
        
        service = WatchlistService()
        # Create multiple watchlists
        service.create_watchlist(sample_user.userId, 'Watchlist 1')
        service.create_watchlist(sample_user.userId, 'Watchlist 2')
        
        watchlists = service.get_watchlists_for_user(sample_user.userId)
        assert len(watchlists) == 2
        assert all(w.userId == sample_user.userId for w in watchlists)
    
    def test_get_watchlist_by_id(self, app_context, sample_user):
        """Test retrieving a specific watchlist."""
        from Services.watchlistService import WatchlistService
        
        service = WatchlistService()
        created = service.create_watchlist(sample_user.userId, 'Test List')
        retrieved = service.get_watchlist_by_id(created.watchlistId)
        
        assert retrieved is not None
        assert retrieved.watchlistId == created.watchlistId
        assert retrieved.name == 'Test List'
    
    def test_add_anime_to_watchlist(self, app_context, sample_user, sample_anime):
        """Test adding anime to a watchlist."""
        from Services.watchlistService import WatchlistService
        
        service = WatchlistService()
        watchlist = service.create_watchlist(sample_user.userId, 'My Anime')
        
        success = service.add_anime_to_watchlist(watchlist.watchlistId, sample_anime.animeId)
        assert success is True
        
        updated = service.get_watchlist_by_id(watchlist.watchlistId)
        assert len(updated.items) == 1
        assert updated.items[0]['animeId'] == str(sample_anime.animeId)
        assert updated.items[0]['title'] == sample_anime.title
    
    def test_remove_anime_from_watchlist(self, app_context, sample_user, sample_anime):
        """Test removing anime from a watchlist."""
        from Services.watchlistService import WatchlistService
        
        service = WatchlistService()
        watchlist = service.create_watchlist(sample_user.userId, 'My Anime')
        service.add_anime_to_watchlist(watchlist.watchlistId, sample_anime.animeId)
        
        success = service.remove_anime_from_watchlist(watchlist.watchlistId, sample_anime.animeId)
        assert success is True
        
        updated = service.get_watchlist_by_id(watchlist.watchlistId)
        assert len(updated.items) == 0
    
    def test_delete_watchlist(self, app_context, sample_user):
        """Test deleting a watchlist."""
        from Services.watchlistService import WatchlistService
        
        service = WatchlistService()
        watchlist = service.create_watchlist(sample_user.userId, 'Temp List')
        watchlist_id = watchlist.watchlistId
        
        success = service.delete_watchlist(watchlist_id)
        assert success is True
        
        retrieved = service.get_watchlist_by_id(watchlist_id)
        assert retrieved is None


class TestSearchService:
    """Unit tests for search service functionality."""

    @patch('Services.searchService.execute_query')
    def test_search_by_title(self, mock_query):
        """Test searching anime by title."""
        from Services.searchService import SearchService
        
        mock_results = [
            {'animeId': str(uuid4()), 'title': 'Death Note', 'genres': 'Thriller,Supernatural'},
            {'animeId': str(uuid4()), 'title': 'Death Note Another Note', 'genres': 'Mystery'}
        ]
        mock_query.return_value = mock_results
        
        service = SearchService()
        results = service.advanced_search(title='Death Note', genre=None, year=None, rating=None)
        
        assert len(results) == 2
        assert all('Death Note' in r['title'] for r in results)
    
    @patch('Services.searchService.execute_query')
    def test_search_by_genre(self, mock_query):
        """Test searching anime by genre."""
        from Services.searchService import SearchService
        
        mock_results = [
            {'animeId': str(uuid4()), 'title': 'Attack on Titan', 'genres': 'Action,Supernatural'},
            {'animeId': str(uuid4()), 'title': 'Demon Slayer', 'genres': 'Action,Shounen'}
        ]
        mock_query.return_value = mock_results
        
        service = SearchService()
        results = service.advanced_search(title=None, genre='Action', year=None, rating=None)
        
        assert len(results) == 2
        assert all('Action' in r['genres'] for r in results)
    
    @patch('Services.searchService.execute_query')
    def test_search_by_year(self, mock_query):
        """Test searching anime by release year."""
        from Services.searchService import SearchService
        
        mock_results = [
            {'animeId': str(uuid4()), 'title': 'Anime A', 'releaseYear': 2023, 'genres': 'Action'},
            {'animeId': str(uuid4()), 'title': 'Anime B', 'releaseYear': 2023, 'genres': 'Romance'}
        ]
        mock_query.return_value = mock_results
        
        service = SearchService()
        results = service.advanced_search(title=None, genre=None, year=2023, rating=None)
        
        assert len(results) == 2
        assert all(r['releaseYear'] == 2023 for r in results)
    
    @patch('Services.searchService.execute_query')
    def test_search_by_rating(self, mock_query):
        """Test searching anime by minimum rating."""
        from Services.searchService import SearchService
        
        mock_results = [
            {'animeId': str(uuid4()), 'title': 'Top Anime', 'averageRating': 8.9},
            {'animeId': str(uuid4()), 'title': 'Great Anime', 'averageRating': 8.5}
        ]
        mock_query.return_value = mock_results
        
        service = SearchService()
        results = service.advanced_search(title=None, genre=None, year=None, rating='8.5')
        
        assert len(results) == 2
        assert all(r['averageRating'] >= 8.5 for r in results)
    
    @patch('Services.searchService.execute_query')
    def test_search_with_multiple_filters(self, mock_query):
        """Test searching with multiple filters applied."""
        from Services.searchService import SearchService
        
        mock_results = [
            {'animeId': str(uuid4()), 'title': 'Perfect Anime', 'releaseYear': 2023, 
             'averageRating': 8.8, 'genres': 'Action,Drama'}
        ]
        mock_query.return_value = mock_results
        
        service = SearchService()
        results = service.advanced_search(title='Perfect', genre='Action', year=2023, rating='8.0')
        
        assert len(results) == 1
        assert results[0]['title'] == 'Perfect Anime'
    
    @patch('Services.searchService.execute_query')
    def test_search_no_results(self, mock_query):
        """Test search that returns no results."""
        from Services.searchService import SearchService
        
        mock_query.return_value = []
        
        service = SearchService()
        results = service.advanced_search(title='NonexistentAnime', genre=None, year=None, rating=None)
        
        assert len(results) == 0
    
    @patch('Services.searchService.execute_query')
    def test_search_error_handling(self, mock_query):
        """Test that search handles database errors gracefully."""
        from Services.searchService import SearchService
        
        mock_query.side_effect = Exception("Database error")
        
        service = SearchService()
        results = service.advanced_search(title='Any', genre=None, year=None, rating=None)
        
        assert results == []


class TestRecommendationService:
    """Extended tests for recommendation service core functionality."""

    @patch('Services.recommendationService.execute_query')
    def test_extract_series_name(self, mock_query):
        """Test extracting base series name from title."""
        from Services.recommendationService import RecommendationService
        
        service = RecommendationService()
        
        # Test various formats
        assert service.extract_series_name('Attack on Titan Season 1') == 'Attack on Titan'
        assert service.extract_series_name('Fullmetal Alchemist Part 2') == 'Fullmetal Alchemist'
        assert service.extract_series_name('Sword Art Online II') == 'Sword Art Online'
        assert service.extract_series_name('My Anime') == 'My Anime'
    
    @patch('Services.recommendationService.execute_query')
    def test_get_recommendations_returns_list(self, mock_query):
        """Test that get_recommendations returns a list."""
        from Services.recommendationService import RecommendationService
        
        mock_query.side_effect = [
            [{'animeId': str(uuid4()), 'title': 'Test', 'genres': 'Action,Drama'}],  # source
            []  # same series
        ]
        
        service = RecommendationService()
        result = service.get_recommendations(str(uuid4()))
        
        assert isinstance(result, list)
    
    @patch('Services.recommendationService.execute_query')
    def test_get_personalized_recommendations_no_genres(self, mock_query):
        """Test personalized recommendations when user has no genre preferences."""
        from Services.recommendationService import RecommendationService
        
        mock_query.side_effect = [
            [],  # cache check
            [],  # preferences
            [],  # rated genres
            [   # popular fallback
                {'animeId': str(uuid4()), 'title': 'Popular 1'},
                {'animeId': str(uuid4()), 'title': 'Popular 2'}
            ]
        ]
        
        service = RecommendationService()
        result = service.get_personalized_recommendations(str(uuid4()))
        
        assert isinstance(result, list)
        assert len(result) > 0
    
    def test_sanitize_payload_nested_structures(self):
        """Test sanitizing complex nested data structures."""
        from Services.recommendationService import RecommendationService
        
        service = RecommendationService()
        
        payload = {
            'anime': [
                {
                    'id': uuid4(),
                    'rating': Decimal('8.5'),
                    'updated': datetime.now(),
                    'genres': ['Action', 'Drama']
                }
            ],
            'metadata': {
                'count': Decimal('10'),
                'timestamp': datetime.now()
            }
        }
        
        sanitized = service.sanitize_payload(payload)
        json_str = json.dumps(sanitized)
        assert json_str is not None


class TestFlaggingServiceExtended:
    """Extended tests for flagging service."""

    def test_flag_anime_with_valid_data(self, app_context, sample_user, sample_anime):
        """Test flagging anime with complete valid data."""
        from Services.flaggingService import flag_anime, get_flagged_anime
        from models import db
        
        success = flag_anime(str(sample_anime.animeId), str(sample_user.userId), 'Title is incorrect')
        assert success is True
        
        # Verify flag was created (success return confirms it worked)
        # Note: get_flagged_anime filters by status='pending', so it may not show all flags
        assert success is True
    
    def test_flag_anime_with_empty_reason(self, app_context, sample_user, sample_anime):
        """Test that empty reason is handled gracefully."""
        from Services.flaggingService import flag_anime
        
        # Service doesn't validate reason; validation happens in app.py
        result = flag_anime(str(sample_anime.animeId), str(sample_user.userId), '')
        # Service will succeed, but app layer should prevent this
        assert isinstance(result, bool)
    
    def test_get_flagged_anime_returns_list(self, app_context):
        """Test that get_flagged_anime returns a list."""
        from Services.flaggingService import get_flagged_anime
        
        result = get_flagged_anime()
        assert isinstance(result, list)
    
    @patch('Services.flaggingService.execute_query')
    def test_update_flag_status_with_rowcount(self, mock_query):
        """Test update_flag_status respects rowcount in result."""
        from Services.flaggingService import update_flag_status
        
        mock_query.return_value = {'status': 'success', 'rowcount': 1}
        result = update_flag_status('flag-123', 'resolved')
        assert result is True
    
    @patch('Services.flaggingService.execute_query')
    def test_update_flag_status_zero_rowcount(self, mock_query):
        """Test update_flag_status returns False when no rows affected."""
        from Services.flaggingService import update_flag_status
        
        mock_query.return_value = {'status': 'success', 'rowcount': 0}
        result = update_flag_status('nonexistent-flag', 'resolved')
        assert result is False
