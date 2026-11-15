from fastapi.testclient import TestClient

from pix_bancada import __version__
from pix_bancada.main import app


def test_saude() -> None:
    client = TestClient(app)
    r = client.get("/saude")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["versao"] == __version__
