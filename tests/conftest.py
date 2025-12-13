import os
import sqlite3
import pytest
from fastapi.testclient import TestClient
from docu_serve.main import app, get_db

# Define test database path
TEST_DB = "users_test.db"

# Override the get_db dependency to use the test database
def override_get_db():
    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    return conn
#Test Database setup and teardown
@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
# Remove existing test database if any
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
# Create test database and users table
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            age INTEGER,
            hashed_password TEXT,
            role TEXT
        )
    """)
    #commit and close
    conn.commit()
    conn.close()
    # Override the dependency
    app.dependency_overrides[get_db] = override_get_db
    yield
    # Teardown: remove test database
    os.remove(TEST_DB)

@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)
