"""Persistent warnings storage — PostgreSQL (Railway) with SQLite fallback (local dev)."""

import sqlite3
from datetime import datetime

from core.config import DATA_DIR, DATABASE_URL

WARNINGS_DB = DATA_DIR / "warnings.db"

_CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS warnings (
        id SERIAL PRIMARY KEY,
        guild_id BIGINT NOT NULL,
        user_id BIGINT NOT NULL,
        moderator_id BIGINT NOT NULL,
        reason TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
"""


def using_postgres() -> bool:
    return bool(DATABASE_URL)


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def _format_rows(rows: list[tuple]) -> list[dict]:
    warnings_list = []
    for row in rows:
        try:
            dt = datetime.fromisoformat(row[3])
            formatted = dt.strftime("%d/%m/%Y às %H:%M")
        except Exception:
            formatted = row[3] or "Unknown date"

        warnings_list.append({
            "id": row[0],
            "moderator_id": row[1],
            "reason": row[2],
            "timestamp": formatted,
        })
    return warnings_list


def _init_sqlite() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(WARNINGS_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            moderator_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def _init_postgres() -> None:
    import psycopg2

    with psycopg2.connect(_normalize_database_url(DATABASE_URL)) as conn:
        with conn.cursor() as cur:
            cur.execute(_CREATE_TABLE_SQL)
        conn.commit()


def _migrate_sqlite_to_postgres() -> int:
    """Copy existing SQLite warns into PostgreSQL on first startup."""
    if not WARNINGS_DB.exists():
        return 0

    import psycopg2

    with psycopg2.connect(_normalize_database_url(DATABASE_URL)) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM warnings")
            if cur.fetchone()[0] > 0:
                return 0

    sqlite_conn = sqlite3.connect(WARNINGS_DB)
    rows = sqlite_conn.execute(
        "SELECT id, guild_id, user_id, moderator_id, reason, timestamp FROM warnings"
    ).fetchall()
    sqlite_conn.close()

    if not rows:
        return 0

    with psycopg2.connect(_normalize_database_url(DATABASE_URL)) as conn:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(
                    """
                    INSERT INTO warnings (id, guild_id, user_id, moderator_id, reason, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    row,
                )
            cur.execute(
                "SELECT setval(pg_get_serial_sequence('warnings', 'id'), COALESCE((SELECT MAX(id) FROM warnings), 1))"
            )
        conn.commit()

    print(f"[LOG] SQLite → PostgreSQL migration complete ({len(rows)} warnings)")
    return len(rows)


def init_warnings_db() -> None:
    print(f"[LOG] DATABASE_URL configured: {using_postgres()}")

    if using_postgres():
        _init_postgres()
        _migrate_sqlite_to_postgres()
        print("[LOG] Warnings database: PostgreSQL (DATABASE_URL)")
        return

    _init_sqlite()
    print(f"[LOG] Warnings database: SQLite fallback ({WARNINGS_DB})")
    print("[WARN] Set DATABASE_URL for persistent storage on Railway (PostgreSQL)")


def add_warning(guild_id: int, user_id: int, moderator_id: int, reason: str) -> int:
    ts = datetime.utcnow().isoformat()

    if using_postgres():
        import psycopg2

        with psycopg2.connect(_normalize_database_url(DATABASE_URL)) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO warnings (guild_id, user_id, moderator_id, reason, timestamp)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (guild_id, user_id, moderator_id, reason, ts),
                )
                warning_id = cur.fetchone()[0]
            conn.commit()
    else:
        conn = sqlite3.connect(WARNINGS_DB)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO warnings (guild_id, user_id, moderator_id, reason, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (guild_id, user_id, moderator_id, reason, ts),
        )
        warning_id = cur.lastrowid
        conn.commit()
        conn.close()

    print(
        f"[DEBUG] Warning saved | ID={warning_id} | Guild={guild_id} | User={user_id} "
        f"| Mod={moderator_id} | Reason={reason[:50]}"
    )
    return warning_id


def get_user_warnings(guild_id: int, user_id: int) -> list[dict]:
    if using_postgres():
        import psycopg2

        with psycopg2.connect(_normalize_database_url(DATABASE_URL)) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, moderator_id, reason, timestamp
                    FROM warnings
                    WHERE guild_id = %s AND user_id = %s
                    ORDER BY timestamp DESC
                    """,
                    (guild_id, user_id),
                )
                rows = cur.fetchall()
    else:
        conn = sqlite3.connect(WARNINGS_DB)
        rows = conn.execute(
            """
            SELECT id, moderator_id, reason, timestamp
            FROM warnings
            WHERE guild_id = ? AND user_id = ?
            ORDER BY timestamp DESC
            """,
            (guild_id, user_id),
        ).fetchall()
        conn.close()

    warnings_list = _format_rows(rows)
    print(f"[DEBUG] Review query | Guild={guild_id} | User={user_id} | Found={len(warnings_list)} warns")
    return warnings_list