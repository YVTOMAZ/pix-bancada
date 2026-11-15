import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _limpar_db():
    for nome in ("pix_bancada.db",):
        p = Path(nome)
        if p.exists():
            p.unlink()
    yield
    for nome in ("pix_bancada.db",):
        p = Path(nome)
        if p.exists():
            p.unlink()
