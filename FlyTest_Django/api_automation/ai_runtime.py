from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from django.core.cache import cache

T = TypeVar("T")

_AI_FEATURE_LOCKS: dict[str, threading.Lock] = {}
_AI_FEATURE_LOCKS_GUARD = threading.Lock()


@dataclass
class AIOperationMeta:
    feature: str
    cache_key: str | None
    cache_hit: bool
    duration_ms: float
    lock_wait_ms: float = 0.0


def _stable_json_default(value: Any):
    if isinstance(value, set):
        return sorted(value)
    if hasattr(value, "__dict__"):
        return value.__dict__
    return str(value)


def stable_json_dumps(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_stable_json_default,
    )


def stable_digest(*parts: Any) -> str:
    payload = stable_json_dumps(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_ai_cache_key(feature: str, *parts: Any) -> str:
    return f"api_automation:ai:{feature}:{stable_digest(feature, *parts)}"


def _get_feature_lock(user, feature: str) -> threading.Lock:
    user_key = str(getattr(user, "pk", None) or "anonymous")
    lock_key = f"{feature}:{user_key}"
    with _AI_FEATURE_LOCKS_GUARD:
        lock = _AI_FEATURE_LOCKS.get(lock_key)
        if lock is None:
            lock = threading.Lock()
            _AI_FEATURE_LOCKS[lock_key] = lock
        return lock


def acquire_feature_lock(
    *,
    user,
    feature: str,
    timeout_seconds: int,
    error_message: str,
) -> tuple[threading.Lock, float]:
    started_at = time.perf_counter()
    lock = _get_feature_lock(user, feature)
    if lock.acquire(timeout=max(int(timeout_seconds), 1)):
        waited_ms = round((time.perf_counter() - started_at) * 1000, 2)
        return lock, waited_ms
    raise RuntimeError(error_message)


def run_ai_operation(
    *,
    user,
    feature: str,
    cache_key: str | None,
    cache_ttl_seconds: int,
    lock_timeout_seconds: int,
    lock_error_message: str,
    compute: Callable[[], T],
    should_cache: Callable[[T], bool] | None = None,
) -> tuple[T, AIOperationMeta]:
    started_at = time.perf_counter()
    if cache_key:
        cached_value = cache.get(cache_key)
        if cached_value is not None:
            return copy.deepcopy(cached_value), AIOperationMeta(
                feature=feature,
                cache_key=cache_key,
                cache_hit=True,
                duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
            )

    lock, waited_ms = acquire_feature_lock(
        user=user,
        feature=feature,
        timeout_seconds=lock_timeout_seconds,
        error_message=lock_error_message,
    )
    try:
        if cache_key:
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return copy.deepcopy(cached_value), AIOperationMeta(
                    feature=feature,
                    cache_key=cache_key,
                    cache_hit=True,
                    duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
                    lock_wait_ms=waited_ms,
                )

        result = compute()
        if cache_key and max(int(cache_ttl_seconds), 0) > 0:
            cache_enabled = True if should_cache is None else bool(should_cache(result))
            if cache_enabled:
                cache.set(cache_key, copy.deepcopy(result), timeout=max(int(cache_ttl_seconds), 1))
        return result, AIOperationMeta(
            feature=feature,
            cache_key=cache_key,
            cache_hit=False,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
            lock_wait_ms=waited_ms,
        )
    finally:
        lock.release()
