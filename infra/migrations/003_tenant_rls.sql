ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS documents_tenant_isolation ON documents;
CREATE POLICY documents_tenant_isolation ON documents
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS document_chunks_tenant_isolation ON document_chunks;
CREATE POLICY document_chunks_tenant_isolation ON document_chunks
    USING (EXISTS (
        SELECT 1 FROM documents d
        WHERE d.id = document_chunks.document_id
          AND d.tenant_id = current_setting('app.tenant_id', true)
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM documents d
        WHERE d.id = document_chunks.document_id
          AND d.tenant_id = current_setting('app.tenant_id', true)
    ));

ALTER TABLE ingestion_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingestion_jobs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ingestion_jobs_tenant_isolation ON ingestion_jobs;
CREATE POLICY ingestion_jobs_tenant_isolation ON ingestion_jobs
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS audit_events_tenant_isolation ON audit_events;
CREATE POLICY audit_events_tenant_isolation ON audit_events
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE tool_approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE tool_approvals FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tool_approvals_tenant_isolation ON tool_approvals;
CREATE POLICY tool_approvals_tenant_isolation ON tool_approvals
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE idempotency_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE idempotency_records FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS idempotency_records_tenant_isolation ON idempotency_records;
CREATE POLICY idempotency_records_tenant_isolation ON idempotency_records
    USING (tenant_id = current_setting('app.tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
