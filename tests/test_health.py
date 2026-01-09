# tests/test_health.py
"""Tests for health check endpoints"""

from fastapi.testclient import TestClient
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