def execute_query(query, params=None, fetch=False):
    """Execute raw SQL query using SQLAlchemy connection"""
    try:
        from sqlalchemy import text
        from models import db
        # SQLAlchemy uses named parameters like :param_name, not %s
        result = db.session.execute(text(query), params or {})
        if fetch and query.strip().upper().startswith('SELECT'):
            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]
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
