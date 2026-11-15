"""Rotas de cobranca imediata (cob) e location (loc)."""

import logging
from datetime import datetime, timedelta
from typing import Any

import aiosqlite
from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, Field, model_validator

from pix_bancada.brcode import gerar_brcode
from pix_bancada.erros import problema
from pix_bancada.estado import caminho_banco, relogio
from pix_bancada.ids import gerar_txid

logger = logging.getLogger(__name__)

router = APIRouter()


class CobExpiracao(BaseModel):
    expiracao: int = Field(default=86400, ge=1)


class CobValor(BaseModel):
    original: str | None = Field(default=None, pattern=r"^\d{1,10}\.\d{2}$")
    modalidadeAlteracao: int | None = Field(default=None, ge=0, le=1)


class Devedor(BaseModel):
    cpf: str | None = None
    cnpj: str | None = None
    nome: str

    @model_validator(mode="after")
    def _um_identificador(self) -> "Devedor":
        if (self.cpf is None) == (self.cnpj is None):
            raise ValueError("informe cpf ou cnpj, nunca os dois")
        return self


class CobSolicitada(BaseModel):
    chave: str
    valor: CobValor | None = None
    calendario: CobExpiracao | None = None
    devedor: Devedor | None = None
    loc: Any | None = None
    solicitacaoPagador: str | None = None
    infoAdicionais: list[Any] | None = None
    tributo: Any | None = None
    legado: bool = False

    @model_validator(mode="before")
    @classmethod
    def _converter_legado(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        novo = dict(data)
        convertido = False
        valor = novo.get("valor")
        if isinstance(valor, str):
            novo["valor"] = {"original": valor}
            convertido = True
        if "expiracao" in novo and "calendario" not in novo:
            try:
                novo["calendario"] = {"expiracao": int(novo.pop("expiracao"))}
            except (TypeError, ValueError):
                novo["calendario"] = {"expiracao": novo.pop("expiracao")}
            convertido = True
        else:
            novo.pop("expiracao", None)
        if convertido:
            if "calendario" not in novo:
                novo["calendario"] = {"expiracao": 86400}
            novo["legado"] = True
            logger.warning("formato plano legado recebido em cob; sera removido na v0.2.0")
        return novo


class CobRevisada(BaseModel):
    status: str | None = None
    valor: CobValor | None = None
    calendario: CobExpiracao | None = None
    devedor: Devedor | None = None
    loc: Any | None = None
    solicitacaoPagador: str | None = None
    infoAdicionais: list[Any] | None = None
    tributo: Any | None = None
    legado: bool = False

    @model_validator(mode="before")
    @classmethod
    def _converter_legado(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        novo = dict(data)
        convertido = False
        valor = novo.get("valor")
        if isinstance(valor, str):
            novo["valor"] = {"original": valor}
            convertido = True
        if "expiracao" in novo and "calendario" not in novo:
            try:
                novo["calendario"] = {"expiracao": int(novo.pop("expiracao"))}
            except (TypeError, ValueError):
                novo["calendario"] = {"expiracao": novo.pop("expiracao")}
            convertido = True
        else:
            novo.pop("expiracao", None)
        if convertido:
            if "calendario" not in novo:
                novo["calendario"] = {"expiracao": 86400}
            novo["legado"] = True
            logger.warning("formato plano legado recebido em cob; sera removido na v0.2.0")
        return novo


ESTADOS_VALIDOS = {"ATIVA", "CONCLUIDA", "REMOVIDA_PELO_USUARIO_RECEBEDOR", "REMOVIDA_PELO_PSP"}


async def _conn() -> aiosqlite.Connection:
    db = await aiosqlite.connect(caminho_banco)
    db.row_factory = aiosqlite.Row
    return db


def _row_para_cob(row: aiosqlite.Row) -> dict[str, object]:
    criacao = row["criado_em"]
    expiracao_seg = 3600
    if row["expiracao_em"] and criacao:
        try:
            delta = datetime.fromisoformat(row["expiracao_em"]) - datetime.fromisoformat(criacao)
            expiracao_seg = int(delta.total_seconds())
        except ValueError:
            expiracao_seg = 3600
    return {
        "calendario": {"criacao": criacao, "expiracao": expiracao_seg},
        "txid": row["txid"],
        "revisao": 0,
        "status": row["status"],
        "valor": {"original": row["valor"]} if row["valor"] else {},
        "chave": row["chave"],
        "loc": {
            "id": int(row["txid"][:8]) if row["txid"][:8].isdigit() else 0,
            "location": f"http://pix-bancada.local/loc/{row['txid'][:8]}",
            "tipoCob": "cob",
            "criacao": row["criado_em"],
            "txid": row["txid"],
        },
        "pixCopiaECola": row["brcode"],
    }


@router.put("/cob/{txid}", status_code=201)
async def criar_ou_alterar_cob(
    txid: str, body: CobSolicitada, response: Response
) -> dict[str, object]:
    agora = relogio.agora().isoformat()
    valor_str = body.valor.original if body.valor is not None else None
    expiracao = body.calendario.expiracao if body.calendario is not None else 86400
    expira = (relogio.agora() + timedelta(seconds=expiracao)).isoformat()
    brcode = gerar_brcode(body.chave, valor=valor_str, txid=txid)
    db = await _conn()
    try:
        await db.execute(
            """INSERT INTO cobrancas (txid, chave, valor, status, expiracao_em, criado_em, brcode)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(txid) DO UPDATE SET
                 chave=excluded.chave, valor=excluded.valor, status='ATIVA',
                 expiracao_em=excluded.expiracao_em, brcode=excluded.brcode""",
            (txid, body.chave, valor_str, "ATIVA", expira, agora, brcode),
        )
        await db.commit()
        async with db.execute("SELECT * FROM cobrancas WHERE txid=?", (txid,)) as cur:
            row = await cur.fetchone()
        assert row is not None
    finally:
        await db.close()
    if body.legado:
        response.headers["Deprecation"] = "true"
    return _row_para_cob(row)


@router.post("/cob", status_code=201)
async def criar_cob(body: CobSolicitada, response: Response) -> dict[str, object]:
    txid = gerar_txid()
    # delegar preservando header: chamar e setar header na response local
    r = await criar_ou_alterar_cob(txid, body, response)
    return r


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
async def alterar_cob(txid: str, body: CobRevisada, response: Response) -> dict[str, object]:
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
            await db.execute(
                "UPDATE cobrancas SET valor=? WHERE txid=?", (body.valor.original, txid)
            )
        if body.calendario is not None and body.calendario.expiracao is not None:
            criacao = row["criado_em"]
            try:
                base = datetime.fromisoformat(criacao)
                novo_exp = (base + timedelta(seconds=body.calendario.expiracao)).isoformat()
                await db.execute(
                    "UPDATE cobrancas SET expiracao_em=? WHERE txid=?", (novo_exp, txid)
                )
            except ValueError:
                pass
        await db.commit()
        async with db.execute("SELECT * FROM cobrancas WHERE txid=?", (txid,)) as cur:
            row = await cur.fetchone()
        assert row is not None
    finally:
        await db.close()
    if body.legado:
        response.headers["Deprecation"] = "true"
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
        if inicio:
            q += " AND criado_em >= ?"
            params.append(inicio)
        if fim:
            q += " AND criado_em <= ?"
            params.append(fim)
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
        "id": int(loc_id) if str(loc_id).isdigit() else 0,
        "location": f"http://pix-bancada.local/loc/{loc_id}",
        "tipoCob": "cob",
        "txid": row["txid"],
        "criacao": row["criado_em"],
    }
