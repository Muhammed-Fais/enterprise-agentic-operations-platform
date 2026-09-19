from uuid import uuid4

import pytest

from agentic_ai.ingestion import IngestionQueue


class FakeRedis:
    def __init__(self) -> None:
        self.created = False
        self.enqueued: list[tuple[str, dict[str, str]]] = []
        self.acked: list[str] = []

    async def xgroup_create(self, stream: str, group: str, *, id: str, mkstream: bool) -> None:
        self.created = True

    async def xadd(self, stream: str, fields: dict[str, str]) -> str:
        self.enqueued.append((stream, fields))
        return "1-0"

    async def xreadgroup(self, group: str, consumer: str, streams: dict[str, str], *, count: int, block: int):
        return []

    async def xack(self, stream: str, group: str, message_id: str) -> None:
        self.acked.append(message_id)


@pytest.mark.asyncio
async def test_ingestion_queue_creates_group_and_enqueues_job() -> None:
    redis = FakeRedis()
    queue = IngestionQueue(redis)
    job_id = uuid4()

    await queue.enqueue(job_id, "tenant-a")

    assert redis.created is False
    await queue.ensure_group()
    assert redis.created
    assert redis.enqueued == [
        ("agentic:ingestion:jobs", {"job_id": str(job_id), "tenant_id": "tenant-a"})
    ]
