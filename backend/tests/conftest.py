"""Test fixtures for Flask app with in-memory SQLite."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def client(monkeypatch):
    import app.db.models  # noqa: F401
    from app.db.base import Base
    import app.db.base as db_base
    import app.main as main_mod

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(engine)

    monkeypatch.setattr(db_base, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(main_mod, "create_tables", lambda: Base.metadata.create_all(engine))

    app = main_mod.create_app()
    app.config["TESTING"] = True

    with app.test_client() as test_client:
        yield test_client

    Base.metadata.drop_all(engine)
    engine.dispose()
