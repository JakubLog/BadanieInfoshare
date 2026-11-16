"""Wyjątki harnessu niezależne od backendu (bez importu SDK)."""

from __future__ import annotations


class InfraError(Exception):
    """Błąd infrastruktury (API po wyczerpaniu ponowień, awaria środowiska): przebieg nie jest liczony."""


class QuotaError(Exception):
    """Wyczerpany limit abonamentu: przebieg nie jest liczony, runner czeka do resetu okna."""

    def __init__(self, message: str, resets_at: int | None):
        super().__init__(message)
        self.resets_at = resets_at
