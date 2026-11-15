"""Rotas de cobranca imediata (cob) e location (loc)."""

from datetime import datetime, timedelta

import aiosqlite
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from pix_bancada.brcode import gerar_brcode
from pix_bancada.erros import problema
from pix_bancada.estado import caminho_banco, relogio
from pix_bancada.ids import gerar_txid

router = APIRouter()


class CobrancaCriar(BaseModel):
    chave: str
    valor: str | None = None
    expiracao: int = Field(default=3600, ge=1)
    solicitacaoPagador: str | None = None


class CobrancaPatch(BaseModel):
    status: str | None = None
    valor: str | None = None


ESTADOS_VALIDOS = {"ATIVA", "CONCLUIDA", "REMOVIDA_PELO_USUARIO_RECEBEDOR", "REMOVIDA_PELO_PSP"}


async def _conn() -> aiosqlite.Connection:
    db = await aiosqlite.connect(caminho_banco)
    db.row_factory = aiosqlite.Row
    return db


def _row_para_cob(row: aiosqlite.Row) -> dict[str, object]:
    return {
        "calendario": {"criacao": row["criado_em"], "expiracao": row["expiracao_em"]},
        "txid": row["txid"],
        "revisao": 0,
        "status": row["status"],
        "valor": {"original": row["valor"]} if row["valor"] else {},
        "chave": row["chave"],
        "solicitacaoPagador": None,
        "loc": {
            "id": row["txid"][:8],
            "location": f"pix-bancada.local/loc/{row['txid'][:8]}",
            "tipoCob": "cob",
        },
        "pixCopiaECola": row["brcode"],
    }


@router.put("/cob/{txid}")
async def criar_ou_alterar_cob(txid: str, body: CobrancaCriar) -> dict[str, object]:
    agora = relogio.agora().isoformat()
    expira = (relogio.agora() + timedelta(seconds=body.expiracao)).isoformat()
    brcode = gerar_brcode(body.chave, valor=body.valor, txid=txid)
    db = await _conn()
    try:
        await db.execute(
            """INSERT INTO cobrancas (txid, chave, valor, status, expiracao_em, criado_em, brcode)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(txid) DO UPDATE SET
                 chave=excluded.chave, valor=excluded.valor, status='ATIVA',
                 expiracao_em=excluded.expiracao_em, brcode=excluded.brcode""",
            (txid, body.chave, body.valor, "ATIVA", expira, agora, brcode),
        )
        await db.commit()
        async with db.execute("SELECT * FROM cobrancas WHERE txid=?", (txid,)) as cur:
            row = await cur.fetchone()
        assert row is not None
    finally:
        await db.close()
    return _row_para_cob(row)


@router.post("/cob")
async def criar_cob(body: CobrancaCriar) -> dict[str, object]:
    txid = gerar_txid()
    return await criar_ou_alterar_cob(txid, body)


@router.get("/cob/{txid}")
async def consultar_cob(txid: str) -> dict[str, object]:
    db = await _conn()
    try:
        async with db.execute("SELECT * FROM cobrancas WHERE txid=?", (txid,)) as cur:
            row = await cur.fetchone()
    finally:
        await db.close()
    if row is None:
        raise problema(404, "Nao encontrado", f"Cobranca {txid} nao encontrada", "https://pix-bancada.local/problems/not-found")
    # expiracao
    if row["status"] == "ATIVA" and row["expiracao_em"]:
        exp = datetime.fromisoformat(row["expiracao_em"])
        if relogio.agora() >= exp:
            db2 = await _conn()
            await db2.execute(
                "UPDATE cobrancas SET status='REMOVIDA_PELO_PSP' WHERE txid=?",
                (txid,),
            )
            await db2.commit()
            await db2.close()
            row = None
            db3 = await _conn()
            async with db3.execute("SELECT * FROM cobrancas WHERE txid=?", (txid,)) as cur:
                row = await cur.fetchone()
            await db3.close()
    assert row is not None
    return _row_para_cob(row)


@router.patch("/cob/{txid}")
async def alterar_cob(txid: str, body: CobrancaPatch) -> dict[str, object]:
    db = await _conn()
    try:
        async with db.execute("SELECT * FROM cobrancas WHERE txid=?", (txid,)) as cur:
            row = await cur.fetchone()
        if row is None:
            raise problema(404, "Nao encontrado", f"Cobranca {txid} nao encontrada", "https://pix-bancada.local/problems/not-found")
        assert row is not None
        if body.status is not None:
            if body.status not in ESTADOS_VALIDOS:
                raise problema(400, "Estado invalido", f"Estado {body.status} invalido", "https://pix-bancada.local/problems/invalid-state")
            await db.execute("UPDATE cobrancas SET status=? WHERE txid=?", (body.status, txid))
        if body.valor is not None:
            await db.execute("UPDATE cobrancas SET valor=? WHERE txid=?", (body.valor, txid))
        await db.commit()
        async with db.execute("SELECT * FROM cobrancas WHERE txid=?", (txid,)) as cur:
            row = await cur.fetchone()
        assert row is not None
    finally:
        await db.close()
    return _row_para_cob(row)


@router.get("/cob")
async def listar_cob(
    inicio: str | None = Query(default=None),
    fim: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> dict[str, object]:
    db = await _conn()
    try:
        q = "SELECT * FROM cobrancas WHERE 1=1"
        params: list[object] = []
        if status:
            q += " AND status=?"
            params.append(status)
        async with db.execute(q, params) as cur:
            rows = await cur.fetchall()
    finally:
        await db.close()
    return {"cobrancas": [_row_para_cob(r) for r in rows]}


@router.get("/loc/{loc_id}")
async def consultar_loc(loc_id: str) -> dict[str, object]:
    # loc_id e prefixo do txid; busca cobranca cujo txid comeca com loc_id
    db = await _conn()
    try:
        async with db.execute("SELECT * FROM cobrancas WHERE txid LIKE ?", (loc_id + "%",)) as cur:
            row = await cur.fetchone()
    finally:
        await db.close()
    if row is None:
        raise problema(404, "Nao encontrado", f"Location {loc_id} nao encontrada", "https://pix-bancada.local/problems/not-found")
    assert row is not None
    return {
        "id": loc_id,
        "location": f"pix-bancada.local/loc/{loc_id}",
        "tipoCob": "cob",
        "txid": row["txid"],
    }
