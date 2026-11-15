from fastapi.testclient import TestClient

from pix_bancada.main import app


def test_registro_webhook() -> None:
    with TestClient(app) as c:
        r = c.put("/webhook/chave1", json={"webhookUrl": "http://example.com/hook"})
        assert r.status_code == 200
        assert c.get("/webhook/chave1").status_code == 200
        assert c.delete("/webhook/chave1").status_code == 200


def test_cenario() -> None:
    with TestClient(app) as c:
        r = c.post("/_bancada/cenarios", json={"perder": True, "semente": 7})
        assert r.status_code == 200
        assert r.json()["perder"] is True
        assert c.get("/_bancada/cenarios").json()["semente"] == 7
