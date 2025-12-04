"""Cache leve para resultados de serviços."""
from __future__ import annotations

import functools
import hashlib
import json
from typing import Any, Callable, Optional

from app.config import CACHE_TTL, ENABLE_CACHE


class SimpleCache:
    """Cache simples em memória com TTL."""

    def __init__(self, ttl: int = 3600):
        self._cache: dict[str, tuple[Any, float]] = {}
        self.ttl = ttl

    def get(self, key: str) -> Optional[Any]:
        """Recupera valor do cache se ainda válido."""
        if not ENABLE_CACHE:
            return None

        if key in self._cache:
            value, timestamp = self._cache[key]
            import time

            if time.time() - timestamp < self.ttl:
                return value
            else:
                del self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """Armazena valor no cache."""
        if not ENABLE_CACHE:
            return

        import time

        self._cache[key] = (value, time.time())

    def clear(self) -> None:
        """Limpa o cache."""
        self._cache.clear()


# Cache global
_global_cache = SimpleCache(ttl=CACHE_TTL)


def cache_key(*args, **kwargs) -> str:
    """Gera chave de cache a partir de argumentos."""
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.md5(key_data.encode()).hexdigest()


def cached(func: Callable) -> Callable:
    """Decorator para cachear resultados de funções."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        key = f"{func.__module__}.{func.__name__}:{cache_key(*args, **kwargs)}"
        cached_value = _global_cache.get(key)
        if cached_value is not None:
            return cached_value

        result = func(*args, **kwargs)
        _global_cache.set(key, result)
        return result

    return wrapper


