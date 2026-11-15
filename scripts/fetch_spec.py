"""Baixa o openapi.yaml oficial do BCB (pinado por commit + SHA256)."""

import hashlib
import pathlib
import sys
import urllib.request

PINNED_COMMIT = "3ebbd6a184519cf8a032f2747b87cce2a3d05e7f"
PINNED_SHA256 = "cf191845044a5edd38c00b0e099924e8daceacfe53502abaa6a5b238bed41eb4"
URL = f"https://raw.githubusercontent.com/bacen/pix-api/{PINNED_COMMIT}/openapi.yaml"


def main() -> int:
    cache_dir = pathlib.Path(".cache")
    cache_dir.mkdir(exist_ok=True)
    destino = cache_dir / "openapi.yaml"
    urllib.request.urlretrieve(URL, destino)
    h = hashlib.sha256(destino.read_bytes()).hexdigest()
    if h != PINNED_SHA256:
        print(f"Hash divergente: esperado {PINNED_SHA256}, obtido {h}", file=sys.stderr)
        return 1
    (cache_dir / "openapi.sha256").write_text(h)
    print(f"OK: {destino} ({h})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
