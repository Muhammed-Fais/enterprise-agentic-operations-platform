import asyncio
import os
from uuid import UUID

from agentic_ai.api.dependencies import get_redis
from agentic_ai.config import get_settings
from agentic_ai.db.session import session_factory, set_tenant_context
from agentic_ai.embeddings import LocalSentenceTransformerEmbedder
from agentic_ai.ingestion import IngestionQueue, IngestionService
from agentic_ai.ingestion.jobs import (
    get_ingestion_job,
    mark_job_completed,
    mark_job_failed,
    mark_job_running,
)


async def process_job(
    job_id: UUID, tenant_id: str, embedder: LocalSentenceTransformerEmbedder
) -> bool:
    async with session_factory() as session:
        await set_tenant_context(session, tenant_id)
        job = await get_ingestion_job(session, job_id, tenant_id)
        if job is None:
            return True
        if not await mark_job_running(session, job_id):
            return True
        try:
            await IngestionService(session, embedder).ingest(
                job.document,
                tenant_id=job.tenant_id,
                allowed_subjects=job.allowed_subjects,
                metadata=job.metadata,
            )
            await mark_job_completed(session, job_id)
            return True
        except Exception as exc:  # noqa: BLE001 - worker must persist every job failure
            await session.rollback()
            terminal = await mark_job_failed(session, job_id, str(exc))
            return terminal


async def run_worker() -> None:
    settings = get_settings()
    queue = IngestionQueue(get_redis())
    consumer = os.getenv("INGESTION_WORKER_CONSUMER", "worker-1")
    embedder = LocalSentenceTransformerEmbedder(settings.embedding_model)
    while True:
        for message_id, fields in await queue.read(consumer):
            raw_job_id = fields.get(b"job_id") or fields.get("job_id")
            if not raw_job_id:
                await queue.ack(message_id)
                continue
            raw_tenant_id = fields.get(b"tenant_id") or fields.get("tenant_id")
            if not raw_tenant_id:
                await queue.ack(message_id)
                continue
            job_id = UUID(raw_job_id.decode() if isinstance(raw_job_id, bytes) else raw_job_id)
            tenant_id = raw_tenant_id.decode() if isinstance(raw_tenant_id, bytes) else raw_tenant_id
            terminal = await process_job(job_id, tenant_id, embedder)
            if terminal:
                await queue.ack(message_id)
            else:
                await queue.enqueue(job_id, tenant_id)
                await queue.ack(message_id)


if __name__ == "__main__":
    asyncio.run(run_worker())
