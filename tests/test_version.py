"""Garante que a versao e coerente entre todos os manifestos."""

import json
import tomllib
from importlib.metadata import version as installed_version
from pathlib import Path

import pix_bancada

ROOT = Path(__file__).resolve().parents[1]


def _versao_pyproject() -> str:
    with (ROOT / "pyproject.toml").open("rb") as f:
        return tomllib.load(f)["project"]["version"]


def _versao_frontend() -> str:
    with (ROOT / "frontend" / "package.json").open() as f:
        return json.load(f)["version"]


def test_versoes_coerentes() -> None:
    versao = pix_bancada.__version__
    assert versao == _versao_pyproject()
    assert versao == _versao_frontend()
    assert versao == installed_version("pix-bancada")

    changelog = (ROOT / "CHANGELOG.md").read_text()
    assert f"## [{versao}]" in changelog