from __future__ import annotations

import structlog
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = structlog.get_logger(__name__)


def _existing_columns(conn, table: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {row[1] for row in rows}


def run_column_migrations(engine: Engine) -> None:
    """Add any missing columns to existing tables without dropping data."""
    with engine.begin() as conn:
        cols = _existing_columns(conn, "portal_lanes")
        if "notes" not in cols:
            conn.execute(text("ALTER TABLE portal_lanes ADD COLUMN notes TEXT"))
            logger.info("migration.applied", table="portal_lanes", column="notes")

        cols = _existing_columns(conn, "outreach_messages")
        if "source_type" not in cols:
            conn.execute(text("ALTER TABLE outreach_messages ADD COLUMN source_type VARCHAR(30)"))
            logger.info("migration.applied", table="outreach_messages", column="source_type")
        if "attempt_number" not in cols:
            conn.execute(text("ALTER TABLE outreach_messages ADD COLUMN attempt_number INTEGER NOT NULL DEFAULT 1"))
            logger.info("migration.applied", table="outreach_messages", column="attempt_number")
        if "is_follow_up" not in cols:
            conn.execute(text("ALTER TABLE outreach_messages ADD COLUMN is_follow_up BOOLEAN NOT NULL DEFAULT 0"))
            logger.info("migration.applied", table="outreach_messages", column="is_follow_up")
