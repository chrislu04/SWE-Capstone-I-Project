from pydantic import BaseModel, Field, ValidationError
from typing import Optional, List
import pandas as pd
import uuid
from datetime import datetime
from models import Anime, AnimeGenre, AnimeGenreDetailed, ImportJob, db
import json


class AnimeRowModel(BaseModel):
    animeId: str = Field(..., alias="animeID")
    title: str
    alternative_title: Optional[str] = None
    type: Optional[str] = None
    year: Optional[int] = None
    score: Optional[float] = None
    episodes: Optional[int] = None
    mal_url: Optional[str] = None
    sequel: Optional[bool] = None
    image_url: Optional[str] = None
    genres: Optional[str] = None
    genres_detailed: Optional[str] = None

    class Config:
        populate_by_name = True
        coerce_numbers_to_str = True

    @classmethod
    def model_validate(cls, obj):
        if isinstance(obj, dict):
            if 'year' in obj and obj['year'] and str(obj['year']).strip() in ('?', 'nan', 'N/A'):
                obj['year'] = None
            if 'score' in obj and obj['score'] and str(obj['score']).strip() in ('?', 'nan', 'N/A'):
                obj['score'] = None
        return super().model_validate(obj)

    def to_db_row(self):
        import ast

        def parse_list(val):
            if not val:
                return []
            try:
                parsed = ast.literal_eval(val)
                if isinstance(parsed, list):
                    return [str(g).strip() for g in parsed]
            except Exception:
                pass
            return [g.strip() for g in val.split(",") if g.strip()]

        return {
            "title": self.title,
            "alternativeTitle": self.alternative_title,
            "type": self.type,
            "releaseYear": self.year,
            "episodes": self.episodes,
            "malUrl": self.mal_url,
            "sequel": self.sequel,
            "imageUrl": self.image_url,
            "averageRating": self.score,
            "genres": parse_list(self.genres),
            "genresDetailed": parse_list(self.genres_detailed)
        }


def import_anime_csv(file, session, job_id: str = None):
    # Prepare session
    try:
        session.rollback()
    except Exception:
        pass

    # Read CSV; accept FileStorage-like objects (with .stream) or a file path
    try:
        if isinstance(file, str):
            df = pd.read_csv(file)
        else:
            stream = getattr(file, 'stream', None)
            if stream is not None:
                df = pd.read_csv(stream)
            else:
                df = pd.read_csv(file)
    except Exception as e:
        return {"success": False, "imported": 0, "error": f"Failed to read CSV: {str(e)}"}

    if 'sequel' in df.columns:
        df['sequel'] = df['sequel'].apply(
            lambda x: True if str(x).lower() == 'true' else False if str(x).lower() == 'false' else None
        )
    df = df.where(pd.notnull(df), None)
    valid_rows = []
    errors = []

    # Validate each row with Pydantic
    for idx, row in df.iterrows():
        try:
            row_dict = row.to_dict()
            if 'animeID' in row_dict and row_dict['animeID'] is not None:
                row_dict['animeID'] = str(row_dict['animeID'])
            if 'sequel' in row_dict and row_dict['sequel'] is not None:
                row_dict['sequel'] = str(row_dict['sequel'])
            anime = AnimeRowModel(**row_dict)
            valid_rows.append(anime.to_db_row())
        except ValidationError as ve:
            errors.append({"row": idx, "errors": [str(e) for e in ve.errors()]})

    session.autoflush = False

    # Main import loop with periodic job updates
    try:
        imported_count = 0
        total = len(valid_rows)
        batch_update_interval = 100

        job_uuid = None
        if job_id:
            try:
                job_uuid = uuid.UUID(job_id)
            except Exception:
                job_uuid = None

        for idx, row_data in enumerate(valid_rows, start=1):
            try:
                anime = Anime(
                    title=row_data["title"],
                    alternativeTitle=row_data["alternativeTitle"],
                    type=row_data["type"],
                    releaseYear=row_data["releaseYear"],
                    episodes=row_data["episodes"],
                    malUrl=row_data["malUrl"],
                    sequel=row_data["sequel"],
                    imageUrl=row_data["imageUrl"],
                    averageRating=row_data["averageRating"],
                    status="active"
                )
                session.add(anime)
                session.flush()  # Flush to get the generated animeId

                # Add genres
                for genre in row_data.get("genres", []) or []:
                    if genre:
                        genre_record = AnimeGenre(animeId=anime.animeId, genre=genre)
                        session.add(genre_record)

                # Add detailed genres
                for genre_detail in row_data.get("genresDetailed", []) or []:
                    if genre_detail:
                        genre_detail_record = AnimeGenreDetailed(animeId=anime.animeId, genreDetail=genre_detail)
                        session.add(genre_detail_record)

                imported_count += 1

                # Update job progress occasionally
                if job_uuid and (idx % batch_update_interval == 0 or idx == total):
                    try:
                        jb = session.query(ImportJob).get(job_uuid)
                        if jb:
                            payload = jb.payload or {}
                            payload.update({"progress": idx, "total": total})
                            payload_errors = payload.get('errors', [])
                            payload_errors.extend(errors)
                            payload['errors'] = payload_errors
                            jb.payload = payload
                            jb.status = 'running'
                            session.add(jb)
                            session.commit()
                    except Exception:
                        session.rollback()

            except Exception as row_err:
                # Don't rollback here - just log error and skip this row
                errors.append({"row": idx, "error": str(row_err)})
                try:
                    session.rollback()  # rollback just the failed row
                except Exception:
                    pass
                continue

        # Commit all successfully imported rows
        try:
            session.commit()
        except Exception as commit_err:
            session.rollback()
            raise Exception(f"Failed to commit import: {str(commit_err)}")

        # Final job update
        if job_uuid:
            try:
                jb = session.query(ImportJob).get(job_uuid)
                if jb:
                    payload = jb.payload or {}
                    payload.update({"progress": imported_count, "total": total})
                    payload_errors = payload.get('errors', [])
                    payload_errors.extend(errors)
                    payload['errors'] = payload_errors
                    jb.payload = payload
                    jb.status = 'completed'
                    session.add(jb)
                    session.commit()
            except Exception:
                session.rollback()

        return {
            "success": True,
            "imported": imported_count,
            "errors": errors,
            "message": f"Successfully imported {imported_count} anime records"
        }
    except Exception as e:
        try:
            session.rollback()
        except Exception:
            pass

        # Attempt to mark job failed
        if job_id:
            try:
                job_uuid = uuid.UUID(job_id)
                jb = session.query(ImportJob).get(job_uuid)
                if jb:
                    jb.payload = {"error": str(e)}
                    jb.status = 'failed'
                    session.add(jb)
                    session.commit()
            except Exception:
                try:
                    session.rollback()
                except Exception:
                    pass

        return {
            "success": False,
            "imported": 0,
            "error": str(e),
            "message": f"Import failed: {str(e)}"
        }

