from Services.db_utils import execute_query

class RecommendationService:
    def get_recommendations(self, anime_id):
        """
        Get "if you liked x, try y" recommendations based on shared genres.
        """
        # Step 1: Get the genres of the given anime_id (comma-separated string)
        genre_query = """
            SELECT genres FROM "animeGenres" WHERE "animeId" = :anime_id
        """
        genres_result = execute_query(genre_query, {"anime_id": anime_id}, fetch=True)
        
        if not genres_result or not genres_result[0].get('genres'):
            return []
        
        # Parse comma-separated genres into a list
        raw_genres = genres_result[0]['genres']
        genres = [g.strip().lower() for g in raw_genres.split(',') if g.strip()]

        # Step 2: Find other anime that have at least one of the same genres
        recommendation_query = """
            SELECT DISTINCT a."animeId", a.title, a."releaseYear", a."averageRating"
            FROM "animeCatalog" a
            JOIN "animeGenres" ag ON a."animeId" = ag."animeId"
            WHERE (
                SELECT COUNT(*) > 0 FROM unnest(string_to_array(ag.genres, ',')) AS g 
                WHERE LOWER(TRIM(g)) = ANY(:genres)
            ) AND a."animeId" != :anime_id
            ORDER BY a."averageRating" DESC
            LIMIT 10
        """
        recommendations = execute_query(recommendation_query, {"genres": genres, "anime_id": anime_id}, fetch=True)

        return recommendations
