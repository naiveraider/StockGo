from __future__ import annotations

from sqlalchemy import text


def ensure_instruments_is_etf_column(engine) -> None:
    """
    Lightweight "migration" to add instruments.is_etf for existing DBs.
    Works for MySQL and SQLite.
    """
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect == "mysql":
            exists = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'instruments'
                      AND COLUMN_NAME = 'is_etf'
                    """
                )
            ).scalar()
            if int(exists or 0) == 0:
                conn.execute(
                    text(
                        """
                        ALTER TABLE instruments
                        ADD COLUMN is_etf TINYINT(1) NOT NULL DEFAULT 0,
                        ADD INDEX ix_instruments_is_etf (is_etf)
                        """
                    )
                )
        elif dialect == "sqlite":
            cols = [r[1] for r in conn.execute(text("PRAGMA table_info('instruments')")).fetchall()]
            if "is_etf" not in cols:
                conn.execute(text("ALTER TABLE instruments ADD COLUMN is_etf INTEGER NOT NULL DEFAULT 0"))


def ensure_users_role_column(engine) -> None:
    """Add users.role column for existing DBs. Default: member."""
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect == "mysql":
            exists = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'users'
                      AND COLUMN_NAME = 'role'
                    """
                )
            ).scalar()
            if int(exists or 0) == 0:
                conn.execute(
                    text(
                        """
                        ALTER TABLE users
                        ADD COLUMN role VARCHAR(32) NOT NULL DEFAULT 'member',
                        ADD INDEX ix_users_role (role)
                        """
                    )
                )
        elif dialect == "sqlite":
            cols = [r[1] for r in conn.execute(text("PRAGMA table_info('users')")).fetchall()]
            if "role" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(32) NOT NULL DEFAULT 'member'"))

