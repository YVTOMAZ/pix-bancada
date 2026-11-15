"""OAuth2 client_credentials simplificado."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class TokenRequest(BaseModel):
    grant_type: str = "client_credentials"
    client_id: str = "pix-bancada"
    client_secret: str = "pix-bancada"
    scope: str = "cob.read cob.write pix.read webhook.read webhook.write"


@router.post("/oauth/token")
async def token(body: TokenRequest | None = None) -> dict[str, object]:
    return {
        "access_token": "pix-bancada-token-ficticio",
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": (body.scope if body else "cob.read cob.write"),
    }
