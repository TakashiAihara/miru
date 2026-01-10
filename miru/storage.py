import sqlite3
import os
from contextlib import contextmanager
from typing import Optional, List, Dict, Any
from datetime import datetime

class Database:
    def __init__(self, db_path: str = "miru.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with self.get_connection() as conn:
            # Videos table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                s3_key TEXT UNIQUE NOT NULL,
                size INTEGER NOT NULL,
                last_modified TEXT,
                duration REAL,
                processed_at TEXT,
                fingerprint_path TEXT
            )
            """)
            
            # Create index on s3_key for fast lookups
            conn.execute("CREATE INDEX IF NOT EXISTS idx_s3_key ON videos (s3_key)")

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def add_or_update_video(self, key: str, size: int, last_modified: datetime) -> int:
        """
        Adds a video to the inventory or updates it if it exists.
        Returns the video ID.
        """
        with self.get_connection() as conn:
            conn.execute("""
            INSERT INTO videos (s3_key, size, last_modified)
            VALUES (?, ?, ?)
            ON CONFLICT(s3_key) DO UPDATE SET
                size=excluded.size,
                last_modified=excluded.last_modified
            """, (key, size, last_modified.isoformat()))
            
            cursor = conn.execute("SELECT id FROM videos WHERE s3_key = ?", (key,))
            return cursor.fetchone()['id']

    def mark_processed(self, video_id: int, duration: float, fingerprint_path: str):
        with self.get_connection() as conn:
            conn.execute("""
            UPDATE videos 
            SET processed_at = ?, duration = ?, fingerprint_path = ?
            WHERE id = ?
            """, (datetime.utcnow().isoformat(), duration, fingerprint_path, video_id))

    def get_unprocessed_videos(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.execute("""
            SELECT * FROM videos 
            WHERE processed_at IS NULL 
            ORDER BY last_modified DESC
            LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_all_videos(self) -> List[Dict[str, Any]]:
        """Iterator for all processed videos for searching."""
        # Using generator might be better for huge datasets
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM videos WHERE processed_at IS NOT NULL")
            return [dict(row) for row in cursor.fetchall()]
