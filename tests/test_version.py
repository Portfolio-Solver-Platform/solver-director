from src.config import Config


def test_version_endpoint(client):
    """Test the version endpoint"""
    response = client.get("/version")
    assert response.status_code == 200
    data = response.get_json()

    assert data["service"] == Config.App.NAME
    assert data["version"] == Config.App.VERSION
    assert data["api_version"] == Config.Api.VERSION
