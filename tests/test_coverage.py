# tests/test_coverage.py
"""Additional tests to improve code coverage"""

from fastapi.testclient import TestClient
from fastapi import HTTPException
from unittest.mock import patch, AsyncMock, MagicMock
from jose import jwt
from datetime import datetime, timedelta, timezone
from docu_serve.main import SECRET_KEY, ALGORITHM, get_rabbitmq_connection, _log_failed_event
from docu_serve.models import User
from pybreaker import CircuitBreakerError
import pytest
import asyncio
import os
import json


def test_rabbitmq_connection_retry_success(client):
    """Test RabbitMQ connection with retry logic"""
    async def test_async():
        with patch('docu_serve.main.aio_pika.connect_robust') as mock_connect:
            mock_connection = AsyncMock()
            mock_connect.return_value = mock_connection
            
            connection = await get_rabbitmq_connection()
            assert connection == mock_connection
            mock_connect.assert_called_once()
    
    asyncio.run(test_async())


def test_rabbitmq_connection_retry_failure(client):
    """Test RabbitMQ connection fails after retries"""
    async def test_async():
        with patch('docu_serve.main.aio_pika.connect_robust') as mock_connect:
            mock_connect.side_effect = Exception("Connection failed")
            
            with pytest.raises(Exception, match="Connection failed"):
                await get_rabbitmq_connection()
            
            # Should retry 5 times
            assert mock_connect.call_count == 5
    
    asyncio.run(test_async())


def test_rabbitmq_connection_retry_eventual_success(client):
    """Test RabbitMQ connection succeeds after retries"""
    async def test_async():
        with patch('docu_serve.main.aio_pika.connect_robust') as mock_connect:
            with patch('docu_serve.main.asyncio.sleep', new_callable=AsyncMock):
                mock_connection = AsyncMock()
                # Fail twice, then succeed
                mock_connect.side_effect = [
                    Exception("Failed 1"),
                    Exception("Failed 2"),
                    mock_connection
                ]
                
                connection = await get_rabbitmq_connection()
                assert connection == mock_connection
                assert mock_connect.call_count == 3
    
    asyncio.run(test_async())


def test_log_failed_event():
    """Test logging failed events to file"""
    event_type = "test.event"
    payload = {"test": "data", "user_id": 123}
    
    # Clean up before test
    if os.path.exists("failed_events.log"):
        os.remove("failed_events.log")
    
    _log_failed_event(event_type, payload)
    
    # Verify file was created and contains data
    assert os.path.exists("failed_events.log")
    with open("failed_events.log", "r") as f:
        content = f.read()
        assert "test.event" in content
        assert "test" in content
        assert "123" in content
    
    # Clean up
    os.remove("failed_events.log")


def test_patch_user_database_error(client, db_session):
    """Test patch user handles database errors"""
    from sqlalchemy.exc import IntegrityError
    
    # Create two users with different emails
    user1 = User(
        name="Test 1",
        email="unique1@test.com",
        age=25,
        hashed_password="hash",
        role="user"
    )
    user2 = User(
        name="Test 2",
        email="unique2@test.com",
        age=30,
        hashed_password="hash",
        role="user"
    )
    db_session.add(user1)
    db_session.add(user2)
    db_session.commit()
    db_session.refresh(user2)
    user2_id = user2.user_id
    
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
    
    # Try to update user2's email to user1's email (duplicate)
    response = client.patch(
        f"/api/admin/users/{user2_id}",
        json={"email": "unique1@test.com"},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Should return 409 for duplicate email
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


def test_detailed_health_database_error():
    """Test detailed health check when database fails"""
    from docu_serve.main import app, get_db
    from sqlalchemy.exc import OperationalError
    from fastapi.testclient import TestClient
    
    # Create a generator that raises an exception
    def override_failing_db():
        raise OperationalError("Database connection failed", None, None)
        yield  # This line won't be reached but is needed for generator syntax
    
    # Store original override
    original_override = app.dependency_overrides.get(get_db)
    
    # Override get_db to raise an exception
    app.dependency_overrides[get_db] = override_failing_db
    
    try:
        test_client = TestClient(app)
        response = test_client.get("/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "unhealthy" in data["checks"]["database"]
    finally:
        # Restore original override
        if original_override:
            app.dependency_overrides[get_db] = original_override
        else:
            app.dependency_overrides.pop(get_db, None)


def test_login_circuit_breaker_error(client):
    """Test login when circuit breaker is open"""
    from docu_serve.main import auth_breaker
    
    # Mock the circuit breaker to raise CircuitBreakerError
    with patch.object(auth_breaker, 'call_async') as mock_call:
        mock_call.side_effect = CircuitBreakerError(auth_breaker)
        
        response = client.post(
            "/api/users/login",
            data={"username": "admin@test.com", "password": "password"}
        )
        
        assert response.status_code == 503
        assert "unavailable" in response.json()["detail"].lower()


def test_login_unexpected_error(client):
    """Test login handles unexpected errors"""
    from docu_serve.main import auth_breaker
    
    # Mock the circuit breaker to raise unexpected error
    with patch.object(auth_breaker, 'call_async') as mock_call:
        mock_call.side_effect = RuntimeError("Unexpected error")
        
        response = client.post(
            "/api/users/login",
            data={"username": "admin@test.com", "password": "password"}
        )
        
        assert response.status_code == 500
        assert "unexpected error" in response.json()["detail"].lower()


def test_call_auth_service_invalid_credentials():
    """Test call_auth_service with invalid credentials"""
    from docu_serve.main import call_auth_service
    
    async def test_async():
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 401
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            with pytest.raises(HTTPException) as exc_info:
                await call_auth_service("invalid@test.com", "wrongpass")
            
            assert exc_info.value.status_code == 401
    
    asyncio.run(test_async())


def test_publish_event_circuit_breaker_open(client, db_session):
    """Test event publishing when circuit breaker is open"""
    user = User(
        name="Test",
        email="cbtest@test.com",
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
    
    # Mock the circuit breaker to be open
    with patch('docu_serve.main.rabbitmq_breaker.call_async') as mock_breaker:
        mock_breaker.side_effect = CircuitBreakerError("Circuit is open")
        
        # Clean up log file before test
        if os.path.exists("failed_events.log"):
            os.remove("failed_events.log")
        
        response = client.delete(
            f"/api/admin/delete/{user.user_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Should still succeed
        assert response.status_code == 200
        
        # Check that event was logged
        assert os.path.exists("failed_events.log")
        with open("failed_events.log", "r") as f:
            content = f.read()
            assert "user.deleted" in content
        
        # Clean up
        os.remove("failed_events.log")


def test_patch_user_with_update_publishes_event(client, db_session):
    """Test that patching a user publishes an event"""
    user = User(
        name="Original",
        email="patchevent@test.com",
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
    
    with patch('docu_serve.main.publish_event', new_callable=AsyncMock) as mock_publish:
        response = client.patch(
            f"/api/admin/users/{user.user_id}",
            json={"name": "Updated Name"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        
        # Verify publish_event was called
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert call_args[0][0] == "user.updated"
        assert call_args[0][1]["email"] == "patchevent@test.com"
        assert call_args[0][1]["name"] == "Updated Name"
