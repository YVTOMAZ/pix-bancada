import re

from pix_bancada.brcode import crc16_ccitt, gerar_brcode, parse_brcode, validar_crc
from pix_bancada.clock import Relogio
from pix_bancada.ids import gerar_end_to_end_id, gerar_txid


def test_crc16_vetor_conhecido() -> None:
    # CRC16-CCITT (Kermit) vetor classico
    assert crc16_ccitt(b"123456789") == 0x29B1


def test_txid_formato() -> None:
    t = gerar_txid()
    assert 26 <= len(t) <= 35
    assert re.fullmatch(r"[A-Za-z0-9]+", t)


def test_e2eid_formato() -> None:
    e = gerar_end_to_end_id()
    assert re.fullmatch(r"E[0-9]{8}[0-9]{12}[A-Za-z0-9]{11}", e)
    assert len(e) == 32


def test_brcode_crc_valido() -> None:
    bc = gerar_brcode("12345678901", valor="10.50")
    assert validar_crc(bc) is True


def test_brcode_parse_tem_crc() -> None:
    bc = gerar_brcode("12345678901")
    p = parse_brcode(bc)
    assert "63" in p
    assert p["00"] == "01"


def test_relogio_avanca() -> None:
    r = Relogio()
    a0 = r.agora()
    r.avancar(minutos=5)
    assert (r.agora() - a0).total_seconds() == 300
