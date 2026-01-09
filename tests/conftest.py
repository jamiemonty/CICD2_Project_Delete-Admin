# tests/conftest.py
"""Test configuration and fixtures"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy. orm import sessionmaker
from sqlalchemy.pool import StaticPool
from docu_serve.main import app, get_db
from docu_serve.models import Base

# Test database URL (in-memory for speed)
TEST_DATABASE_URL = "sqlite:///:memory:"

# Create test engine with StaticPool to keep in-memory DB alive
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

# Create session factory
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def override_get_db():
    """Override get_db to use test database"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create test database tables once for all tests"""
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Override the dependency
    app.dependency_overrides[get_db] = override_get_db
    
    yield
    
    # Cleanup
    Base. metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def mock_publish_event():
    """Mock publish_event to avoid RabbitMQ/async issues"""
    with patch('docu_serve.main.publish_event', new_callable=AsyncMock) as mock:
        mock.return_value = None
        yield mock


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def db_session():
    """Provide a database session for tests"""
    session = TestingSessionLocal()
    try:
        yield session
        session.rollback()  # Rollback any uncommitted changes
    finally:
        session.close()