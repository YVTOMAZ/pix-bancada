"""Geradores de txid e endToEndId no formato do BCB."""

import random
import string
from datetime import datetime


def gerar_txid(tamanho: int = 35) -> str:
    if not (26 <= tamanho <= 35):
        raise ValueError("txid deve ter entre 26 e 35 caracteres")
    alfabeto = string.ascii_letters + string.digits
    return "".join(random.choice(alfabeto) for _ in range(tamanho))


def gerar_end_to_end_id(ispb: str = "00000000", data: datetime | None = None) -> str:
    """Formato: E<ispb 8><AAAAMMDDHHMM><rand 11>. Total 32 chars."""
    data = data or datetime.now()
    carimbo = data.strftime("%Y%m%d%H%M")
    alfabeto = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    rand = "".join(random.choice(alfabeto) for _ in range(11))
    return f"E{ispb}{carimbo}{rand}"
