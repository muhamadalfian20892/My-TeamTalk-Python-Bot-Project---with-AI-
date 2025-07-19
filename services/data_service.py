
import sqlite3
import datetime
import logging
from threading import Lock

class DataService:
    def __init__(self, db_file):
        self.db_file = db_file
        self.conn = None
        self.lock = Lock()
        try:
            # `check_same_thread=False` is safe here because we use our own lock
            self.conn = sqlite3.connect(db_file, check_same_thread=False)
            self.init_db()
        except sqlite3.Error as e:
            logging.error(f"Database connection failed: {e}")
            self.conn = None

    def init_db(self):
        if not self.conn: return
        with self.lock:
            cursor = self.conn.cursor()
            # Last Seen Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS last_seen (
                    user_id INTEGER PRIMARY KEY,
                    nick TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL
                )
            ''')
            # AFK Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS afk_status (
                    user_id INTEGER PRIMARY KEY,
                    nick TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            ''')
            self.conn.commit()
            logging.info(f"Database '{self.db_file}' initialized successfully.")

    def close(self):
        if self.conn:
            self.conn.close()
            logging.info("Database connection closed.")

    def update_last_seen(self, user_id: int, nick: str, action: str):
        if not self.conn: return
        timestamp = datetime.datetime.now().isoformat()
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute('''
                    INSERT INTO last_seen (user_id, nick, timestamp, action)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                    nick=excluded.nick, timestamp=excluded.timestamp, action=excluded.action
                ''', (user_id, nick, timestamp, action))
                self.conn.commit()
            except sqlite3.Error as e:
                logging.error(f"Failed to update last_seen for {nick}: {e}")

    def get_last_seen(self, nick: str) -> dict | None:
        if not self.conn: return None
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT nick, timestamp, action FROM last_seen WHERE lower(nick) = ?", (nick.lower(),))
                row = cursor.fetchone()
                if row:
                    return {'nick': row[0], 'timestamp': row[1], 'action': row[2]}
                return None
            except sqlite3.Error as e:
                logging.error(f"Failed to get last_seen for {nick}: {e}")
                return None

    def set_afk(self, user_id: int, nick: str, reason: str):
        if not self.conn: return
        timestamp = datetime.datetime.now().isoformat()
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute('''
                    INSERT INTO afk_status (user_id, nick, reason, timestamp)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                    nick=excluded.nick, reason=excluded.reason, timestamp=excluded.timestamp
                ''', (user_id, nick, reason, timestamp))
                self.conn.commit()
            except sqlite3.Error as e:
                logging.error(f"Failed to set AFK for {nick}: {e}")

    def remove_afk(self, user_id: int) -> bool:
        if not self.conn: return False
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM afk_status WHERE user_id = ?", (user_id,))
                self.conn.commit()
                return cursor.rowcount > 0
            except sqlite3.Error as e:
                logging.error(f"Failed to remove AFK for user_id {user_id}: {e}")
                return False

    def get_afk_user(self, user_id: int) -> dict | None:
        if not self.conn: return None
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT nick, reason, timestamp FROM afk_status WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                if row:
                    return {'nick': row[0], 'reason': row[1], 'timestamp': row[2]}
                return None
            except sqlite3.Error as e:
                logging.error(f"Failed to get AFK status for user_id {user_id}: {e}")
                return None
                
    def is_db_connected(self) -> bool:
        """Checks if the database connection is alive."""
        if not self.conn:
            return False
        try:
            self.conn.cursor()
            return True
        except (sqlite3.ProgrammingError, sqlite3.OperationalError):
            return False