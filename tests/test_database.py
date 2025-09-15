import pytest

try:
    from app import app  # Works in CI (Docker container)
except ImportError:
    from src.app import app  # Works locally


@pytest.fixture
def client():
    """Flask test client"""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_root_endpoint(client):
    """Test the root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["service"] == "flask-helm-skaffold"
