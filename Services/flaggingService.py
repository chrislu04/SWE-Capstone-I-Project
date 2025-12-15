from Services.db_utils import execute_query, execute_query_one

def flag_anime(anime_id, user_id, reason):
    """
    Flags an anime for review.

    Args:
        anime_id (str): The ID of the anime to flag.
        user_id (str): The ID of the user flagging the anime.
        reason (str): The reason for flagging.

    Returns:
        bool: True if the anime was flagged successfully, False otherwise.
    """
    result = execute_query(
        """
        INSERT INTO "flagged_anime" ("animeId", "userId", "reason")
        VALUES (:anime_id, :user_id, :reason)
        """,
        {"anime_id": anime_id, "user_id": user_id, "reason": reason}
    )
    return result is not None

def get_flagged_anime():
    """
    Retrieves all flagged anime with a 'pending' status.

    Returns:
        list: A list of dictionaries, where each dictionary represents a flagged anime.
    """
    flagged_anime_list = execute_query(
        """
        SELECT f."flagId", a."title", u."username", f."reason", f."createdTime"
        FROM "flagged_anime" f
        JOIN "animeCatalog" a ON f."animeId" = a."animeId"
        JOIN "users" u ON f."userId" = u."userId"
        WHERE f."status" = 'pending'
        ORDER BY f."createdTime" DESC
        """,
        fetch=True
    )
    return flagged_anime_list or []

def update_flag_status(flag_id, status):
    """
    Updates the status of a flagged anime.

    Args:
        flag_id (str): The ID of the flag to update.
        status (str): The new status ('resolved' or 'dismissed').

    Returns:
        bool: True if the status was updated successfully, False otherwise.
    """
    if status not in ['resolved', 'dismissed', 'pending']:
        return False
    result = execute_query(
        """
        UPDATE "flagged_anime"
        SET "status" = :status
        WHERE "flagId" = :flag_id
        """,
        {"status": status, "flag_id": flag_id}
    )
    return result is not None
