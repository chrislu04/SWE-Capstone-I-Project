from models import db
from sqlalchemy import text


def _normalize_query_for_sqlite(query: str) -> str:
    """Replace PostgreSQL-specific NOW() with SQLite-friendly CURRENT_TIMESTAMP when needed."""
    try:
        if db.engine.url.get_backend_name() == 'sqlite':
            return query.replace('NOW()', 'CURRENT_TIMESTAMP')
    except Exception:
        pass
    return query


def execute_query(query, params=None, fetch=False):
    """Execute raw SQL query using SQLAlchemy connection."""
    try:
        normalized = _normalize_query_for_sqlite(query)
        result = db.session.execute(text(normalized), params or {})
        if fetch and normalized.strip().upper().startswith('SELECT'):
            rows = result.fetchall()
            result_dicts = []
            for row in rows:
                row_dict = dict(row._mapping)
                if 'animeid' in row_dict and 'animeId' not in row_dict:
                    row_dict['animeId'] = row_dict['animeid']
                if 'imageurl' in row_dict and 'imageUrl' not in row_dict:
                    row_dict['imageUrl'] = row_dict['imageurl']
                result_dicts.append(row_dict)
            return result_dicts
        db.session.commit()
        return {"status": "success", "rowcount": result.rowcount}
    except Exception as e:
        print(f"Query error: {e}")
        db.session.rollback()
        return None

def execute_query_one(query, params=None):
    """Execute SQL query and return single result."""
    try:
        normalized = _normalize_query_for_sqlite(query)
        result = db.session.execute(text(normalized), params or {})
        if normalized.strip().upper().startswith('SELECT'):
            row = result.fetchone()
            return dict(row._mapping) if row else None
        db.session.commit()
        return {"status": "success", "rowcount": result.rowcount}
    except Exception as e:
        print(f"Query error: {e}")
        db.session.rollback()
        return None
