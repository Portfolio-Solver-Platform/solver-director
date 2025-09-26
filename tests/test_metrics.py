def test_metrics_endpoint(client):
    """Test the metrics endpoint"""
    response = client.get("/metrics")
    assert response.status_code == 200
    # Prometheus metrics are plain text
    assert "text/plain" in response.headers["content-type"]

    data = response.text

    assert data.startswith("# HELP")
    # Should have both process and python data
    assert "process_" in data and "python_" in data
