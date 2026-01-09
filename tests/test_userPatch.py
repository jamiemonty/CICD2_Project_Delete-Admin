# tests/test_userPatch. py
"""Tests for PATCH /api/admin/users/{user_id} endpoint"""

from fastapi.testclient import TestClient
from jose import jwt
from datetime import datetime, timedelta, timezone
from docu_serve.main import SECRET_KEY, ALGORITHM
from docu_serve.models import User
import pytest


def test_patch_user_name_success(client, db_session):
    """Test successful name update"""
    user = User(
        name="Old Name",
        email="patch@test.com",
        age=30,
        hashed_password="hash123",
        role="user"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    user_id = user.user_id
    
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
    
    response = client.patch(
        f"/api/admin/users/{user_id}",
        json={"name": "New Name"},
        headers={"Authorization":  f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert data["email"] == "patch@test. com"


def test_patch_multiple_fields(client, db_session):
    """Test updating multiple fields"""
    user = User(
        name="Test",
        email="multi@test.com",
        age=20,
        hashed_password="hash",
        role="user"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    user_id = user.user_id
    
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
    
    response = client. patch(
        f"/api/admin/users/{user_id}",
        json={"name":  "Updated", "age": 35},
        headers={"Authorization":  f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    assert response.json()["name"] == "Updated"
    assert response. json()["age"] == 35


def test_patch_nonexistent_user(client):
    """Test 404 for nonexistent user"""
    token = jwt.encode(
        {
            "sub": "admin@example.com",
            "role":  "admin",
            "aud": "delete-service",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )
    
    response = client.patch(
        "/api/admin/users/99999",
        json={"name":  "Test"},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 404


def test_patch_without_admin(client):
    """Test non-admin cannot patch"""
    token = jwt.encode(
        {
            "sub":  "user@example.com",
            "role": "user",
            "aud": "delete-service",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )
    
    response = client.patch(
        "/api/admin/users/1",
        json={"name": "Hack"},
        headers={"Authorization":  f"Bearer {token}"}
    )
    
    assert response.status_code == 403


def test_patch_empty_payload(client, db_session):
    """Test 400 for empty payload"""
    user = User(
        name="Test",
        email="empty@test.com",
        age=25,
        hashed_password="hash",
        role="user"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    token = jwt.encode(
        {
            "sub": "admin@example.com",
            "role": "admin",
            "aud": "delete-service",
            "exp": datetime. now(timezone.utc) + timedelta(minutes=30)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )
    
    response = client. patch(
        f"/api/admin/users/{user.user_id}",
        json={},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response. status_code == 400


def test_patch_without_token(client):
    """Test patch without auth fails"""
    response = client. patch(
        "/api/admin/users/1",
        json={"name": "Test"}
    )
    
    assert response.status_code == 401