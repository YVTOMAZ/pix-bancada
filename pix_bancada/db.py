"""Camada de persistencia SQLite (aiosqlite)."""

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS cobrancas (
    txid TEXT PRIMARY KEY,
    chave TEXT NOT NULL,
    valor TEXT,
    status TEXT NOT NULL,
    expiracao_em TEXT,
    criado_em TEXT NOT NULL,
    brcode TEXT
);
CREATE TABLE IF NOT EXISTS pix (
    end_to_end_id TEXT PRIMARY KEY,
    txid TEXT,
    valor TEXT NOT NULL,
    pago_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS devolucoes (
    id TEXT PRIMARY KEY,
    e2eid TEXT NOT NULL,
    valor TEXT NOT NULL,
    status TEXT NOT NULL,
    criado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS webhooks (
    chave TEXT PRIMARY KEY,
    url TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entregas_webhook (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chave TEXT NOT NULL,
    payload TEXT NOT NULL,
    status INTEGER,
    tentativas INTEGER NOT NULL DEFAULT 0,
    proxima_em TEXT,
    ultimo_status_http INTEGER
);
"""


async def inicializar_banco(caminho: str) -> None:
    async with aiosqlite.connect(caminho) as db:
        await db.executescript(SCHEMA)
        # migration: add ultimo_status_http if missing
        async with db.execute("PRAGMA table_info(entregas_webhook)") as cur:
            cols = [r[1] for r in await cur.fetchall()]
        if "ultimo_status_http" not in cols:
            await db.execute("ALTER TABLE entregas_webhook ADD COLUMN ultimo_status_http INTEGER")
        await db.commit()


def caminho_do_banco(url: str) -> str:
    # sqlite+aiosqlite:///./x.db  -> ./x.db
    if ":///" in url:
        return url.split(":///", 1)[1]
    return url
