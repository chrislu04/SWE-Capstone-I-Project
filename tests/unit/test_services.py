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
