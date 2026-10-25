def test_metrics_endpoint(client):
    client.get("/item")
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "http_request" in resp.text