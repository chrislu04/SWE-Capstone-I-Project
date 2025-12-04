from models import db, Watchlist, Anime
from sqlalchemy.dialects.postgresql import UUID
import uuid

class WatchlistService:
    def get_watchlists_for_user(self, user_id):
        return Watchlist.query.filter_by(userId=user_id).all()

    def create_watchlist(self, user_id, name):
        new_watchlist = Watchlist(
            userId=user_id,
            name=name,
            items=[]
        )
        db.session.add(new_watchlist)
        db.session.commit()
        return new_watchlist

    def delete_watchlist(self, watchlist_id):
        watchlist = Watchlist.query.get(watchlist_id)
        if watchlist:
            db.session.delete(watchlist)
            db.session.commit()
            return True
        return False

    def get_watchlist_by_id(self, watchlist_id):
        return Watchlist.query.get(watchlist_id)

    def add_anime_to_watchlist(self, watchlist_id, anime_id):
        watchlist = self.get_watchlist_by_id(watchlist_id)
        anime = Anime.query.get(anime_id)
        if watchlist and anime:
            # Ensure items is a list
            if not isinstance(watchlist.items, list):
                watchlist.items = []
            
            # Create a mutable copy of the items
            items = list(watchlist.items)
            
            # Add the new item
            items.append({'animeId': str(anime_id), 'title': anime.title})
            
            # Assign the modified list back to the model
            watchlist.items = items
            
            db.session.commit()
            return True
        return False


    def remove_anime_from_watchlist(self, watchlist_id, anime_id):
        watchlist = self.get_watchlist_by_id(watchlist_id)
        if watchlist:
            # Ensure items is a list
            if not isinstance(watchlist.items, list):
                return False  # Or handle as an error

            # Create a mutable copy of the items
            items = list(watchlist.items)

            # Find and remove the item
            original_length = len(items)
            items = [item for item in items if item.get('animeId') != str(anime_id)]

            if len(items) < original_length:
                # If an item was removed, update the watchlist
                watchlist.items = items
                db.session.commit()
                return True
        return False
