import json
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .loaders import LoadedDocument


@dataclass(frozen=True)
class IngestionJob:
    job_id: UUID
    tenant_id: str
    document: LoadedDocument
    allowed_subjects: list[str]
    metadata: dict[str, str]
    attempt_count: int
    max_attempts: int
    status: str
    error_message: str | None = None


async def create_ingestion_job(
    session: AsyncSession,
    *,
    tenant_id: str,
    document: LoadedDocument,
    allowed_subjects: list[str],
    metadata: dict[str, str],
    max_attempts: int = 3,
) -> UUID:
    job_id = uuid4()
    await session.execute(
        text(
            """
            INSERT INTO ingestion_jobs
                (id, tenant_id, source, external_id, title, content, allowed_subjects,
                 metadata, status, max_attempts)
            VALUES
                (:id, :tenant_id, :source, :external_id, :title, :content, :allowed_subjects,
                 CAST(:metadata AS jsonb), 'queued', :max_attempts)
            """
        ),
        {
            "id": job_id,
            "tenant_id": tenant_id,
            "source": document.source,
            "external_id": document.external_id,
            "title": document.title,
            "content": document.content,
            "allowed_subjects": allowed_subjects,
            "metadata": json.dumps(metadata),
            "max_attempts": max_attempts,
        },
    )
    await session.commit()
    return job_id


async def get_ingestion_job(session: AsyncSession, job_id: UUID, tenant_id: str) -> IngestionJob | None:
    row = (
        await session.execute(
            text("SELECT * FROM ingestion_jobs WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": job_id, "tenant_id": tenant_id},
        )
    ).mappings().first()
    if not row:
        return None
    return IngestionJob(
        job_id=row["id"],
        tenant_id=row["tenant_id"],
        document=LoadedDocument(
            external_id=row["external_id"],
            title=row["title"],
            source=row["source"],
            content=row["content"],
        ),
        allowed_subjects=list(row["allowed_subjects"] or []),
        metadata=dict(row["metadata"] or {}),
        attempt_count=row["attempt_count"],
        max_attempts=row["max_attempts"],
        status=row["status"],
        error_message=row["error_message"],
    )


async def get_ingestion_job_by_id(session: AsyncSession, job_id: UUID) -> IngestionJob | None:
    row = (
        await session.execute(
            text("SELECT * FROM ingestion_jobs WHERE id = :id"),
            {"id": job_id},
        )
    ).mappings().first()
    if not row:
        return None
    return await get_ingestion_job(session, job_id, row["tenant_id"])


async def mark_job_running(session: AsyncSession, job_id: UUID) -> bool:
    result = await session.execute(
        text(
            """
            UPDATE ingestion_jobs
            SET status = 'running', attempt_count = attempt_count + 1, started_at = now(), error_message = NULL
            WHERE id = :id AND status = 'queued'
            RETURNING id
            """
        ),
        {"id": job_id},
    )
    await session.commit()
    return result.scalar_one_or_none() is not None


async def mark_job_completed(session: AsyncSession, job_id: UUID) -> None:
    await session.execute(
        text(
            "UPDATE ingestion_jobs SET status = 'completed', documents_processed = 1, finished_at = now() WHERE id = :id"
        ),
        {"id": job_id},
    )
    await session.commit()


async def mark_job_failed(session: AsyncSession, job_id: UUID, error_message: str) -> bool:
    result = await session.execute(
        text(
            """
            UPDATE ingestion_jobs
            SET status = CASE WHEN attempt_count >= max_attempts THEN 'failed' ELSE 'queued' END,
                error_message = :error_message,
                finished_at = CASE WHEN attempt_count >= max_attempts THEN now() ELSE NULL END
            WHERE id = :id
            RETURNING status
            """
        ),
        {"id": job_id, "error_message": error_message[:1000]},
    )
    await session.commit()
    return result.scalar_one() == "failed"
