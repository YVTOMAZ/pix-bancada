from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from pix_bancada.cobrancas import router as cob_router
from pix_bancada.config import obter_configuracao
from pix_bancada.estado import inicializar
from pix_bancada.oauth import router as oauth_router
from pix_bancada.pix import router as pix_router

configuracao = obter_configuracao()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await inicializar()
    yield


app = FastAPI(title="pix-bancada", version="0.1.0", lifespan=lifespan)


@app.get("/saude")
async def saude() -> dict[str, str]:
    return {"status": "ok", "versao": "0.1.0"}


app.include_router(oauth_router)
app.include_router(cob_router)
app.include_router(pix_router)
