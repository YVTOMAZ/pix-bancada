import asyncio
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from pix_bancada.db import inicializar_banco
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


def _criar(c: TestClient, txid: str, expiracao: int = 3600) -> dict[str, object]:
    r = c.put(
        f"/cob/{txid}",
        json={
            "chave": "12345678901",
            "valor": {"original": "10.50"},
            "calendario": {"expiracao": expiracao},
        },
    )
    assert r.status_code == 201
    return r.json()  # type: ignore[no-any-return]


def test_patch_status_nao_permitido_rejeitado() -> None:
    with TestClient(app) as c:
        _criar(c, "txst1")
        for status in ("CONCLUIDA", "ATIVA", "REMOVIDA_PELO_PSP", "XYZ"):
            r = c.patch("/cob/txst1", json={"status": status})
            assert r.status_code == 400, status
            assert r.json()["detail"]["type"].endswith("/problems/invalid-state")
        atual = c.get("/cob/txst1").json()
        assert atual["status"] == "ATIVA"
        assert atual["revisao"] == 0


def test_patch_remocao_pelo_recebedor() -> None:
    with TestClient(app) as c:
        _criar(c, "txst2")
        r = c.patch("/cob/txst2", json={"status": "REMOVIDA_PELO_USUARIO_RECEBEDOR"})
        assert r.status_code == 200
        assert r.json()["status"] == "REMOVIDA_PELO_USUARIO_RECEBEDOR"
        assert r.json()["revisao"] == 1


def test_revisao_incrementa_por_alteracao() -> None:
    with TestClient(app) as c:
        assert _criar(c, "txrev")["revisao"] == 0
        assert c.patch("/cob/txrev", json={"valor": {"original": "11.00"}}).json()["revisao"] == 1
        r = c.patch("/cob/txrev", json={"calendario": {"expiracao": 7200}})
        assert r.json()["revisao"] == 2
        # valor + calendario na mesma requisicao: um unico incremento
        r = c.patch(
            "/cob/txrev",
            json={"valor": {"original": "12.00"}, "calendario": {"expiracao": 100}},
        )
        assert r.json()["revisao"] == 3
        # sem mudanca real e so loc: nao incrementa
        assert c.patch("/cob/txrev", json={"valor": {"original": "12.00"}}).json()["revisao"] == 3
        assert c.patch("/cob/txrev", json={"loc": {"id": 1}}).json()["revisao"] == 3
        assert c.get("/cob/txrev").json()["revisao"] == 3


def test_put_em_txid_existente_incrementa_revisao() -> None:
    with TestClient(app) as c:
        _criar(c, "txup")
        assert _criar(c, "txup")["revisao"] == 1


def test_patch_legado_preserva_expiracao() -> None:
    with TestClient(app) as c:
        _criar(c, "txleg", expiracao=3600)
        r = c.patch("/cob/txleg", json={"valor": "12.00"})
        assert r.status_code == 200
        assert r.headers["deprecation"] == "true"
        assert r.json()["valor"]["original"] == "12.00"
        assert r.json()["calendario"]["expiracao"] == 3600


def test_patch_valor_regenera_brcode() -> None:
    with TestClient(app) as c:
        antes = _criar(c, "txbr")["pixCopiaECola"]
        depois = c.patch("/cob/txbr", json={"valor": {"original": "12.00"}}).json()["pixCopiaECola"]
        assert depois != antes
        assert "540512.00" in depois
        assert "540510.50" in antes


def test_put_sem_calendario_rejeitado() -> None:
    with TestClient(app) as c:
        r = c.put("/cob/txsc", json={"chave": "12345678901", "valor": {"original": "10.50"}})
        assert r.status_code in (400, 422)


def test_put_sem_valor_original_rejeitado() -> None:
    with TestClient(app) as c:
        r = c.put(
            "/cob/txsv",
            json={"chave": "12345678901", "valor": {}, "calendario": {"expiracao": 60}},
        )
        assert r.status_code in (400, 422)


def test_migracao_adiciona_revisao_idempotente(tmp_path: Path) -> None:
    db = tmp_path / "antigo.db"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE cobrancas (txid TEXT PRIMARY KEY, chave TEXT NOT NULL, valor TEXT,"
        " status TEXT NOT NULL, expiracao_em TEXT, criado_em TEXT NOT NULL, brcode TEXT)"
    )
    con.execute(
        "INSERT INTO cobrancas (txid, chave, status, criado_em) VALUES ('a','k','ATIVA','x')"
    )
    con.commit()
    con.close()
    for _ in range(2):
        asyncio.run(inicializar_banco(str(db)))
    con = sqlite3.connect(db)
    assert con.execute("SELECT revisao FROM cobrancas WHERE txid='a'").fetchone() == (0,)
    con.close()
