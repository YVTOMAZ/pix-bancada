"""Webhooks e caos controlavel."""

import json
import random
from datetime import timedelta

import aiosqlite
import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from pix_bancada.erros import problema
from pix_bancada.estado import caminho_banco, relogio

router = APIRouter()

# Cenario global
cenario: dict[str, object] = {
    "duplicar": False,
    "atrasar_segundos": 0,
    "perder": False,
    "fora_de_ordem": False,
    "erro_5xx": False,
    "semente": 42,
}


class WebhookBody(BaseModel):
    webhookUrl: str


class CenarioBody(BaseModel):
    duplicar: bool | None = None
    atrasar_segundos: int | None = None
    perder: bool | None = None
    fora_de_ordem: bool | None = None
    erro_5xx: bool | None = None
    semente: int | None = None


class RelogioBody(BaseModel):
    segundos: int = 0
    minutos: int = 0
    horas: int = 0
    dias: int = 0


@router.put("/webhook/{chave}")
async def registrar_webhook(chave: str, body: WebhookBody) -> dict[str, object]:
    db = await aiosqlite.connect(caminho_banco)
    try:
        await db.execute(
            (
                "INSERT INTO webhooks (chave, url) VALUES (?,?)"
                " ON CONFLICT(chave) DO UPDATE SET url=excluded.url"
            ),
            (chave, body.webhookUrl),
        )
        await db.commit()
    finally:
        await db.close()
    return {"chave": chave, "webhookUrl": body.webhookUrl}


@router.get("/webhook/{chave}")
async def consultar_webhook(chave: str) -> dict[str, object]:
    db = await aiosqlite.connect(caminho_banco)
    db.row_factory = aiosqlite.Row
    try:
        async with db.execute("SELECT * FROM webhooks WHERE chave=?", (chave,)) as cur:
            row = await cur.fetchone()
    finally:
        await db.close()
    if row is None:
        raise problema(404, "Nao encontrado", f"Webhook {chave} nao encontrado", "https://pix-bancada.local/problems/not-found")
    return {
        "chave": row["chave"],
        "webhookUrl": row["url"],
        "cnpj": "00000000000191",
        "criacao": relogio.agora().isoformat(),
    }


@router.delete("/webhook/{chave}")
async def remover_webhook(chave: str) -> dict[str, object]:
    db = await aiosqlite.connect(caminho_banco)
    try:
        await db.execute("DELETE FROM webhooks WHERE chave=?", (chave,))
        await db.commit()
    finally:
        await db.close()
    return {"chave": chave, "removido": True}


async def enfileirar_entrega(chave: str, e2eid: str, valor: str, txid: str | None = None) -> None:
    db = await aiosqlite.connect(caminho_banco)
    try:
        async with db.execute("SELECT url FROM webhooks WHERE chave=?", (chave,)) as cur:
            row = await cur.fetchone()
        if row is None:
            return
        url = row[0]
        _ = url
        payload = {
            "pix": [
                {
                    "endToEndId": e2eid,
                    "txid": txid,
                    "valor": valor,
                    "horario": relogio.agora().isoformat(),
                }
            ]
        }
        # txid sera preenchido pelo chamador? manter simples
        atraso = int(str(cenario.get("atrasar_segundos", 0) or 0))
        proxima = relogio.agora() + timedelta(seconds=atraso)
        await db.execute(
            (
                "INSERT INTO entregas_webhook "
                "(chave, payload, status, tentativas, proxima_em) VALUES (?,?,?,?,?)"
            ),
            (chave, json.dumps(payload), None, 0, proxima.isoformat()),
        )
        # guardar url no payload? armazenar em tabela separada nao; usar webhooks lookup
        await db.commit()
    finally:
        await db.close()


async def processar_entregas() -> int:
    processadas = 0
    db = await aiosqlite.connect(caminho_banco)
    db.row_factory = aiosqlite.Row
    try:
        async with db.execute(
            "SELECT * FROM entregas_webhook WHERE proxima_em <= ? AND status IS NULL",
            (relogio.agora().isoformat(),),
        ) as cur:
            rows = list(await cur.fetchall())
        if bool(cenario.get("fora_de_ordem", False)):
            random.Random(int(str(cenario.get("semente", 42)))).shuffle(rows)
        for row in rows:
            # lookup url
            async with db.execute(
                "SELECT url FROM webhooks WHERE chave=?",
                (row["chave"],),
            ) as cur2:
                wrow = await cur2.fetchone()
            if wrow is None:
                continue
            url = wrow["url"]
            payload = json.loads(row["payload"])
            tentativas = row["tentativas"] + 1
            status_code: int | None = None
            if bool(cenario.get("perder", False)):
                status_code = None
            elif bool(cenario.get("erro_5xx", False)):
                status_code = 500
            else:
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.post(url, json=payload)
                        status_code = resp.status_code
                except Exception:
                    status_code = 0
            # sucesso se 2xx
            sucesso = status_code is not None and 200 <= status_code < 300
            if sucesso:
                await db.execute(
                    "UPDATE entregas_webhook "
                    "SET status=?, tentativas=?, ultimo_status_http=? WHERE id=?",
                    (status_code, tentativas, status_code, row["id"]),
                )
                processadas += 1
            else:
                # reagendar com backoff; manter pendente (status NULL) para retry
                proxima = relogio.agora() + timedelta(seconds=5)
                http_code = status_code if status_code is not None else 0
                await db.execute(
                    "UPDATE entregas_webhook "
                    "SET status=NULL, tentativas=?, proxima_em=?, ultimo_status_http=? WHERE id=?",
                    (
                        tentativas,
                        proxima.isoformat(),
                        http_code,
                        row["id"],
                    ),
                )
            # duplicar: enfileirar copia
            if bool(cenario.get("duplicar", False)):
                await db.execute(
                    (
                        "INSERT INTO entregas_webhook "
                        "(chave, payload, status, tentativas, proxima_em) VALUES (?,?,?,?,?)"
                    ),
                    (row["chave"], row["payload"], None, 0, relogio.agora().isoformat()),
                )
        await db.commit()
    finally:
        await db.close()
    return processadas


@router.post("/_bancada/relogio/avancar")
async def avancar_relogio(body: RelogioBody) -> dict[str, object]:
    relogio.avancar(segundos=body.segundos, minutos=body.minutos, horas=body.horas, dias=body.dias)
    processadas = await processar_entregas()
    return {"agora": relogio.agora().isoformat(), "entregas_processadas": processadas}


@router.get("/_bancada/cenarios")
async def obter_cenario() -> dict[str, object]:
    return dict(cenario)


@router.post("/_bancada/cenarios")
async def definir_cenario(body: CenarioBody) -> dict[str, object]:
    if body.duplicar is not None:
        cenario["duplicar"] = body.duplicar
    if body.atrasar_segundos is not None:
        cenario["atrasar_segundos"] = body.atrasar_segundos
    if body.perder is not None:
        cenario["perder"] = body.perder
    if body.fora_de_ordem is not None:
        cenario["fora_de_ordem"] = body.fora_de_ordem
    if body.erro_5xx is not None:
        cenario["erro_5xx"] = body.erro_5xx
    if body.semente is not None:
        cenario["semente"] = body.semente
    return dict(cenario)
