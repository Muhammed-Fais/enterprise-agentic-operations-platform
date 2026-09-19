from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import ResponseError


class IngestionQueue:
    def __init__(
        self,
        redis: Redis,
        *,
        stream: str = "agentic:ingestion:jobs",
        group: str = "ingestion-workers",
    ):
        self.redis = redis
        self.stream = stream
        self.group = group

    async def ensure_group(self) -> None:
        try:
            await self.redis.xgroup_create(self.stream, self.group, id="0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def enqueue(self, job_id: UUID | str, tenant_id: str) -> str:
        return await self.redis.xadd(
            self.stream,
            {"job_id": str(job_id), "tenant_id": tenant_id},
        )

    async def read(self, consumer: str, *, block_ms: int = 5000) -> list[tuple[str, dict[bytes, bytes]]]:
        await self.ensure_group()
        batches = await self.redis.xreadgroup(
            self.group,
            consumer,
            {self.stream: ">"},
            count=1,
            block=block_ms,
        )
        messages: list[tuple[str, dict[bytes, bytes]]] = []
        for _, entries in batches or []:
            messages.extend(entries)
        return messages

    async def ack(self, message_id: str) -> None:
        await self.redis.xack(self.stream, self.group, message_id)
