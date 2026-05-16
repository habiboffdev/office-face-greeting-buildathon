import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from config import DB_PATH


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS people (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                image_path TEXT NOT NULL,
                embedding_path TEXT,
                total_visits INTEGER DEFAULT 0,
                last_seen_at TEXT,
                is_vip INTEGER DEFAULT 0,
                birthday TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL,
                visited_at TEXT NOT NULL,
                FOREIGN KEY (person_id) REFERENCES people(id)
            );

            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL UNIQUE,
                title TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS greeting_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                title_template TEXT NOT NULL,
                subtitle_template TEXT NOT NULL,
                use_smart_rules INTEGER DEFAULT 0,
                birthday_title_template TEXT,
                birthday_subtitle_template TEXT
            );
            """
        )
        _migrate_people_columns(conn)
        _migrate_founders(conn)
        _migrate_founders_columns(conn)


def _migrate_founders(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS founders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL UNIQUE,
            hero_image_path TEXT NOT NULL,
            welcome_title TEXT NOT NULL,
            welcome_subtitle TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE CASCADE
        )
        """
    )


def _migrate_founders_columns(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(founders)").fetchall()}
    if "welcome_title_repeat" not in cols:
        conn.execute("ALTER TABLE founders ADD COLUMN welcome_title_repeat TEXT")
    if "welcome_subtitle_repeat" not in cols:
        conn.execute("ALTER TABLE founders ADD COLUMN welcome_subtitle_repeat TEXT")


def _migrate_people_columns(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(people)").fetchall()}
    if "birthday" not in cols:
        conn.execute("ALTER TABLE people ADD COLUMN birthday TEXT")
    if "is_vip" not in cols:
        conn.execute("ALTER TABLE people ADD COLUMN is_vip INTEGER DEFAULT 0")


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
