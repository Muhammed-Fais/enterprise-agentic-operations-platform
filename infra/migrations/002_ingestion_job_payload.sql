ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS external_id TEXT;
ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS content TEXT;
ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS allowed_subjects TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS max_attempts INTEGER NOT NULL DEFAULT 3;

CREATE INDEX IF NOT EXISTS ingestion_jobs_status_idx
    ON ingestion_jobs (status, created_at);
