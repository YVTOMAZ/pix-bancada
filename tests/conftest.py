from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _limpar_db() -> Generator[None, None, None]:
    for nome in ("pix_bancada.db",):
        p = Path(nome)
        if p.exists():
            p.unlink()
    yield
    for nome in ("pix_bancada.db",):
        p = Path(nome)
        if p.exists():
            p.unlink()
