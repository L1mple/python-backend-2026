from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_failed_request_rolls_back_flushed_item(app: FastAPI, client: TestClient, monkeypatch):
    def fail_commit(session):
        raise RuntimeError("Commit failed")

    with monkeypatch.context() as patch:
        patch.setattr(app.state.session_factory.class_, "commit", fail_commit)
        with TestClient(app, raise_server_exceptions=False) as failing_client:
            response = failing_client.post("/item", json={"name": "Rolled back", "price": 10})

    assert response.status_code == 500
    assert client.get("/item").json() == []
    response = client.post("/item", json={"name": "Committed", "price": 20})
    assert response.status_code == 201
    assert client.get("/item").json() == [response.json()]
