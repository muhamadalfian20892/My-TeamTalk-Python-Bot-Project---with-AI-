
import collections
import datetime
import logging

class ContextHistoryManager:
    def __init__(self, retention_minutes: int = 60):
        self.history = collections.defaultdict(collections.deque)
        self.retention_minutes = retention_minutes
        logging.debug(f"ContextHistoryManager initialized with retention: {retention_minutes} minutes")

    def add_message(self, user_id: str, message: str, is_bot: bool = False):
        timestamp = datetime.datetime.now()
        self.history[user_id].append({'message': message, 'timestamp': timestamp, 'is_bot': is_bot})
        self._prune_history(user_id)
        logging.debug(f"Added message for user_id {user_id}. Current history length: {len(self.history[user_id])}")

    def get_history(self, user_id: str) -> list[dict]:
        self._prune_history(user_id)
        current_history = list(self.history[user_id])
        logging.debug(f"Retrieved history for user_id {user_id}. Length: {len(current_history)}")
        return current_history

    def set_retention_minutes(self, minutes: int):
        if minutes < 0:
            raise ValueError("Retention minutes cannot be negative.")
        logging.debug(f"Setting retention minutes to: {minutes}")
        self.retention_minutes = minutes
        for user_id in self.history:
            self._prune_history(user_id)

    def _prune_history(self, user_id: str):
        min_timestamp = datetime.datetime.now() - datetime.timedelta(minutes=self.retention_minutes)
        initial_len = len(self.history[user_id])
        while self.history[user_id] and self.history[user_id][0]['timestamp'] < min_timestamp:
            self.history[user_id].popleft()
        if len(self.history[user_id]) < initial_len:
            logging.debug(f"Pruned history for user_id {user_id}. Removed {initial_len - len(self.history[user_id])} messages.")

    def clear_history(self, user_id: str = None):
        if user_id:
            if user_id in self.history:
                del self.history[user_id]
                logging.debug(f"Cleared history for user_id: {user_id}")
        else:
            self.history.clear()
            logging.debug("Cleared all history.")
