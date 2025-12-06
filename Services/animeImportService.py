from pydantic import BaseModel, Field, ValidationError
from typing import Optional, List
import pandas as pd
import uuid
from datetime import datetime
from models import Anime, AnimeGenre, ImportJob, db
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

        base_genres = parse_list(self.genres)
        detailed_genres = parse_list(self.genres_detailed)

        # Preserve order while removing duplicates across both lists
        combined_genres = []
        for g in base_genres + detailed_genres:
            if g and g not in combined_genres:
                combined_genres.append(g)

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
            "genresCombined": combined_genres
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

    def update_job(job_uuid, status, progress, total, errors_list, started_at):
        """Persist progress info to ImportJob payload."""
        if not job_uuid:
            return
        try:
            percent = round((progress / total) * 100, 2) if total > 0 else 0
            elapsed = (datetime.utcnow() - started_at).total_seconds() if started_at else 0
            eta = None
            if elapsed > 0 and progress > 0 and total > 0:
                rate = progress / elapsed
                if rate > 0:
                    eta = max(int((total - progress) / rate), 0)
            payload = {
                "progress": progress,
                "total": total,
                "percent": percent,
                "errors": errors_list[:50] if errors_list else [],
                "elapsedSeconds": elapsed,
                "etaSeconds": eta,
                "updatedAt": datetime.utcnow().isoformat()
            }
            # Query using the current session's connection
            jb = session.query(ImportJob).filter(ImportJob.jobId == job_uuid).first()
            if jb:
                jb.payload = payload
                jb.status = status
                session.flush()
                session.commit()
        except Exception as e:
            pass

    # Main import loop with periodic job updates
    try:
        imported_count = 0
        total = len(valid_rows)
        # More frequent progress writes so the UI updates in real time
        # For small files, update more frequently
        if total <= 10:
            batch_update_interval = 1  # Update every row for very small files
        elif total <= 100:
            batch_update_interval = 5  # Update every 5 rows for small files
        elif total <= 1000:
            batch_update_interval = 50  # Update every 50 rows
        elif total <= 5000:
            batch_update_interval = 100  # Update every 100 rows
        else:
            batch_update_interval = 200  # Update every 200 rows for large files

        job_uuid = None
        job_start = datetime.utcnow()
        if job_id:
            try:
                job_uuid = uuid.UUID(job_id)
            except Exception:
                job_uuid = None

        # Initialize job payload with totals
        if job_uuid:
            update_job(job_uuid, 'running', 0, total, errors, job_start)

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

                # Add combined genres as a single comma-separated field
                combined_genres = row_data.get("genresCombined", []) or []
                genre_string = ",".join([g.strip() for g in combined_genres if g and g.strip()])
                if genre_string:
                    genre_record = AnimeGenre(animeId=anime.animeId, genres=genre_string)
                    session.add(genre_record)

                imported_count += 1

                # Update job progress occasionally
                if job_uuid and (idx % batch_update_interval == 0 or idx == total):
                    update_job(job_uuid, 'running', imported_count, total, errors, job_start)

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
            update_job(job_uuid, 'completed', imported_count, total, errors, job_start)

        # Build final stats for callers
        elapsed_final = (datetime.utcnow() - job_start).total_seconds() if job_start else None
        percent_final = round((imported_count / total) * 100, 2) if total else 0
        return {
            "success": True,
            "imported": imported_count,
            "errors": errors,
            "message": f"Successfully imported {imported_count} anime records",
            "progress": imported_count,
            "total": total,
            "percent": percent_final,
            "elapsedSeconds": elapsed_final,
            "etaSeconds": 0
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
                jb = session.get(ImportJob, job_uuid)
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

