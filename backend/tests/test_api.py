import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.config.settings import settings

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "Upstox Trading Bot API"

def test_health_check():
    # Mock DB and API checks to be fast
    with pytest.MonkeyPatch.context() as m:
        # We can mock the health_check function directly or its dependencies
        response = client.get("/health")
        assert response.status_code == 200
        assert "status" in response.json()

def test_ml_stats_endpoint():
    response = client.get("/api/v1/monitoring/ml-stats")
    # It might return 200 even if empty
    assert response.status_code == 200
    assert "total_samples" in response.json()
