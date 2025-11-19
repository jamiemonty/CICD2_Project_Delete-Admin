from fastapi.testclient import TestClient
from jose import jwt
from datetime import datetime, timedelta
from app.main import SECRET_KEY, ALGORITHM, get_db
import sqlite3
import os


def test_admin_can_delete_user(client):
    # Insert a fake user in the test DB
    conn = get_db()# get test database connection, overrided in conftest.pyS
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (name, email, age, hashed_password, role)
        VALUES ('Test User', 'test@example.com', 25, 'abc123', 'user')
    """)
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Create a valid admin JWT
    token = jwt.encode(
        {
            "sub": "admin@example.com",
            "role": "admin",
            "aud": "delete-service",
            "exp": datetime.utcnow() + timedelta(minutes=30)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    # Call the delete endpoint
    response = client.delete(
        f"/api/admin/delete/{user_id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    # Assertions
    assert response.status_code == 200
    assert "deleted" in response.json()["message"]

def test_delete_fails_without_token(client):
    response = client.delete("/api/admin/delete/1")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"

def test_non_admin_cannot_delete_user(client):
    token = jwt.encode(
        {
            "sub": "user@example.com",
            "role": "user",       # NOT admin
            "aud": "delete-service",
            "exp": datetime.utcnow() + timedelta(minutes=30)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    response = client.delete(
        "/api/admin/delete/1",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"

def test_expired_token_rejected(client):
    expired_token = jwt.encode(
        {
            "sub": "admin@example.com",
            "role": "admin",
            "aud": "delete-service",
            "exp": datetime.utcnow() - timedelta(minutes=1)  # already expired
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    response = client.delete(
        "/api/admin/delete/1",
        headers={"Authorization": f"Bearer {expired_token}"}
    )

    assert response.status_code == 401

def test_wrong_audience_rejected(client):
    token = jwt.encode(
        {
            "sub": "admin@example.com",
            "role": "admin",
            "aud": "login-service",  # WRONG audience
            "exp": datetime.utcnow() + timedelta(minutes=30)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    response = client.delete(
        "/api/admin/delete/1",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401

def test_delete_nonexistent_user(client):
    token = jwt.encode(
        {
            "sub": "admin@example.com",
            "role": "admin",
            "aud": "delete-service",
            "exp": datetime.utcnow() + timedelta(minutes=30)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    response = client.delete(
        "/api/admin/delete/99999",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"

def test_token_missing_role(client):
    token = jwt.encode(
        {
            "sub": "admin@example.com",
            "aud": "delete-service",
            "exp": datetime.utcnow() + timedelta(minutes=30)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    response = client.delete(
        "/api/admin/delete/1",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403
