"""Validated runtime limits and cache settings for KandaGuide."""

import math
import os
from dataclasses import dataclass

from app.vectorstore import MAX_TOP_K

MAX_QUESTION_LENGTH = 1000


class SettingsError(ValueError):
    """Raised when an environment setting is invalid."""


@dataclass(frozen=True)
class RuntimeSettings:
    max_question_length: int
    max_top_k: int
    cache_enabled: bool
    cache_ttl_seconds: float
    cache_max_entries: int


def _integer(name: str, default: int, minimum: int, maximum: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as error:
        raise SettingsError(
            f"{name} must be an integer between {minimum} and {maximum}."
        ) from error
    if not minimum <= parsed <= maximum:
        raise SettingsError(
            f"{name} must be an integer between {minimum} and {maximum}."
        )
    return parsed


def _cache_enabled() -> bool:
    value = os.getenv("KANDAGUIDE_CACHE_ENABLED", "true").strip().lower()
    if value not in {"true", "false"}:
        raise SettingsError("KANDAGUIDE_CACHE_ENABLED must be 'true' or 'false'.")
    return value == "true"


def _cache_ttl() -> float:
    value = os.getenv("KANDAGUIDE_CACHE_TTL_SECONDS")
    if value is None:
        return 60.0
    try:
        parsed = float(value)
    except ValueError as error:
        raise SettingsError(
            "KANDAGUIDE_CACHE_TTL_SECONDS must be a number from 0 to 86400."
        ) from error
    if not math.isfinite(parsed) or not 0 <= parsed <= 86400:
        raise SettingsError(
            "KANDAGUIDE_CACHE_TTL_SECONDS must be a number from 0 to 86400."
        )
    return parsed


def get_settings() -> RuntimeSettings:
    """Read and validate settings on each request so invalid overrides surface."""
    return RuntimeSettings(
        max_question_length=_integer(
            "KANDAGUIDE_MAX_QUESTION_LENGTH", MAX_QUESTION_LENGTH, 1, MAX_QUESTION_LENGTH
        ),
        max_top_k=_integer("KANDAGUIDE_MAX_TOP_K", MAX_TOP_K, 1, MAX_TOP_K),
        cache_enabled=_cache_enabled(),
        cache_ttl_seconds=_cache_ttl(),
        cache_max_entries=_integer(
            "KANDAGUIDE_CACHE_MAX_ENTRIES", 128, 0, 100000
        ),
    )
