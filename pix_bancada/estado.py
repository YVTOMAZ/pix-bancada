"""Estado compartilhado do aplicativo (relogio virtual, banco)."""

from pix_bancada.clock import Relogio
from pix_bancada.config import obter_configuracao
from pix_bancada.db import caminho_do_banco, inicializar_banco

configuracao = obter_configuracao()
relogio = Relogio()
caminho_banco = caminho_do_banco(configuracao.banco_url)


async def inicializar() -> None:
    await inicializar_banco(caminho_banco)
