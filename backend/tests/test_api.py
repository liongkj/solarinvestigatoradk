"""Basic API endpoint tests"""


def test_root_endpoint(test_client):
    """Test the root endpoint"""
    response = test_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert "status" in data
    assert data["status"] == "running"


def test_health_check(test_client):
    """Test the health check endpoint"""
    response = test_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert "timestamp" in data
    assert data["status"] == "healthy"
