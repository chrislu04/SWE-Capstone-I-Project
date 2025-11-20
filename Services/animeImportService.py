from pydantic import BaseModel, Field, ValidationError
from typing import Optional, List
import pandas as pd
import uuid
from datetime import datetime
from models import Anime

class AnimeRowModel(BaseModel):
    animeId: str = Field(..., alias="ID")
    title: str
    alternative_title: Optional[str] = None
    type: Optional[str] = None
    year: Optional[int] = None
    score: Optional[float] = None
    episodes: Optional[int] = None
    mal_url: Optional[str] = None
    sequel: Optional[str] = None
    image_url: Optional[str] = None
    genres: Optional[str] = None
    genres_detailed: Optional[str] = None

    class Config:
        populate_by_name = True

    def to_db_row(self):
        """Convert CSV row to Anime model data"""
        core_record = {
            "anime_id": self.animeId,
            "title": self.title,
            "alternativeTitle": self.alternative_title,
            "type": self.type,
            "releaseYear": self.year,
            "episodes": self.episodes,
            "malUrl": self.mal_url,
            "sequel": self.sequel,
            "imageUrl": self.image_url
        }
        about_me = {
            "genres": [g.strip() for g in (self.genres or "").split(",") if g.strip()],
            "genresDetailed": [g.strip() for g in (self.genres_detailed or "").split(",") if g.strip()]
        }
        popularity = {"averageRating": self.score}
        return {
            "animeId": self.animeId,
            "coreRecord": core_record,
            "aboutMe": about_me,
            "popularity": popularity,
            "status": "active",
            "dataFingerprint": str(uuid.uuid4()),
            "updateTime": datetime.utcnow()
        }


def import_anime_csv(file, session):
    """
    Import anime data from CSV file into database.
    
    Args:
        file: Flask FileStorage object
        session: SQLAlchemy session (db.session from app context)
    
    Returns:
        dict with import summary
    """
    try:
        # Read CSV
        df = pd.read_csv(file.stream)
        valid_rows = []
        errors = []
        
        # Validate each row with Pydantic
        for idx, row in df.iterrows():
            try:
                anime = AnimeRowModel(**row.to_dict())
                valid_rows.append(anime.to_db_row())
            except ValidationError as ve:
                errors.append({"row": idx, "errors": [str(e) for e in ve.errors()]})
        
        # Batch upsert all valid rows
        for row_data in valid_rows:
            # Check if anime exists
            existing = session.query(Anime).filter_by(animeId=row_data["animeId"]).first()
            
            if existing:
                # Update existing
                existing.coreRecord = row_data["coreRecord"]
                existing.aboutMe = row_data["aboutMe"]
                existing.popularity = row_data["popularity"]
                existing.status = row_data["status"]
                existing.dataFingerprint = row_data["dataFingerprint"]
                existing.updateTime = row_data["updateTime"]
            else:
                # Create new
                new_anime = Anime(
                    animeId=row_data["animeId"],
                    coreRecord=row_data["coreRecord"],
                    aboutMe=row_data["aboutMe"],
                    popularity=row_data["popularity"],
                    status=row_data["status"],
                    dataFingerprint=row_data["dataFingerprint"],
                    updateTime=row_data["updateTime"]
                )
                session.add(new_anime)
        
        # Commit transaction
        session.commit()
        
        return {
            "success": True,
            "imported": len(valid_rows),
            "errors": errors,
            "message": f"Successfully imported {len(valid_rows)} anime records"
        }
        
    except Exception as e:
        session.rollback()
        return {
            "success": False,
            "imported": 0,
            "error": str(e),
            "message": f"Import failed: {str(e)}"
        }

