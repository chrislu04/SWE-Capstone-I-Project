def execute_query(query, params=None, fetch=False):
    """Execute raw SQL query using SQLAlchemy connection"""
    try:
        from sqlalchemy import text
        from models import db
        # SQLAlchemy uses named parameters like :param_name, not %s
        result = db.session.execute(text(query), params or {})
        if fetch and query.strip().upper().startswith('SELECT'):
            rows = result.fetchall()
            # Convert to dict and ensure consistent field naming
            result_dicts = []
            for row in rows:
                row_dict = dict(row._mapping)
                # PostgreSQL can return uppercase or lowercase keys, standardize them
                # Keep original keys but ensure animeId and imageUrl are available
                if 'animeid' in row_dict and 'animeId' not in row_dict:
                    row_dict['animeId'] = row_dict['animeid']
                if 'imageurl' in row_dict and 'imageUrl' not in row_dict:
                    row_dict['imageUrl'] = row_dict['imageurl']
                result_dicts.append(row_dict)
            return result_dicts
        else:
            db.session.commit()
            return {"status": "success", "rowcount": result.rowcount}
    except Exception as e:
        print(f"Query error: {e}")
        db.session.rollback()
        return None

def execute_query_one(query, params=None):
    """Execute SQL query and return single result"""
    try:
        from sqlalchemy import text
        from models import db
        # SQLAlchemy uses named parameters like :param_name, not %s
        result = db.session.execute(text(query), params or {})
        if query.strip().upper().startswith('SELECT'):
            row = result.fetchone()
            return dict(row._mapping) if row else None
        else:
            db.session.commit()
            return {"status": "success", "rowcount": result.rowcount}
    except Exception as e:
        print(f"Query error: {e}")
        db.session.rollback()
        return None
