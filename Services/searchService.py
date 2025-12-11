from Services.db_utils import execute_query

class SearchService:
    def advanced_search(self, title, genre, year, rating):
        """
        Performs an advanced search for anime based on multiple criteria.
        """
        query = 'SELECT ac.*, ag.genres FROM "animeCatalog" ac LEFT JOIN "animeGenres" ag ON ac."animeId" = ag."animeId" WHERE 1=1'
        params = {}

        if title:
            query += ' AND ac.title ILIKE :title'
            params['title'] = f"%{title}%"
        
        if year:
            query += ' AND ac."releaseYear" = :year'
            params['year'] = int(year)
        
        if rating:
            query += ' AND ac."averageRating" >= :rating'
            params['rating'] = float(rating)

        if genre:
            query += ' AND ag.genres ILIKE :genre'
            params['genre'] = f"%{genre}%"
        
        try:
            results = execute_query(query, params, fetch=True)
            return results
        except Exception as e:
            print(f"Error during advanced search: {e}")
            return []
