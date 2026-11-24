"""Distributed fixed-window API admission limits backed by atomic Redis Lua.

No access token, email, user-submitted IP or raw principal key is persisted.
Redis failures raise and the presentation boundary returns 503 (fail closed).
"""

from hashlib import sha256

from redis.asyncio import Redis

from evidenceos.domain.ports.rate_limits import RateLimitDecision

WINDOW_SECONDS = 60
KEY_PREFIX = "evidenceos:api:rate:v1:"

# Check both quotas before incrementing either, atomically across replicas.
# The window starts with the first successful request; keys expire after 60 s.
_CONSUME_SCRIPT = """
local all_count = tonumber(redis.call('GET', KEYS[1]) or '0')
local costly_count = tonumber(redis.call('GET', KEYS[2]) or '0')
local max_all = tonumber(ARGV[1])
local max_costly = tonumber(ARGV[2])
local window = tonumber(ARGV[3])
local is_costly = tonumber(ARGV[4]) == 1
local retry = 0

if all_count >= max_all then
  retry = math.max(retry, redis.call('TTL', KEYS[1]), 1)
end
if is_costly and costly_count >= max_costly then
  retry = math.max(retry, redis.call('TTL', KEYS[2]), 1)
end
if retry > 0 then
  return {0, retry}
end

local new_all = redis.call('INCR', KEYS[1])
if new_all == 1 then redis.call('EXPIRE', KEYS[1], window) end
if is_costly then
  local new_costly = redis.call('INCR', KEYS[2])
  if new_costly == 1 then redis.call('EXPIRE', KEYS[2], window) end
end
return {1, 0}
"""


class RedisApiRateLimiter:
    """One short-lived fixed-window budget per verified principal, per minute."""

    def __init__(self, url: str, password: str) -> None:
        self._redis = Redis.from_url(
            url,
            password=password,
            decode_responses=True,
            socket_connect_timeout=1.5,
            socket_timeout=1.5,
            retry_on_timeout=False,
        )

    async def consume(
        self,
        principal_key: str,
        *,
        maximum: int,
        expensive_maximum: int,
        expensive: bool,
    ) -> RateLimitDecision:
        # Authenticated issuer-scoped keys are already pseudonymous. Hash again
        # to avoid storing the raw principal identifier in Redis key names.
        def key(bucket: str) -> str:
            digest = sha256(f"{bucket}:{principal_key}".encode()).hexdigest()
            return KEY_PREFIX + digest

        reply = await self._redis.eval(
            _CONSUME_SCRIPT,
            2,
            key("all"),
            key("expensive"),
            maximum,
            expensive_maximum,
            WINDOW_SECONDS,
            int(expensive),
        )
        if (
            not isinstance(reply, list)
            or len(reply) != 2
            or type(reply[0]) is not int
            or type(reply[1]) is not int
            or reply[0] not in (0, 1)
            or reply[1] < 0
        ):
            raise RuntimeError("Invalid API rate-limit store response")
        return RateLimitDecision(allowed=reply[0] == 1, retry_after_seconds=reply[1])

    async def aclose(self) -> None:
        await self._redis.aclose()
