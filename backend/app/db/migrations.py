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
        if "campaign_config_json" not in cols:
            conn.execute(text("ALTER TABLE portal_lanes ADD COLUMN campaign_config_json TEXT DEFAULT '{}'"))
            logger.info("migration.applied", table="portal_lanes", column="campaign_config_json")

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

        cols = _existing_columns(conn, "outreach_batches")
        batch_columns = {
            "send_email": "BOOLEAN NOT NULL DEFAULT 1",
            "send_whatsapp": "BOOLEAN NOT NULL DEFAULT 0",
            "whatsapp_template_name": "VARCHAR(100)",
            "whatsapp_language": "VARCHAR(20)",
            "email_sent_count": "INTEGER NOT NULL DEFAULT 0",
            "whatsapp_sent_count": "INTEGER NOT NULL DEFAULT 0",
        }
        for column, definition in batch_columns.items():
            if column not in cols:
                conn.execute(text(f"ALTER TABLE outreach_batches ADD COLUMN {column} {definition}"))
                logger.info("migration.applied", table="outreach_batches", column=column)

        cols = _existing_columns(conn, "messaging_messages")
        message_columns = {
            "lane_id": "CHAR(32)",
            "batch_id": "CHAR(32)",
            "outreach_row_id": "CHAR(32)",
            "carrier_name": "VARCHAR(500)",
            "source_type": "VARCHAR(30)",
        }
        for column, definition in message_columns.items():
            if column not in cols:
                conn.execute(text(f"ALTER TABLE messaging_messages ADD COLUMN {column} {definition}"))
                logger.info("migration.applied", table="messaging_messages", column=column)

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS bounced_emails (
                id TEXT NOT NULL PRIMARY KEY,
                email VARCHAR(254) NOT NULL UNIQUE,
                bounced_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                provider_message_id VARCHAR(100)
            )
        """))
        logger.info("migration.applied", table="bounced_emails", action="create_if_not_exists")
