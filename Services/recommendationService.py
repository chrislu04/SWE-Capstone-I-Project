from app import execute_query

class RecommendationService:
    def get_recommendations(self, anime_id):
        """
        Get "if you liked x, try y" recommendations based on shared genres.
        """
        # Step 1: Get the genres of the given anime_id
        genre_query = """
            SELECT genre FROM "animeGenres" WHERE "animeId" = :anime_id
        """
        genres_result = execute_query(genre_query, {"anime_id": anime_id}, fetch=True)
        
        if not genres_result:
            return []
        
        genres = [row['genre'] for row in genres_result]

        # Step 2: Find other anime that have at least one of the same genres
        recommendation_query = """
            SELECT DISTINCT a."animeId", a.title, a."releaseYear", a."averageRating"
            FROM "animeCatalog" a
            JOIN "animeGenres" ag ON a."animeId" = ag."animeId"
            WHERE ag.genre = ANY(:genres) AND a."animeId" != :anime_id
            ORDER BY a."averageRating" DESC
            LIMIT 10
        """
        recommendations = execute_query(recommendation_query, {"genres": genres, "anime_id": anime_id}, fetch=True)

        return recommendations
