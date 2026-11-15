import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from openapi_core import OpenAPI
from openapi_core.configurations import Config
from openapi_core.testing.requests import MockRequest
from openapi_core.testing.responses import MockResponse

from pix_bancada.brcode import gerar_brcode
from pix_bancada.main import app


def test_fetch_spec_baixa_e_hash_bate() -> None:
    r = subprocess.run([sys.executable, "scripts/fetch_spec.py"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    p = Path(".cache/openapi.yaml")
    assert p.exists()
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    assert h == "cf191845044a5edd38c00b0e099924e8daceacfe53502abaa6a5b238bed41eb4"


def test_cache_gitignored() -> None:
    gitignore = Path(".gitignore").read_text()
    assert ".cache/" in gitignore or ".cache" in gitignore


def test_hash_divergente_falha() -> None:
    spec_path = Path("scripts/fetch_spec.py")
    src = spec_path.read_text()
    # carregar modulo com hash alterado
    src_mod = src.replace(
        'PINNED_SHA256 = "cf191845044a5edd38c00b0e099924e8daceacfe53502abaa6a5b238bed41eb4"',
        'PINNED_SHA256 = "0000000000000000000000000000000000000000000000000000000000000000"',
    )
    ns: dict[str, object] = {}
    exec(compile(src_mod, "fetch_spec_mod", "exec"), ns)
    # chamar main com cache ja existente nao re-baixa? main sempre baixa. Rodar.
    main_fn = ns["main"]
    assert callable(main_fn)
    rc = main_fn()
    assert rc == 1


def _spec() -> OpenAPI:
    return OpenAPI.from_file_path(".cache/openapi.yaml", config=Config(spec_validator_cls=None))


TXID = "12345678901234567890123456"


def _req(
    method: str,
    path: str,
    path_pattern: str,
    view_args: dict[str, str] | None = None,
    body: Any = None,
) -> MockRequest:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    return MockRequest(
        "https://pix.example.com",
        method,
        path,
        path_pattern=path_pattern,
        view_args=view_args or {},
        data=data,
        headers=headers,
    )


def test_contract_cob_put_get() -> None:
    spec = _spec()
    body = {
        "chave": "12345678901",
        "valor": {"original": "10.50"},
        "calendario": {"expiracao": 3600},
    }
    req = _req("put", f"/api/cob/{TXID}", "/api/cob/{txid}", {"txid": TXID}, body)
    assert list(spec.iter_request_errors(req)) == []
    with TestClient(app) as c:
        r = c.put(f"/cob/{TXID}", json=body)
        assert r.status_code == 201
    resp = MockResponse(r.content, status_code=r.status_code, headers=dict(r.headers))
    assert list(spec.iter_response_errors(req, resp)) == []

    req2 = _req("get", f"/api/cob/{TXID}", "/api/cob/{txid}", {"txid": TXID})
    with TestClient(app) as c:
        r2 = c.get(f"/cob/{TXID}")
        assert r2.status_code == 200
    resp2 = MockResponse(r2.content, status_code=r2.status_code, headers=dict(r2.headers))
    assert list(spec.iter_response_errors(req2, resp2)) == []


def test_contract_pix_get() -> None:
    spec = _spec()
    with TestClient(app) as c:
        c.put(
            f"/cob/{TXID}",
            json={
                "chave": "12345678901",
                "valor": {"original": "10.50"},
                "calendario": {"expiracao": 3600},
            },
        )
        bc = gerar_brcode("12345678901", valor="10.50", txid=TXID)
        pay = c.post("/_bancada/banco/pagar", json={"pixCopiaECola": bc})
        assert pay.status_code == 200
        e2e = pay.json()["endToEndId"]
        req = _req("get", f"/api/pix/{e2e}", "/api/pix/{e2eid}", {"e2eid": e2e})
        assert list(spec.iter_request_errors(req)) == []
        r = c.get(f"/pix/{e2e}")
        assert r.status_code == 200
        resp = MockResponse(r.content, status_code=r.status_code, headers=dict(r.headers))
        assert list(spec.iter_response_errors(req, resp)) == []


def test_contract_webhook_put_get() -> None:
    spec = _spec()
    body = {"webhookUrl": "https://example.com/hook"}
    chave = "12345678901"
    req = _req("put", f"/api/webhook/{chave}", "/api/webhook/{chave}", {"chave": chave}, body)
    assert list(spec.iter_request_errors(req)) == []
    with TestClient(app) as c:
        r = c.put(f"/webhook/{chave}", json=body)
        assert r.status_code == 200
    # PUT response has no content schema; skip response validation

    req2 = _req("get", f"/api/webhook/{chave}", "/api/webhook/{chave}", {"chave": chave})
    assert list(spec.iter_request_errors(req2)) == []
    with TestClient(app) as c:
        r2 = c.get(f"/webhook/{chave}")
        assert r2.status_code == 200
    resp2 = MockResponse(r2.content, status_code=r2.status_code, headers=dict(r2.headers))
    assert list(spec.iter_response_errors(req2, resp2)) == []


def test_contract_loc_get() -> None:
    spec = _spec()
    prefix = TXID[:8]
    with TestClient(app) as c:
        c.put(
            f"/cob/{TXID}",
            json={
                "chave": "12345678901",
                "valor": {"original": "10.50"},
                "calendario": {"expiracao": 3600},
            },
        )
        req = _req("get", f"/api/loc/{prefix}", "/api/loc/{id}", {"id": prefix})
        r = c.get(f"/loc/{prefix}")
        assert r.status_code == 200
        resp = MockResponse(r.content, status_code=r.status_code, headers=dict(r.headers))
        assert list(spec.iter_response_errors(req, resp)) == []


def test_contract_cob_post() -> None:
    spec = _spec()
    body = {
        "chave": "12345678901",
        "valor": {"original": "10.50"},
        "calendario": {"expiracao": 3600},
    }
    req = _req("post", "/api/cob", "/api/cob", {}, body)
    assert list(spec.iter_request_errors(req)) == []
    with TestClient(app) as c:
        r = c.post("/cob", json=body)
        assert r.status_code == 201
    resp = MockResponse(r.content, status_code=r.status_code, headers=dict(r.headers))
    assert list(spec.iter_response_errors(req, resp)) == []


def test_contract_cob_patch() -> None:
    spec = _spec()
    with TestClient(app) as c:
        c.put(
            f"/cob/{TXID}",
            json={
                "chave": "12345678901",
                "valor": {"original": "10.50"},
                "calendario": {"expiracao": 3600},
            },
        )
    body = {"valor": {"original": "20.00"}}
    req = _req("patch", f"/api/cob/{TXID}", "/api/cob/{txid}", {"txid": TXID}, body)
    assert list(spec.iter_request_errors(req)) == []
    with TestClient(app) as c:
        r = c.patch(f"/cob/{TXID}", json=body)
        assert r.status_code == 200
    resp = MockResponse(r.content, status_code=r.status_code, headers=dict(r.headers))
    assert list(spec.iter_response_errors(req, resp)) == []
