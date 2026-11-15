"""Erros no formato de problema da API Pix (RFC 7807-like)."""

from fastapi import HTTPException


def problema(
    status: int,
    title: str,
    detail: str,
    type_: str = "https://pix-bancada.local/problems/generic",
) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"type": type_, "title": title, "status": status, "detail": detail},
    )
