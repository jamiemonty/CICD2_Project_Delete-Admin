from fastapi.testclient import TestClient
from jose import jwt
from datetime import datetime, timedelta
from app.main import SECRET_KEY, ALGORITHM
import sqlite3
import os

def test_admin_can_delete_user(client):
    # Insert a fake user in the test DB
    conn = sqlite3.connect("users_test.db")
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
