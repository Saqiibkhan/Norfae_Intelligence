import os
import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


# Keep application imports and tests away from the configured live database.
# The ASGI tests do not run lifespan handlers or open a database connection.
os.environ["DATABASE_URL"] = (
    "postgresql+psycopg2://test:test@127.0.0.1:1/norfae_test"
)
os.environ["DISCORD_BOT_TOKEN"] = ""

from app.main import app  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.core.dependencies import get_db  # noqa: E402
from app.core.database import SessionLocal, TenantSession  # noqa: E402


TEST_SECRET = "isolated-api-test-key-with-at-least-32-bytes"


@pytest.fixture
def api_client(monkeypatch):
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", SecretStr(TEST_SECRET))
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")
    monkeypatch.setattr(settings, "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30)

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    original_bind = SessionLocal.kw["bind"]
    SessionLocal.configure(bind=engine)
    session_factory = sessionmaker(
        bind=engine, expire_on_commit=False, class_=TenantSession
    )

    def override_get_db():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    client.session_factory = session_factory
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        SessionLocal.configure(bind=original_bind)
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture(scope="session")
def application():
    return app


@pytest.fixture
def api_get(application):
    def get(path):
        async def request():
            transport = httpx.ASGITransport(app=application)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.get(path)

        return asyncio.run(request())

    return get
