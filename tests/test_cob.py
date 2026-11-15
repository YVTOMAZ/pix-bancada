from fastapi.testclient import TestClient

from pix_bancada.main import app


def test_fluxo_cob() -> None:
    with TestClient(app) as c:
        r = c.put(
            "/cob/tx1",
            json={
                "chave": "12345678901",
                "valor": {"original": "10.50"},
                "calendario": {"expiracao": 3600},
            },
        )
        assert r.status_code == 201
        assert r.json()["status"] == "ATIVA"
        assert r.json()["txid"] == "tx1"
        assert c.get("/cob/tx1").status_code == 200
        # expiracao por relogio: avancar nao testado aqui (sem acesso ao relogio global)
        r2 = c.put(
            "/cob/tx2",
            json={
                "chave": "12345678901",
                "valor": {"original": "10.50"},
                "calendario": {"expiracao": 3600},
            },
        )
        assert r2.status_code == 201
        assert c.get("/cob").status_code == 200
        # nao encontrado
        assert c.get("/cob/naoexiste").status_code == 404


def test_problema_formato() -> None:
    with TestClient(app) as c:
        r = c.get("/cob/naoexiste")
        assert r.status_code == 404
        body = r.json()["detail"]
        assert set(body.keys()) >= {"type", "title", "status", "detail"}


def test_expiracao_por_relogio() -> None:
    with TestClient(app) as c:
        r = c.put(
            "/cob/txe",
            json={
                "chave": "12345678901",
                "valor": {"original": "10.50"},
                "calendario": {"expiracao": 1},
            },
        )
        assert r.status_code == 201
        c.post("/_bancada/relogio/avancar", json={"segundos": 2})
        r2 = c.get("/cob/txe")
        assert r2.status_code == 200
        assert r2.json()["status"] == "REMOVIDA_PELO_PSP"


def test_listar_cob_filtros_periodo() -> None:
    with TestClient(app) as c:
        r0 = c.put(
            "/cob/coba",
            json={
                "chave": "12345678901",
                "valor": {"original": "10.50"},
                "calendario": {"expiracao": 3600},
            },
        )
        assert r0.status_code == 201
        criado_a = r0.json()["calendario"]["criacao"]
        c.post("/_bancada/relogio/avancar", json={"segundos": 10})
        r1 = c.put(
            "/cob/cobb",
            json={
                "chave": "12345678901",
                "valor": {"original": "10.50"},
                "calendario": {"expiracao": 3600},
            },
        )
        assert r1.status_code == 201
        r = c.get("/cob", params={"inicio": criado_a, "fim": criado_a})
        assert r.status_code == 200
        txids = [x["txid"] for x in r.json()["cobrancas"]]
        assert txids == ["coba"]


def test_cob_put_payload_oficial_201() -> None:
    with TestClient(app) as c:
        r = c.put(
            "/cob/txoficial",
            json={
                "chave": "12345678901",
                "valor": {"original": "10.50"},
                "calendario": {"expiracao": 60},
            },
        )
        assert r.status_code == 201
        assert r.json()["valor"]["original"] == "10.50"
        assert r.json()["calendario"]["expiracao"] == 60


def test_cob_post_payload_oficial_201() -> None:
    with TestClient(app) as c:
        r = c.post(
            "/cob",
            json={
                "chave": "12345678901",
                "valor": {"original": "10.50"},
                "calendario": {"expiracao": 60},
            },
        )
        assert r.status_code == 201
        assert r.json()["valor"]["original"] == "10.50"


def test_cob_patch_valor_objeto() -> None:
    with TestClient(app) as c:
        c.put(
            "/cob/txpatch",
            json={
                "chave": "12345678901",
                "valor": {"original": "10.50"},
                "calendario": {"expiracao": 3600},
            },
        )
        r = c.patch("/cob/txpatch", json={"valor": {"original": "20.00"}})
        assert r.status_code == 200
        assert r.json()["valor"]["original"] == "20.00"


def test_cob_valor_invalido_400_ou_422() -> None:
    with TestClient(app) as c:
        r = c.put(
            "/cob/txinv",
            json={
                "chave": "12345678901",
                "valor": {"original": "10.5"},
                "calendario": {"expiracao": 60},
            },
        )
        assert r.status_code in (400, 422)


def test_devedor_cpf_e_cnpj_juntos_rejeitado() -> None:
    with TestClient(app) as c:
        r = c.put(
            "/cob/txdev",
            json={
                "chave": "12345678901",
                "valor": {"original": "10.50"},
                "calendario": {"expiracao": 60},
                "devedor": {"cpf": "12345678901", "cnpj": "12345678901234", "nome": "X"},
            },
        )
        assert r.status_code in (400, 422)


def test_formato_plano_legado_aceito_com_deprecation() -> None:
    with TestClient(app) as c:
        r = c.put("/cob/txleg", json={"chave": "12345678901", "valor": "10.50", "expiracao": 60})
        assert r.status_code == 201
        assert r.headers.get("deprecation", "").lower() == "true"
