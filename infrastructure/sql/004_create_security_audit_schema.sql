-- Kelvin Assistant v0.8 security audit logging schema.
--
-- Stores InputGuard and OutputGuard decisions to connect n8n workflow runs,
-- Kelvin agent runs, and tool executions while keeping secrets masked.

BEGIN;

CREATE TABLE IF NOT EXISTS security_audit_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    correlation_id uuid,
    run_id uuid REFERENCES agent_runs(id) ON DELETE SET NULL,
    event_type text NOT NULL, -- 'input_guard', 'output_guard'
    decision text NOT NULL, -- 'allow', 'block'
    masked_content text,
    warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT security_audit_logs_event_type_allowed
        CHECK (event_type IN ('input_guard', 'output_guard')),
    CONSTRAINT security_audit_logs_decision_allowed
        CHECK (decision IN ('allow', 'block'))
);

CREATE INDEX IF NOT EXISTS ix_security_audit_logs_correlation_id
    ON security_audit_logs (correlation_id);

CREATE INDEX IF NOT EXISTS ix_security_audit_logs_run_id
    ON security_audit_logs (run_id);

CREATE INDEX IF NOT EXISTS ix_security_audit_logs_created_at
    ON security_audit_logs (created_at);

COMMIT;
