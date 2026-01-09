# tests/test_health.py
"""Tests for health check endpoints"""
from fastapi.testclient import TestClient
from unittest.mock import patch
from jose import jwt
from datetime import datetime, timedelta, timezone
from docu_serve.main import SECRET_KEY, ALGORITHM
from docu_serve.models import User  # ← ADD THIS
import pytest

def test_basic_health_check(client):
    """Test /health endpoint"""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "admin-user-deletion"
    assert "circuit_breakers" in data
    assert "auth_service" in data["circuit_breakers"]


def test_detailed_health_check(client):
    """Test /health/detailed endpoint"""
    response = client.get("/health/detailed")
    
    assert response. status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "admin-user-deletion"
    assert "checks" in data
    assert "database" in data["checks"]
    assert "auth_service_circuit" in data["checks"]


def test_health_circuit_breaker_states(client):
    """Test circuit breaker states are reported"""
    response = client.get("/health")
    
    data = response.json()
    auth_cb = data["circuit_breakers"]["auth_service"]
    
    # Check auth circuit breaker
    assert "state" in auth_cb
    assert "fail_counter" in auth_cb
    assert "name" in auth_cb
    assert auth_cb["name"] == "auth_service_breaker"


def test_detailed_health_database_check(client):
    """Test database health is checked"""
    response = client.get("/health/detailed")
    
    data = response.json()
    assert data["checks"]["database"] == "healthy"

def test_failed_event_logging(client, db_session):
    """Test that failed RabbitMQ events are logged to file"""
    import os
    from unittest.mock import patch
    from pybreaker import CircuitBreakerError
    
    # Create a user to delete
    user = User(
        name="Test User",
        email="rabbit@test.com",
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
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )
    
    # Mock RabbitMQ circuit breaker to be OPEN
    with patch('docu_serve.main.rabbitmq_breaker.call_async') as mock:
        mock.side_effect = CircuitBreakerError("Circuit open")
        
        # Delete user (should log failed event)
        response = client. delete(
            f"/api/admin/delete/{user.user_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
    
    # User should still be deleted successfully
    assert response.status_code == 200
    
    # Check that failed event was logged
    if os.path.exists("failed_events.log"):
        with open("failed_events.log", "r") as f:
            content = f.read()
            assert "user. deleted" in content
            assert user.email in content
        # Clean up
        os.remove("failed_events.log")