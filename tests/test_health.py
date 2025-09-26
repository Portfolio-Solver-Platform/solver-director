def test_health_endpoint(client):
    """Test the health endpoint"""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_ready_endpoint(client, monkeypatch):
    """Test the ready endpoint"""
    # fake_response = assume_keycloak_ready_state(monkeypatch, True)

    response = client.get("/readyz")
    # fake_response.json.assert_called_once()
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"


# def assume_keycloak_ready_state(monkeypatch, is_ready: bool):
#     fake_response = Mock()
#     fake_response.json.return_value = {"status": "UP" if is_ready else "DOWN"}

#     monkeypatch.setattr(
#         "src.blueprints.health.try_get_keycloak_ready_response",
#         lambda: fake_response,
#     )

#     return fake_response
