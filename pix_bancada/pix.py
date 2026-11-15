"""Banco ficticio e Pix recebido (devolucao)."""

from datetime import datetime

import aiosqlite
from fastapi import APIRouter
from pydantic import BaseModel

from pix_bancada.brcode import parse_brcode, validar_crc
from pix_bancada.erros import problema
from pix_bancada.estado import caminho_banco, relogio
from pix_bancada.ids import gerar_end_to_end_id
from pix_bancada.webhooks import enfileirar_entrega

router = APIRouter()


class PagarRequest(BaseModel):
    pixCopiaECola: str
    valor: str | None = None


def _txid_do_brcode(brcode: str) -> str | None:
    p = parse_brcode(brcode)
    adf = p.get("62")
    if not adf:
        return None
    # tag 05 dentro do adf
    i = 0
    n = len(adf)
    while i + 4 <= n:
        tag = adf[i : i + 2]
        try:
            length = int(adf[i + 2 : i + 4])
        except ValueError:
            break
        value = adf[i + 4 : i + 4 + length]
        if tag == "05":
            return value
        i += 4 + length
    return None


@router.post("/_bancada/banco/pagar")
async def pagar(body: PagarRequest) -> dict[str, object]:
    if not validar_crc(body.pixCopiaECola):
        raise problema(400, "CRC invalido", "BR Code com CRC invalido", "https://pix-bancada.local/problems/invalid-crc")
    txid = _txid_do_brcode(body.pixCopiaECola)
    if not txid:
        raise problema(400, "txid ausente", "BR Code sem txid", "https://pix-bancada.local/problems/missing-txid")
    db = await aiosqlite.connect(caminho_banco)
    db.row_factory = aiosqlite.Row
    try:
        async with db.execute("SELECT * FROM cobrancas WHERE txid=?", (txid,)) as cur:
            row = await cur.fetchone()
        if row is None:
            raise problema(404, "Nao encontrado", f"Cobranca {txid} nao encontrada", "https://pix-bancada.local/problems/not-found")
        if row["status"] != "ATIVA":
            raise problema(409, "Estado invalido", f"Cobranca em estado {row['status']}", "https://pix-bancada.local/problems/invalid-state")
        if row["expiracao_em"]:
            exp = datetime.fromisoformat(row["expiracao_em"])
            if relogio.agora() >= exp:
                raise problema(410, "Expirada", "Cobranca expirada", "https://pix-bancada.local/problems/expired")
        valor_cob = row["valor"]
        valor_pago = body.valor or valor_cob
        if valor_cob and valor_pago != valor_cob:
            raise problema(400, "Valor divergente", f"Esperado {valor_cob}, recebido {valor_pago}", "https://pix-bancada.local/problems/amount-mismatch")
        # idempotencia: se ja pago, recusar
        async with db.execute("SELECT 1 FROM pix WHERE txid=?", (txid,)) as cur:
            if await cur.fetchone() is not None:
                raise problema(409, "Ja pago", "Cobranca ja foi paga", "https://pix-bancada.local/problems/already-paid")
        e2eid = gerar_end_to_end_id(data=relogio.agora())
        agora = relogio.agora().isoformat()
        await db.execute(
            "INSERT INTO pix (end_to_end_id, txid, valor, pago_em) VALUES (?,?,?,?)",
            (e2eid, txid, valor_pago or "0.00", agora),
        )
        chave_cob = row["chave"]
        await db.execute("UPDATE cobrancas SET status='CONCLUIDA' WHERE txid=?", (txid,))
        await db.commit()
    finally:
        await db.close()
    try:
        await enfileirar_entrega(chave_cob, e2eid, valor_pago or "0.00", txid=txid)
    except Exception:
        pass
    return {"endToEndId": e2eid, "txid": txid, "valor": valor_pago, "horario": agora}


@router.get("/pix/{e2eid}")
async def consultar_pix(e2eid: str) -> dict[str, object]:
    db = await aiosqlite.connect(caminho_banco)
    db.row_factory = aiosqlite.Row
    try:
        async with db.execute("SELECT * FROM pix WHERE end_to_end_id=?", (e2eid,)) as cur:
            row = await cur.fetchone()
    finally:
        await db.close()
    if row is None:
        raise problema(404, "Nao encontrado", f"Pix {e2eid} nao encontrado", "https://pix-bancada.local/problems/not-found")
    return {
        "endToEndId": row["end_to_end_id"],
        "txid": row["txid"],
        "valor": row["valor"],
        "horario": row["pago_em"],
    }


@router.get("/pix")
async def listar_pix() -> dict[str, object]:
    db = await aiosqlite.connect(caminho_banco)
    db.row_factory = aiosqlite.Row
    try:
        async with db.execute("SELECT * FROM pix") as cur:
            rows = await cur.fetchall()
    finally:
        await db.close()
    return {"pix": [dict(r) for r in rows]}


class DevolucaoBody(BaseModel):
    valor: str
    motivo: str | None = None


@router.put("/pix/{e2eid}/devolucao/{dev_id}")
async def criar_devolucao(e2eid: str, dev_id: str, body: DevolucaoBody) -> dict[str, object]:
    db = await aiosqlite.connect(caminho_banco)
    db.row_factory = aiosqlite.Row
    try:
        async with db.execute("SELECT 1 FROM pix WHERE end_to_end_id=?", (e2eid,)) as cur:
            if await cur.fetchone() is None:
                raise problema(404, "Nao encontrado", f"Pix {e2eid} nao encontrado", "https://pix-bancada.local/problems/not-found")
        agora = relogio.agora().isoformat()
        await db.execute(
            (
                "INSERT OR REPLACE INTO devolucoes "
                "(id, e2eid, valor, status, criado_em) VALUES (?,?,?,?,?)"
            ),
            (dev_id, e2eid, body.valor, "EM_PROCESSAMENTO", agora),
        )
        await db.commit()
    finally:
        await db.close()
    return {"id": dev_id, "e2eid": e2eid, "valor": body.valor, "status": "EM_PROCESSAMENTO"}


@router.get("/pix/{e2eid}/devolucao/{dev_id}")
async def consultar_devolucao(e2eid: str, dev_id: str) -> dict[str, object]:
    db = await aiosqlite.connect(caminho_banco)
    db.row_factory = aiosqlite.Row
    try:
        async with db.execute(
            "SELECT * FROM devolucoes WHERE id=? AND e2eid=?",
            (dev_id, e2eid),
        ) as cur:
            row = await cur.fetchone()
    finally:
        await db.close()
    if row is None:
        raise problema(404, "Nao encontrado", f"Devolucao {dev_id} nao encontrada", "https://pix-bancada.local/problems/not-found")
    return {"id": row["id"], "e2eid": row["e2eid"], "valor": row["valor"], "status": row["status"]}
