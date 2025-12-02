import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ["DB_HOST"] = "localhost"
os.environ["DB_PORT"] = "5432"
os.environ["RABBITMQ_HOST"] = "localhost"
os.environ["RABBITMQ_PORT"] = "5672"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base, get_db
from psp_auth.testing import MockAuth
from src.auth import auth_config


@pytest.fixture(autouse=True)
def mock_lifespan_dependencies():
    """Mock asyncpg pool and background tasks for all tests"""

    # Create an async iterator for cursor that yields no results
    class AsyncCursorIterator:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    # Create a mock transaction that supports async context manager protocol
    mock_transaction = AsyncMock()
    mock_transaction.__aenter__ = AsyncMock(return_value=None)
    mock_transaction.__aexit__ = AsyncMock(return_value=None)

    # Create a mock connection that supports async context manager protocol
    mock_conn = AsyncMock()
    mock_conn.transaction = MagicMock(return_value=mock_transaction)
    mock_conn.cursor = MagicMock(return_value=AsyncCursorIterator())

    # Create a mock for acquire() that returns an async context manager
    mock_acquire = AsyncMock()
    mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acquire.__aexit__ = AsyncMock(return_value=None)

    # Create the pool mock
    mock_pool = AsyncMock()
    mock_pool.close = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=mock_acquire)

    async def mock_create_pool(*args, **kwargs):
        return mock_pool

    mock_result_collector = AsyncMock()

    with (
        patch("src.main.asyncpg.create_pool", side_effect=mock_create_pool),
        patch("src.main.result_collector", return_value=mock_result_collector),
    ):
        yield


@pytest.fixture
def client():
    """Simple test client for non-database tests"""
    from src.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def test_db():
    """Create an in-memory test database"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create a test database session
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def auth(monkeypatch):
    return MockAuth(auth_config.client_id, monkeypatch)


@pytest.fixture
def client_with_db(test_db):
    """Test client with test database for database tests"""
    from src.main import app

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
