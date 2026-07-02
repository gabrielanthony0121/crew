"""Persist roles removed during mute so they can be restored on unmute."""

import json
import sqlite3

from core.config import DATA_DIR, DATABASE_URL

MUTED_ROLES_DB = DATA_DIR / "muted_roles.db"

_CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS muted_roles (
        guild_id BIGINT NOT NULL,
        user_id BIGINT NOT NULL,
        role_ids TEXT NOT NULL,
        PRIMARY KEY (guild_id, user_id)
    )
"""


def using_postgres() -> bool:
    return bool(DATABASE_URL)


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def _init_sqlite() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(MUTED_ROLES_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS muted_roles (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role_ids TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id)
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


def init_muted_roles_db() -> None:
    if using_postgres():
        _init_postgres()
        return
    _init_sqlite()


def save_muted_roles(guild_id: int, user_id: int, role_ids: list[int]) -> None:
    payload = json.dumps(role_ids)

    if using_postgres():
        import psycopg2

        with psycopg2.connect(_normalize_database_url(DATABASE_URL)) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO muted_roles (guild_id, user_id, role_ids)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (guild_id, user_id)
                    DO UPDATE SET role_ids = EXCLUDED.role_ids
                    """,
                    (guild_id, user_id, payload),
                )
            conn.commit()
        return

    conn = sqlite3.connect(MUTED_ROLES_DB)
    conn.execute(
        """
        INSERT INTO muted_roles (guild_id, user_id, role_ids)
        VALUES (?, ?, ?)
        ON CONFLICT (guild_id, user_id) DO UPDATE SET role_ids = excluded.role_ids
        """,
        (guild_id, user_id, payload),
    )
    conn.commit()
    conn.close()


def get_muted_roles(guild_id: int, user_id: int) -> list[int]:
    if using_postgres():
        import psycopg2

        with psycopg2.connect(_normalize_database_url(DATABASE_URL)) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT role_ids FROM muted_roles
                    WHERE guild_id = %s AND user_id = %s
                    """,
                    (guild_id, user_id),
                )
                row = cur.fetchone()
    else:
        conn = sqlite3.connect(MUTED_ROLES_DB)
        row = conn.execute(
            "SELECT role_ids FROM muted_roles WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ).fetchone()
        conn.close()

    if not row:
        return []

    try:
        return [int(r) for r in json.loads(row[0])]
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


def clear_muted_roles(guild_id: int, user_id: int) -> None:
    if using_postgres():
        import psycopg2

        with psycopg2.connect(_normalize_database_url(DATABASE_URL)) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM muted_roles WHERE guild_id = %s AND user_id = %s",
                    (guild_id, user_id),
                )
            conn.commit()
        return

    conn = sqlite3.connect(MUTED_ROLES_DB)
    conn.execute(
        "DELETE FROM muted_roles WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    conn.commit()
    conn.close()