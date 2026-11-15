import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fastapi.testclient import TestClient

from pix_bancada.brcode import gerar_brcode
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

def _receiver() -> tuple[
    ThreadingHTTPServer,
    threading.Thread,
    list[dict[str, object]],
    threading.Lock,
    int,
]:
    received: list[dict[str, object]] = []
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length else b""
            try:
                data = json.loads(body) if body else {}
            except Exception:
                data = {"raw": body.decode("utf-8", "replace")}
            with lock:
                received.append(data)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args: object) -> None:
            return

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, thread, received, lock, port


def test_webhook_retry() -> None:
    httpd, thread, received, lock, port = _receiver()
    try:
        with TestClient(app) as c:
            url = f"http://127.0.0.1:{port}/hook"
            c.put("/webhook/minhachave", json={"webhookUrl": url})
            bc = gerar_brcode("minhachave", valor="10.50", txid="txretry")
            c.put("/cob/txretry", json={"chave": "minhachave", "valor": "10.50"})
            c.post("/_bancada/cenarios", json={"erro_5xx": True})
            rpay = c.post("/_bancada/banco/pagar", json={"pixCopiaECola": bc})
            assert rpay.status_code == 200
            r1 = c.post("/_bancada/relogio/avancar", json={"segundos": 0})
            assert r1.json()["entregas_processadas"] == 0
            c.post("/_bancada/cenarios", json={"erro_5xx": False})
            r2 = c.post("/_bancada/relogio/avancar", json={"segundos": 5})
            assert r2.json()["entregas_processadas"] == 1
        with lock:
            assert len(received) == 1
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_webhook_payload_txid() -> None:
    httpd, thread, received, lock, port = _receiver()
    try:
        with TestClient(app) as c:
            url = f"http://127.0.0.1:{port}/hook"
            c.put("/webhook/chave", json={"webhookUrl": url})
            bc = gerar_brcode("chave", valor="10.50", txid="txpayload")
            c.put("/cob/txpayload", json={"chave": "chave", "valor": "10.50"})
            c.post("/_bancada/banco/pagar", json={"pixCopiaECola": bc})
            c.post("/_bancada/relogio/avancar", json={"segundos": 0})
        with lock:
            assert len(received) == 1
            assert received[0]["pix"][0]["txid"] == "txpayload"  # type: ignore[index]
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_webhook_duplicar() -> None:
    httpd, thread, received, lock, port = _receiver()
    try:
        with TestClient(app) as c:
            url = f"http://127.0.0.1:{port}/hook"
            c.put("/webhook/chave", json={"webhookUrl": url})
            bc = gerar_brcode("chave", valor="10.50", txid="txdup")
            c.put("/cob/txdup", json={"chave": "chave", "valor": "10.50"})
            c.post("/_bancada/cenarios", json={"duplicar": True})
            c.post("/_bancada/banco/pagar", json={"pixCopiaECola": bc})
            c.post("/_bancada/relogio/avancar", json={"segundos": 0})
            c.post("/_bancada/relogio/avancar", json={"segundos": 0})
        with lock:
            assert len(received) == 2
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_webhook_perder() -> None:
    httpd, thread, received, lock, port = _receiver()
    try:
        with TestClient(app) as c:
            url = f"http://127.0.0.1:{port}/hook"
            c.put("/webhook/chave", json={"webhookUrl": url})
            bc = gerar_brcode("chave", valor="10.50", txid="txperder")
            c.put("/cob/txperder", json={"chave": "chave", "valor": "10.50"})
            c.post("/_bancada/cenarios", json={"perder": True})
            c.post("/_bancada/banco/pagar", json={"pixCopiaECola": bc})
            r = c.post("/_bancada/relogio/avancar", json={"segundos": 0})
            assert r.json()["entregas_processadas"] == 0
        with lock:
            assert len(received) == 0
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_webhook_atrasar() -> None:
    httpd, thread, received, lock, port = _receiver()
    try:
        with TestClient(app) as c:
            url = f"http://127.0.0.1:{port}/hook"
            c.put("/webhook/chave", json={"webhookUrl": url})
            bc = gerar_brcode("chave", valor="10.50", txid="txatraso")
            c.put("/cob/txatraso", json={"chave": "chave", "valor": "10.50"})
            c.post("/_bancada/cenarios", json={"atrasar_segundos": 5})
            c.post("/_bancada/banco/pagar", json={"pixCopiaECola": bc})
            r1 = c.post("/_bancada/relogio/avancar", json={"segundos": 0})
            assert r1.json()["entregas_processadas"] == 0
            r2 = c.post("/_bancada/relogio/avancar", json={"segundos": 5})
            assert r2.json()["entregas_processadas"] == 1
        with lock:
            assert len(received) == 1
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_webhook_fora_de_ordem() -> None:
    httpd, thread, received, lock, port = _receiver()
    try:
        with TestClient(app) as c:
            url = f"http://127.0.0.1:{port}/hook"
            c.put("/webhook/chave", json={"webhookUrl": url})
            for tx in ("txo1", "txo2"):
                bc = gerar_brcode("chave", valor="10.50", txid=tx)
                c.put(f"/cob/{tx}", json={"chave": "chave", "valor": "10.50"})
            c.post("/_bancada/cenarios", json={"fora_de_ordem": True, "semente": 1})
            for tx in ("txo1", "txo2"):
                bc = gerar_brcode("chave", valor="10.50", txid=tx)
                c.post("/_bancada/banco/pagar", json={"pixCopiaECola": bc})
            c.post("/_bancada/relogio/avancar", json={"segundos": 0})
        with lock:
            assert len(received) == 2
            txids = [r["pix"][0]["txid"] for r in received]  # type: ignore[index]
            assert sorted(txids) == ["txo1", "txo2"]
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_webhook_erro_5xx_retry() -> None:
    httpd, thread, received, lock, port = _receiver()
    try:
        with TestClient(app) as c:
            url = f"http://127.0.0.1:{port}/hook"
            c.put("/webhook/chave", json={"webhookUrl": url})
            bc = gerar_brcode("chave", valor="10.50", txid="tx5xx")
            c.put("/cob/tx5xx", json={"chave": "chave", "valor": "10.50"})
            c.post("/_bancada/cenarios", json={"erro_5xx": True})
            c.post("/_bancada/banco/pagar", json={"pixCopiaECola": bc})
            r1 = c.post("/_bancada/relogio/avancar", json={"segundos": 0})
            assert r1.json()["entregas_processadas"] == 0
            c.post("/_bancada/cenarios", json={"erro_5xx": False})
            r2 = c.post("/_bancada/relogio/avancar", json={"segundos": 5})
            assert r2.json()["entregas_processadas"] == 1
        with lock:
            assert len(received) == 1
    finally:
        httpd.shutdown()
        httpd.server_close()
