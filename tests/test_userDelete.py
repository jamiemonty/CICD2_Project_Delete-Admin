# tests/test_userDelete.py
"""Tests for DELETE /api/admin/delete/{user_id} endpoint"""

from fastapi.testclient import TestClient
from jose import jwt
from datetime import datetime, timedelta, timezone
from docu_serve.main import SECRET_KEY, ALGORITHM
from docu_serve.models import User
import pytest


def test_admin_can_delete_user(client, db_session):
    """Test admin can successfully delete a user"""
    # Insert a test user using SQLAlchemy
    user = User(
        name="Test User",
        email="test@example.com",
        age=25,
        hashed_password="abc123",
        role="user"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    user_id = user. user_id
    
    # Create admin JWT token
    token = jwt.encode(
        {
            "sub":  "admin@example.com",
            "role": "admin",
            "aud": "delete-service",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )
    
    # Delete the user
    response = client. delete(
        f"/api/admin/delete/{user_id}",
        headers={"Authorization":  f"Bearer {token}"}
    )
    
    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert "deleted" in data["message"]
    assert data["deleted"]["user_id"] == user_id
    assert data["deleted"]["email"] == "test@example.com"
    
    # Verify user is deleted from database
    deleted_user = db_session.query(User).filter(User.user_id == user_id).first()
    assert deleted_user is None


def test_delete_fails_without_token(client):
    """Test deletion fails without authentication token"""
    response = client.delete("/api/admin/delete/1")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_non_admin_cannot_delete_user(client):
    """Test non-admin user cannot delete"""
    token = jwt.encode(
        {
            "sub": "user@example.com",
            "role": "user",  # NOT admin
            "aud": "delete-service",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )
    
    response = client.delete(
        "/api/admin/delete/1",
        headers={"Authorization":  f"Bearer {token}"}
    )
    
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"


def test_expired_token_rejected(client):
    """Test expired JWT token is rejected"""
    expired_token = jwt.encode(
        {
            "sub": "admin@example.com",
            "role": "admin",
            "aud": "delete-service",
            "exp": datetime. now(timezone.utc) - timedelta(minutes=1)  # Expired
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
    """Test JWT with wrong audience is rejected"""
    token = jwt.encode(
        {
            "sub": "admin@example.com",
            "role": "admin",
            "aud": "wrong-service",  # Wrong audience
            "exp":  datetime.now(timezone.utc) + timedelta(minutes=30)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )
    
    response = client.delete(
        "/api/admin/delete/1",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response. status_code == 401


def test_delete_nonexistent_user(client):
    """Test deleting non-existent user returns 404"""
    token = jwt.encode(
        {
            "sub": "admin@example.com",
            "role": "admin",
            "aud": "delete-service",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )
    
    response = client. delete(
        "/api/admin/delete/99999",
        headers={"Authorization":  f"Bearer {token}"}
    )
    
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_token_missing_role(client):
    """Test JWT token without role field is rejected"""
    token = jwt.encode(
        {
            "sub": "admin@example. com",
            # Missing "role" field
            "aud": "delete-service",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30)
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


def test_delete_with_invalid_token_format(client):
    """Test deletion with malformed token"""
    response = client.delete(
        "/api/admin/delete/1",
        headers={"Authorization": "Bearer invalid-token-format"}
    )
    
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"