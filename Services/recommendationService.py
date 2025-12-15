from Services.db_utils import execute_query
import re

class RecommendationService:
    def extract_series_name(self, title):
        """
        Extract the base series name from an anime title.
        Removes season numbers, part numbers, and common indicators.
        """
        if not title:
            return ""
        
        # Remove common season/part patterns
        series_name = title
        
        # Remove "Season X" (including Roman numerals and written out)
        series_name = re.sub(r'\s+[Ss]eason\s+[IVXivx0-9]+', '', series_name)
        series_name = re.sub(r'\s+[Ss]eason\s+\w+', '', series_name)
        
        # Remove "Part X"
        series_name = re.sub(r'\s+[Pp]art\s+[IVXivx0-9]+', '', series_name)
        series_name = re.sub(r'\s+[Pp]art\s+\w+', '', series_name)
        
        # Remove trailing Roman numerals that indicate seasons
        series_name = re.sub(r'\s+[IVX]+\s*$', '', series_name)
        
        # Remove numbers in parentheses at the end
        series_name = re.sub(r'\s*\(\d+\)\s*$', '', series_name)
        
        # Remove trailing colons and spaces
        series_name = series_name.rstrip(': ').strip()
        
        return series_name
    
    def get_recommendations(self, anime_id):
        """
        Get "if you liked x, try y" recommendations based on:
        1. Same anime series (sequels, seasons)
        2. Anime with matching genres (prioritize more genre matches)
        """
        try:
            # Ensure anime_id is a string
            anime_id = str(anime_id)
            print(f"[DEBUG] get_recommendations called with anime_id: {anime_id}")
            
            # Step 1: Get the source anime's information
            source_query = """
                SELECT a."animeId", a.title, a."releaseYear", a.episodes, ag.genres
                FROM "animeCatalog" a
                LEFT JOIN "animeGenres" ag ON a."animeId" = ag."animeId"
                WHERE a."animeId" = :anime_id LIMIT 1
            """
            source_result = execute_query(source_query, {"anime_id": anime_id}, fetch=True)
            
            if not source_result or not source_result[0].get('genres'):
                print(f"[WARNING] No genres found for anime {anime_id}")
                return []
            
            source_anime = source_result[0]
            source_title = source_anime.get('title', '')
            source_year = source_anime.get('releaseYear')
            source_episodes = source_anime.get('episodes')
            
            # Extract series name from title
            series_name = self.extract_series_name(source_title)
            print(f"[DEBUG] Source anime: '{source_title}' (year: {source_year})")
            print(f"[DEBUG] Extracted series name: '{series_name}'")
            
            # Parse genres
            raw_genres = source_anime.get('genres', '')
            genres = [g.strip() for g in raw_genres.split(',') if g.strip()]
            
            if not genres:
                print(f"[WARNING] No valid genres parsed for anime {anime_id}")
                return []
            
            print(f"Source anime has {len(genres)} genres: {genres}")
            
            # Step 2: Look for other entries in the same series
            # Search for anime with same series name (case-insensitive, partial match)
            same_series_query = """
                SELECT DISTINCT a."animeId", a.title, a."releaseYear", a."averageRating", 
                       a.type, a.episodes, a."imageUrl", ag.genres
                FROM "animeCatalog" a
                INNER JOIN "animeGenres" ag ON a."animeId" = ag."animeId"
                WHERE a."animeId" != :anime_id
                AND (
                    a.title ILIKE :series_pattern
                    OR a.title ILIKE :series_pattern_season
                    OR a.title ILIKE :series_pattern_part
                )
                ORDER BY a."releaseYear" ASC, a.episodes ASC, a."averageRating" DESC
                LIMIT 60
            """
            
            params = {
                "anime_id": anime_id,
                "series_pattern": f"%{series_name}%",
                "series_pattern_season": f"%{series_name}% season%",
                "series_pattern_part": f"%{series_name}% part%"
            }
            
            same_series = execute_query(same_series_query, params, fetch=True)
            same_series_count = len(same_series) if same_series else 0
            print(f"[DEBUG] Found {same_series_count} anime in same series")
            
            if same_series and same_series_count > 0:
                print(f"[DEBUG] Returning {same_series_count} anime from same series:")
                for rec in same_series[:5]:
                    print(f"  - {rec.get('title')} ({rec.get('releaseYear')})")
                return same_series
            
            # Step 3: If no series found, find anime by genre similarity with more matches
            print(f"[DEBUG] No same series found, searching by genre similarity...")
            
            # Build genre matching with explicit counting
            or_conditions = []
            for i, genre in enumerate(genres):
                param_name = f"genre{i}"
                or_conditions.append(f'ag.genres ILIKE :{param_name}')
                params[param_name] = f"%{genre}%"
            
            genre_query = """
                SELECT a."animeId", a.title, a."releaseYear", a."averageRating", 
                       a.type, a.episodes, a."imageUrl", ag.genres,
                       (
                           SELECT COUNT(*) 
                           FROM (
                               SELECT UNNEST(STRING_TO_ARRAY(ag.genres, ',')) as genre_item
                           ) genres_split
                           WHERE TRIM(genres_split.genre_item) IN ({genre_list})
                       ) as matching_genre_count
                FROM "animeCatalog" a
                INNER JOIN "animeGenres" ag ON a."animeId" = ag."animeId"
                WHERE a."animeId" != :anime_id
            """
            
            # Replace {genre_list} with actual genres - escape single quotes by doubling them
            genre_list = ','.join([f"'{g.replace(chr(39), chr(39)+chr(39))}'" for g in genres])
            genre_query = genre_query.replace('{genre_list}', genre_list)
            
            if or_conditions:
                genre_query += " AND (" + " OR ".join(or_conditions) + ")"
            
            genre_query += """
                ORDER BY matching_genre_count DESC, a."averageRating" DESC NULLS LAST
                LIMIT 60
            """
            
            print(f"Executing genre-based recommendation query")
            
            recommendations = execute_query(genre_query, params, fetch=True)
            result_count = len(recommendations) if recommendations else 0
            print(f"[DEBUG] Found {result_count} recommendations by genre match")
            
            if recommendations:
                print(f"[DEBUG] Top 3 recommendations:")
                for rec in recommendations[:3]:
                    matching_count = rec.get('matching_genre_count', 0)
                    print(f"  - {rec.get('title')} ({matching_count} matching genres)")
            
            return recommendations or []
            
        except Exception as e:
            print(f"Error in get_recommendations: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_personalized_recommendations(self, user_id, limit=12, offset=0):
        """
        Get personalized recommendations for a user based on:
        1. Check recommendation cache first (within last 24 hours)
        2. User's preferred genres from profilePreferences
        3. Genres from highly-rated anime (score >= 7)
        4. Exclude already rated anime
        """
        try:
            user_id = str(user_id)
            print(f"[DEBUG] get_personalized_recommendations called for user_id: {user_id} (limit={limit}, offset={offset})")
            
            # Try to get from cache first (if cache is less than 24 hours old)
            cache_query = """
                SELECT "payload" FROM "recommendationCache" 
                WHERE "userId" = :user_id 
                AND "updatedAt" > NOW() - INTERVAL '24 hours'
            """
            cache_result = execute_query(cache_query, {"user_id": user_id}, fetch=True)
            
            if cache_result and cache_result[0].get('payload'):
                import json
                cached_payload = cache_result[0]['payload']
                if isinstance(cached_payload, str):
                    cached_payload = json.loads(cached_payload)
                
                cached_anime = cached_payload if isinstance(cached_payload, list) else cached_payload.get('recommended_anime', [])
                print(f"[DEBUG] Using cached recommendations ({len(cached_anime)} anime)")
                
                # Apply offset and limit to cached results; if insufficient, fall through to recompute
                window = cached_anime[offset:offset + limit]
                if window and len(window) > 0:
                    return window
                else:
                    print(f"[DEBUG] Cache window empty for offset={offset}, limit={limit}; recomputing recommendations")
            
            # Get user's preferred genres from profilePreferences
            prefs_query = 'SELECT "preferredGenres" FROM "profilePreferences" WHERE "userId" = :user_id'
            prefs_result = execute_query(prefs_query, {"user_id": user_id}, fetch=True)
            
            preferred_genres = []
            if prefs_result and prefs_result[0].get('preferredGenres'):
                preferred_genres = prefs_result[0]['preferredGenres']
                if isinstance(preferred_genres, str):
                    import json
                    preferred_genres = json.loads(preferred_genres)
            
            # Get genres from user's highly-rated anime
            rated_genres_query = """
                SELECT DISTINCT ag.genres
                FROM "ratingSnapshots" rs
                JOIN "animeGenres" ag ON rs."animeId" = ag."animeId"
                WHERE rs."userId" = :user_id AND rs.score >= 7
            """
            rated_genres_result = execute_query(rated_genres_query, {"user_id": user_id}, fetch=True)
            
            # Combine genres from preferences and highly-rated anime
            all_genres = set(preferred_genres) if preferred_genres else set()
            if rated_genres_result:
                for row in rated_genres_result:
                    genre_str = row.get('genres', '')
                    if genre_str:
                        genres_list = [g.strip() for g in genre_str.split(',') if g.strip()]
                        all_genres.update(genres_list)
            
            if not all_genres:
                print(f"[DEBUG] No genres found for user {user_id}, returning popular anime")
                # Return popular anime if no genres found
                popular_query = """
                    SELECT DISTINCT a."animeId", a.title, a."releaseYear", a."averageRating", 
                           a.type, a.episodes, a."imageUrl", ag.genres
                    FROM "animeCatalog" a
                    INNER JOIN "animeGenres" ag ON a."animeId" = ag."animeId"
                    WHERE a."averageRating" >= 7.5
                    AND NOT EXISTS (
                        SELECT 1 FROM "ratingSnapshots" rs WHERE rs."animeId" = a."animeId" AND rs."userId" = :user_id
                    )
                    ORDER BY a."averageRating" DESC NULLS LAST
                    LIMIT :limit OFFSET :offset
                """
                return execute_query(popular_query, {"user_id": user_id, "limit": limit, "offset": offset}, fetch=True) or []
            
            print(f"[DEBUG] Found {len(all_genres)} total genres for recommendations: {list(all_genres)[:5]}...")
            
            # Build query to find anime matching user's preferred genres
            params = {"user_id": user_id, "limit": limit}
            or_conditions = []
            
            for i, genre in enumerate(all_genres):
                param_name = f"genre{i}"
                or_conditions.append(f'ag.genres ILIKE :{param_name}')
                params[param_name] = f"%{genre}%"
            
            genre_list = ','.join([f"'{g.replace(chr(39), chr(39)+chr(39))}'" for g in all_genres])
            
            recommendations_query = f"""
                SELECT DISTINCT a."animeId", a.title, a."releaseYear", a."averageRating", 
                       a.type, a.episodes, a."imageUrl", ag.genres,
                       (
                           SELECT COUNT(*) 
                           FROM (
                               SELECT UNNEST(STRING_TO_ARRAY(ag.genres, ',')) as genre_item
                           ) genres_split
                           WHERE TRIM(genres_split.genre_item) IN ({genre_list})
                       ) as matching_genre_count
                FROM "animeCatalog" a
                INNER JOIN "animeGenres" ag ON a."animeId" = ag."animeId"
                WHERE NOT EXISTS (
                    SELECT 1 FROM "ratingSnapshots" rs WHERE rs."animeId" = a."animeId" AND rs."userId" = :user_id
                )
            """
            
            if or_conditions:
                recommendations_query += " AND (" + " OR ".join(or_conditions) + ")"
            
            recommendations_query += """
                ORDER BY matching_genre_count DESC, a."averageRating" DESC NULLS LAST
                LIMIT :limit OFFSET :offset
            """
            
            params["offset"] = offset
            
            print(f"[DEBUG] Executing personalized recommendations query")
            recommendations = execute_query(recommendations_query, params, fetch=True)
            result_count = len(recommendations) if recommendations else 0
            print(f"[DEBUG] Found {result_count} personalized recommendations")
            
            if recommendations:
                print(f"[DEBUG] Top 3 personalized recommendations:")
                for rec in recommendations[:3]:
                    matching_count = rec.get('matching_genre_count', 0)
                    print(f"  - {rec.get('title')} ({matching_count} matching genres)")
                
                # Cache the recommendations for future use
                import json
                import uuid
                from decimal import Decimal
                from datetime import datetime, date

                def _sanitize_for_json(obj):
                    if isinstance(obj, dict):
                        return {k: _sanitize_for_json(v) for k, v in obj.items()}
                    if isinstance(obj, (list, tuple)):
                        return [_sanitize_for_json(v) for v in obj]
                    if isinstance(obj, uuid.UUID):
                        return str(obj)
                    if isinstance(obj, Decimal):
                        try:
                            return float(obj)
                        except Exception:
                            return str(obj)
                    if isinstance(obj, (datetime, date)):
                        return obj.isoformat()
                    return obj

                try:
                    cache_update_query = """
                        INSERT INTO "recommendationCache" ("userId", "payload", "sourceMetadata", "confidenceScore")
                        VALUES (:user_id, :payload, :metadata, :confidence)
                        ON CONFLICT ("userId") DO UPDATE
                        SET "payload" = :payload, "updatedAt" = NOW()
                    """
                    metadata = {
                        "genres_count": len(all_genres) if all_genres else 0,
                        "rating_based": True,
                        "result_count": result_count
                    }
                    sanitized_payload = _sanitize_for_json(recommendations)
                    result = execute_query(
                        cache_update_query,
                        {
                            "user_id": user_id,
                            "payload": json.dumps(sanitized_payload, ensure_ascii=False),
                            "metadata": json.dumps(metadata),
                            "confidence": 0.8
                        },
                        fetch=False
                    )
                    print(f"[DEBUG] Cached {result_count} recommendations for user {user_id}")
                except Exception as cache_err:
                    print(f"[WARNING] Failed to cache recommendations: {cache_err}")
                    import traceback
                    traceback.print_exc()
            
            return recommendations or []
            
        except Exception as e:
            print(f"Error in get_personalized_recommendations: {e}")
            import traceback
            traceback.print_exc()
            return []


