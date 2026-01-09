# tests/test_login.py
"""Tests for login proxy endpoint"""

from fastapi.testclient import TestClient
from unittest.mock import patch
import pytest
from pybreaker import CircuitBreakerError


def test_login_proxy_circuit_breaker_open(client):
    """Test login when circuit breaker is open"""
    # Mock the circuit breaker's call_async to raise CircuitBreakerError
    with patch('docu_serve.main.auth_breaker.call_async') as mock:
        mock.side_effect = CircuitBreakerError("Circuit breaker is open")
        
        response = client.post(
            "/api/users/login",
            data={"username": "test@example.com", "password":  "test"}
        )
    
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"]. lower()


def test_login_proxy_missing_credentials(client):
    """Test login without credentials"""
    response = client.post("/api/users/login")
    
    # FastAPI will return 422 for missing required fields
    assert response.status_code == 422