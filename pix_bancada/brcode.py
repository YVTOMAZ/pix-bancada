"""Gerador e parser de BR Code (copia-e-cola Pix) EMV com CRC16-CCITT."""

CRC_POLY = 0x1021
CRC_INIT = 0xFFFF


def crc16_ccitt(data: str | bytes) -> int:
    if isinstance(data, str):
        data = data.encode("utf-8")
    crc = CRC_INIT
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ CRC_POLY) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def _tlv(tag: str, value: str) -> str:
    return f"{tag}{len(value):02d}{value}"


def gerar_brcode(
    chave: str,
    valor: str | None = None,
    txid: str = "***",
    nome: str = "RECEBEDOR TESTE",
    cidade: str = "SAO PAULO",
    descricao: str | None = None,
) -> str:
    # Merchant Account Information (tag 26)
    gui = _tlv("00", "br.gov.bcb.pix")
    chave_tlv = _tlv("01", chave)
    if descricao:
        chave_tlv += _tlv("02", descricao)
    mai = _tlv("26", gui + chave_tlv)

    payload = _tlv("00", "01")
    payload += _tlv("01", "12")  # dinamico
    payload += mai
    payload += _tlv("52", "0000")
    payload += _tlv("53", "986")  # BRL
    if valor is not None:
        payload += _tlv("54", valor)
    payload += _tlv("58", "BR")
    payload += _tlv("59", nome[:25])
    payload += _tlv("60", cidade[:15])
    # Additional Data Field (txid)
    adf = _tlv("05", txid)
    payload += _tlv("62", adf)
    # CRC placeholder
    payload += "6304"
    crc = crc16_ccitt(payload)
    payload = payload[:-4] + f"6304{crc:04X}"
    return payload


def validar_crc(brcode: str) -> bool:
    idx = brcode.rfind("6304")
    if idx == -1:
        return False
    corpo = brcode[: idx + 4]
    crc_str = brcode[idx + 4 :]
    if len(crc_str) != 4:
        return False
    try:
        crc_esperado = int(crc_str, 16)
    except ValueError:
        return False
    return crc16_ccitt(corpo) == crc_esperado


def parse_brcode(brcode: str) -> dict[str, str]:
    """Parser minimo de TLV de primeiro nivel."""
    resultado: dict[str, str] = {}
    i = 0
    n = len(brcode)
    while i + 4 <= n:
        tag = brcode[i : i + 2]
        try:
            length = int(brcode[i + 2 : i + 4])
        except ValueError:
            break
        value = brcode[i + 4 : i + 4 + length]
        resultado[tag] = value
        i += 4 + length
        if tag == "63":
            break
    return resultado
