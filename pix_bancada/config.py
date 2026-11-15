from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracao(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PIX_BANCADA_", env_file=".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8080
    banco_url: str = "sqlite+aiosqlite:///./pix_bancada.db"
    semente: int = 42


def obter_configuracao() -> Configuracao:
    return Configuracao()
