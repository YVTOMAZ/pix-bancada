from fastapi.testclient import TestClient

from pix_bancada.brcode import gerar_brcode
from pix_bancada.main import app


def test_fluxo_pagamento() -> None:
    bc = gerar_brcode("12345678901", valor="10.50", txid="txp")
    with TestClient(app) as c:
        c.put(
            "/cob/txp",
            json={
                "chave": "12345678901",
                "valor": {"original": "10.50"},
                "calendario": {"expiracao": 3600},
            },
        )
        r = c.post("/_bancada/banco/pagar", json={"pixCopiaECola": bc})
        assert r.status_code == 200
        e2e = r.json()["endToEndId"]
        assert c.get(f"/pix/{e2e}").status_code == 200
        # duplicado recusado
        r2 = c.post("/_bancada/banco/pagar", json={"pixCopiaECola": bc})
        assert r2.status_code == 409


def test_crc_invalido() -> None:
    with TestClient(app) as c:
        r = c.post("/_bancada/banco/pagar", json={"pixCopiaECola": "000201..."})
        assert r.status_code in (400, 422)
