from fastapi.testclient import TestClient

from pix_bancada.main import app


def test_saude() -> None:
    client = TestClient(app)
    r = client.get("/saude")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
