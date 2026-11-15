from fastapi.testclient import TestClient

from pix_bancada.main import app


def test_fluxo_cob() -> None:
    with TestClient(app) as c:
        r = c.put("/cob/tx1", json={"chave": "12345678901", "valor": "10.50"})
        assert r.status_code == 200
        assert r.json()["status"] == "ATIVA"
        assert r.json()["txid"] == "tx1"
        assert c.get("/cob/tx1").status_code == 200
        # expiracao por relogio: avancar nao testado aqui (sem acesso ao relogio global)
        r2 = c.put("/cob/tx2", json={"chave": "12345678901"})
        assert r2.status_code == 200
        assert c.get("/cob").status_code == 200
        # nao encontrado
        assert c.get("/cob/naoexiste").status_code == 404


def test_problema_formato() -> None:
    with TestClient(app) as c:
        r = c.get("/cob/naoexiste")
        assert r.status_code == 404
        body = r.json()["detail"]
        assert set(body.keys()) >= {"type", "title", "status", "detail"}
