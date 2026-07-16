import json
import logging
from collections.abc import Callable
from json import JSONDecodeError
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheNamespace:
    RBAC = "rbac"
    PUBLIC_SETTINGS = "public-settings"
    DICTIONARY_ITEMS = "dictionary-items"
    LOGIN_RATE_LIMIT = "login-rate-limit"
    LOGIN_CAPTCHA = "login-captcha"
    SMS_VERIFICATION = "sms-verification"
    QR_CODE_LOGIN = "qr-code-login"


class RedisCache:
    def __init__(self) -> None:
        self._client: Redis[str] | None = None
        self._client_initialized = False
        self._last_error_signature: str | None = None

    def is_enabled(self) -> bool:
        return bool(settings.REDIS_URL)

    def _get_client(self) -> Redis[str] | None:
        if not self.is_enabled():
            return None
        if not self._client_initialized:
            self._client = Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                health_check_interval=30,
                socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
            )
            self._client_initialized = True
        return self._client

    def _run_with_fallback(
        self,
        operation: Callable[[Redis[str]], Any],
        *,
        fallback: Any,
        context: str,
    ) -> Any:
        client = self._get_client()
        if client is None:
            return fallback
        try:
            result = operation(client)
            self._last_error_signature = None
            return result
        except RedisError as exc:
            signature = f"{context}:{exc.__class__.__name__}"
            if signature != self._last_error_signature:
                logger.warning(
                    "Redis unavailable during %s, falling back to database-only mode: %s",
                    context,
                    exc,
                )
                self._last_error_signature = signature
            return fallback

    def _namespace_key(self, namespace: str) -> str:
        return f"{settings.REDIS_KEY_PREFIX}:namespace:{namespace}:version"

    def build_key(self, *parts: object) -> str:
        return f"{settings.REDIS_KEY_PREFIX}:{':'.join(str(part) for part in parts)}"

    def get_namespace_version(self, namespace: str) -> int:
        return self._run_with_fallback(
            lambda client: int(client.get(self._namespace_key(namespace)) or 1),
            fallback=1,
            context=f"get namespace version for {namespace}",
        )

    def bump_namespace(self, namespace: str) -> None:
        self._run_with_fallback(
            lambda client: client.incr(self._namespace_key(namespace)),
            fallback=None,
            context=f"bump namespace for {namespace}",
        )

    def build_versioned_key(self, namespace: str, *parts: object) -> str:
        suffix = ":".join(str(part) for part in parts)
        version = self.get_namespace_version(namespace)
        return f"{settings.REDIS_KEY_PREFIX}:{namespace}:v{version}:{suffix}"

    def get_json(self, key: str) -> Any | None:
        raw = self._run_with_fallback(
            lambda client: client.get(key),
            fallback=None,
            context=f"get cache key {key}",
        )
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except JSONDecodeError:
            logger.warning("Redis cache payload for key %s is not valid JSON", key)
            return None

    def get(self, key: str) -> str | None:
        return self._run_with_fallback(
            lambda client: client.get(key),
            fallback=None,
            context=f"get cache key {key}",
        )

    def set(self, key: str, value: str, *, ttl_seconds: int | None = None) -> bool:
        ttl = ttl_seconds or settings.REDIS_CACHE_TTL_SECONDS
        return bool(
            self._run_with_fallback(
                lambda client: client.setex(key, max(ttl, 1), value),
                fallback=False,
                context=f"set cache key {key}",
            )
        )

    def incr(self, key: str, *, ttl_seconds: int | None = None) -> int | None:
        ttl = ttl_seconds or settings.REDIS_CACHE_TTL_SECONDS

        def operation(client: Redis[str]) -> int:
            next_value = int(client.incr(key))
            if next_value == 1:
                client.expire(key, max(ttl, 1))
            return next_value

        return self._run_with_fallback(
            operation,
            fallback=None,
            context=f"increment cache key {key}",
        )

    def delete(self, *keys: str) -> None:
        if not keys:
            return
        self._run_with_fallback(
            lambda client: client.delete(*keys),
            fallback=None,
            context=f"delete cache keys {','.join(keys)}",
        )

    def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> bool:
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        ttl = ttl_seconds or settings.REDIS_CACHE_TTL_SECONDS
        return bool(
            self._run_with_fallback(
                lambda client: client.setex(key, max(ttl, 1), payload),
                fallback=False,
                context=f"set cache key {key}",
            )
        )

    def compare_and_set_json(
        self,
        key: str,
        *,
        expected: dict[str, Any],
        value: Any,
    ) -> bool:
        script = """
        local raw = redis.call('GET', KEYS[1])
        if not raw then return 0 end
        local current = cjson.decode(raw)
        local expected = cjson.decode(ARGV[1])
        for field, expected_value in pairs(expected) do
            if current[field] ~= expected_value then return 0 end
        end
        local ttl = redis.call('PTTL', KEYS[1])
        if ttl <= 0 then return 0 end
        redis.call('SET', KEYS[1], ARGV[2], 'PX', ttl)
        return 1
        """
        expected_payload = json.dumps(
            expected, ensure_ascii=False, separators=(",", ":")
        )
        value_payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return bool(
            self._run_with_fallback(
                lambda client: client.eval(
                    script,
                    1,
                    key,
                    expected_payload,
                    value_payload,
                ),
                fallback=False,
                context=f"compare and set cache key {key}",
            )
        )

    def consume_json_if(
        self,
        key: str,
        *,
        expected: dict[str, Any],
    ) -> Any | None:
        script = """
        local raw = redis.call('GET', KEYS[1])
        if not raw then return nil end
        local current = cjson.decode(raw)
        local expected = cjson.decode(ARGV[1])
        for field, expected_value in pairs(expected) do
            if current[field] ~= expected_value then return nil end
        end
        redis.call('DEL', KEYS[1])
        return raw
        """
        expected_payload = json.dumps(
            expected, ensure_ascii=False, separators=(",", ":")
        )
        raw = self._run_with_fallback(
            lambda client: client.eval(script, 1, key, expected_payload),
            fallback=None,
            context=f"conditionally consume cache key {key}",
        )
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except JSONDecodeError:
            logger.warning("Redis cache payload for key %s is not valid JSON", key)
            return None

    def health_status(self) -> dict[str, Any]:
        if not self.is_enabled():
            return {
                "available": False,
                "degraded": False,
                "enabled": False,
                "status": "disabled",
            }

        available = self._run_with_fallback(
            lambda client: bool(client.ping()),
            fallback=False,
            context="ping redis",
        )
        return {
            "available": available,
            "degraded": not available,
            "enabled": True,
            "status": "up" if available else "down",
        }


redis_cache = RedisCache()
