"""Relogio virtual injetavel para testes deterministas."""

from datetime import UTC, datetime, timedelta


class Relogio:
    def __init__(self, inicio: datetime | None = None) -> None:
        self._agora = inicio or datetime.now(UTC)

    def agora(self) -> datetime:
        return self._agora

    def avancar(
        self,
        segundos: int | float = 0,
        minutos: int = 0,
        horas: int = 0,
        dias: int = 0,
    ) -> datetime:
        self._agora = self._agora + timedelta(
            seconds=segundos, minutes=minutos, hours=horas, days=dias
        )
        return self._agora

    def definir(self, momento: datetime) -> None:
        self._agora = momento
