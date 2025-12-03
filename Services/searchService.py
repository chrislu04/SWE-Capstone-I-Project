from app import execute_query

class SearchService:
    def advanced_search(self, title, genre, year, rating):
        """
        Performs an advanced search for anime based on multiple criteria.
        """
        query = "SELECT * FROM animes WHERE 1=1"
        params = []

        if title:
            query += " AND title ILIKE %s"
            params.append(f"%{title}%")
        
        if year:
            query += " AND EXTRACT(YEAR FROM aired) = %s"
            params.append(year)
        
        if rating:
            query += " AND score >= %s"
            params.append(rating)

        if genre:
            query += " AND genres ILIKE %s"
            params.append(f"%{genre}%")
        
        try:
            results = execute_query(query, params)
            return results
        except Exception as e:
            print(f"Error during advanced search: {e}")
            return []
