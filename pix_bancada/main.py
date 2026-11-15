from fastapi import FastAPI

from pix_bancada.config import obter_configuracao

configuracao = obter_configuracao()

app = FastAPI(title="pix-bancada", version="0.1.0")


@app.get("/saude")
async def saude() -> dict[str, str]:
    return {"status": "ok", "versao": "0.1.0"}
