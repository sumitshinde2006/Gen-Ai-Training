"""Request-scoped telemetry shared by the API and provider integrations."""

from contextvars import ContextVar, Token
from typing import Any

_token_usage: ContextVar[dict[str, Any] | None] = ContextVar(
    "kandaguide_token_usage", default=None
)
_cache_hit: ContextVar[dict[str, bool] | None] = ContextVar(
    "kandaguide_cache_hit", default=None
)


def reset_request_telemetry() -> tuple[
    Token[dict[str, Any] | None], Token[dict[str, bool] | None]
]:
    """Start a clean telemetry scope and return reset tokens for its caller."""
    return _token_usage.set({}), _cache_hit.set({"hit": False})


def restore_request_telemetry(
    tokens: tuple[
        Token[dict[str, Any] | None], Token[dict[str, bool] | None]
    ]
) -> None:
    token_usage_token, cache_hit_token = tokens
    _token_usage.reset(token_usage_token)
    _cache_hit.reset(cache_hit_token)


def record_token_usage(
    provider: str, prompt_tokens: int | None, completion_tokens: int | None
) -> None:
    """Record actual provider usage counts when available."""
    usage = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "provider": provider,
        "source": (
            f"{provider}_actual"
            if prompt_tokens is not None or completion_tokens is not None
            else "unavailable"
        ),
        "available": prompt_tokens is not None or completion_tokens is not None,
    }
    request_usage = _token_usage.get()
    if request_usage is None:
        _token_usage.set(usage)
    else:
        request_usage.update(usage)


def token_usage() -> dict[str, Any]:
    """Return a safe, explicit unavailable value when a provider supplied none."""
    usage = _token_usage.get()
    if usage is None or "source" not in usage:
        return {
            "prompt_tokens": None,
            "completion_tokens": None,
            "source": "unavailable",
            "available": False,
        }
    return dict(usage)


def record_cache_hit(hit: bool) -> None:
    request_cache = _cache_hit.get()
    if request_cache is None:
        _cache_hit.set({"hit": hit})
    else:
        request_cache["hit"] = hit


def cache_hit() -> bool:
    request_cache = _cache_hit.get()
    return request_cache.get("hit", False) if request_cache else False
