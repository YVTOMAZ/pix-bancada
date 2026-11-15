from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pix_bancada.estado import relogio
from pix_bancada.webhooks import cenario


@pytest.fixture(autouse=True)
def _limpar_db() -> Generator[None, None, None]:
    for nome in ("pix_bancada.db",):
        p = Path(nome)
        if p.exists():
            p.unlink()
    # reset relogio virtual
    relogio._agora = datetime.now(UTC)
    # reset cenario
    cenario.clear()
    cenario.update(
        {
            "duplicar": False,
            "atrasar_segundos": 0,
            "perder": False,
            "fora_de_ordem": False,
            "erro_5xx": False,
            "semente": 42,
        }
    )
    yield
    for nome in ("pix_bancada.db",):
        p = Path(nome)
        if p.exists():
            p.unlink()
