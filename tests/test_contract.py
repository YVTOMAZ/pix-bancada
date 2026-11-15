import hashlib
import subprocess
import sys
from pathlib import Path


def test_fetch_spec_baixa_e_hash_bate() -> None:
    r = subprocess.run([sys.executable, "scripts/fetch_spec.py"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    p = Path(".cache/openapi.yaml")
    assert p.exists()
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    assert h == "cf191845044a5edd38c00b0e099924e8daceacfe53502abaa6a5b238bed41eb4"


def test_cache_gitignored() -> None:
    gitignore = Path(".gitignore").read_text()
    assert ".cache/" in gitignore or ".cache" in gitignore


def test_hash_divergente_falha() -> None:
    spec_path = Path("scripts/fetch_spec.py")
    src = spec_path.read_text()
    # carregar modulo com hash alterado
    src_mod = src.replace(
        "PINNED_SHA256 = \"cf191845044a5edd38c00b0e099924e8daceacfe53502abaa6a5b238bed41eb4\"",
        "PINNED_SHA256 = \"0000000000000000000000000000000000000000000000000000000000000000\"",
    )
    ns: dict[str, object] = {}
    exec(compile(src_mod, "fetch_spec_mod", "exec"), ns)
    # chamar main com cache ja existente nao re-baixa? main sempre baixa. Rodar.
    main_fn = ns["main"]
    assert callable(main_fn)
    rc = main_fn()
    assert rc == 1
