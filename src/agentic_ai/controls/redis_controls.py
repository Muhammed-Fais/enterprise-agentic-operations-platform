from datetime import UTC, datetime

from redis.asyncio import Redis


class RateLimitExceeded(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = max(retry_after, 1)
        super().__init__("rate limit exceeded")


class BudgetExceeded(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = max(retry_after, 1)
        super().__init__("workflow budget exceeded")


class RedisControlsUnavailable(Exception):
    pass


class RedisControls:
    """Atomic Redis controls for abuse protection and bounded workflow spend."""

    _WINDOW_SCRIPT = """
    local current = redis.call('INCRBY', KEYS[1], ARGV[1])
    if current == tonumber(ARGV[1]) then
        redis.call('EXPIRE', KEYS[1], ARGV[2])
    end
    return {current, redis.call('TTL', KEYS[1])}
    """
    _BUDGET_SCRIPT = """
    local current = redis.call('INCRBY', KEYS[1], ARGV[1])
    if current == tonumber(ARGV[1]) then
        redis.call('EXPIRE', KEYS[1], ARGV[3])
    end
    if current > tonumber(ARGV[2]) then
        redis.call('DECRBY', KEYS[1], ARGV[1])
        return {-1, redis.call('TTL', KEYS[1])}
    end
    return {current, redis.call('TTL', KEYS[1])}
    """

    def __init__(
        self,
        redis: Redis,
        *,
        requests_per_minute: int = 60,
        agent_budget_per_day: int = 100,
    ):
        self.redis = redis
        self.requests_per_minute = requests_per_minute
        self.agent_budget_per_day = agent_budget_per_day

    async def enforce_rate_limit(self, tenant_id: str, subject_id: str, route: str) -> None:
        now = datetime.now(UTC)
        window = now.strftime("%Y%m%d%H%M")
        key = f"controls:rate:{tenant_id}:{subject_id}:{route}:{window}"
        try:
            result = await self.redis.eval(self._WINDOW_SCRIPT, 1, key, 1, 60)
        except Exception as exc:
            raise RedisControlsUnavailable("rate-limit store unavailable") from exc
        count, ttl = int(result[0]), int(result[1])
        if count > self.requests_per_minute:
            raise RateLimitExceeded(ttl)

    async def reserve_agent_budget(self, tenant_id: str, *, units: int = 1) -> None:
        day = datetime.now(UTC).strftime("%Y%m%d")
        key = f"controls:budget:{tenant_id}:agent:{day}"
        try:
            result = await self.redis.eval(
                self._BUDGET_SCRIPT,
                1,
                key,
                units,
                self.agent_budget_per_day,
                86400,
            )
        except Exception as exc:
            raise RedisControlsUnavailable("budget store unavailable") from exc
        if int(result[0]) == -1:
            raise BudgetExceeded(int(result[1]))
