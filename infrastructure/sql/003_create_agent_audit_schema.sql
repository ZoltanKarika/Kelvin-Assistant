-- Kelvin Assistant v0.6 persistent agent run and audit schema.
--
-- Current run state is versioned for optimistic concurrency. Tool proposals
-- and execution results are retained as separate rows so an approved write can
-- always be traced back to its exact structured arguments and user decision.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS agent_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    goal text NOT NULL,
    status text NOT NULL,
    step_count integer NOT NULL DEFAULT 0,
    max_steps integer NOT NULL DEFAULT 12,
    version integer NOT NULL DEFAULT 0,
    workspace_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT agent_runs_goal_not_blank
        CHECK (length(trim(goal)) > 0 AND length(goal) <= 8192),
    CONSTRAINT agent_runs_status_allowed
        CHECK (
            status IN (
                'received',
                'clarifying',
                'planning',
                'awaiting_approval',
                'executing',
                'observing',
                'completed',
                'cancelled',
                'failed'
            )
        ),
    CONSTRAINT agent_runs_step_count_range
        CHECK (step_count >= 0 AND step_count <= max_steps),
    CONSTRAINT agent_runs_max_steps_range
        CHECK (max_steps >= 1 AND max_steps <= 100),
    CONSTRAINT agent_runs_version_non_negative
        CHECK (version >= 0),
    CONSTRAINT agent_runs_workspace_id_valid
        CHECK (
            workspace_id IS NULL
            OR workspace_id ~ '^[a-z][a-z0-9_-]{0,63}$'
        )
);

CREATE INDEX IF NOT EXISTS ix_agent_runs_created_at
    ON agent_runs (created_at);

CREATE INDEX IF NOT EXISTS ix_agent_runs_status_updated_at
    ON agent_runs (status, updated_at);

CREATE TABLE IF NOT EXISTS agent_tool_proposals (
    tool_call_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    tool_name text NOT NULL,
    arguments jsonb NOT NULL DEFAULT '{}'::jsonb,
    reason text NOT NULL,
    expected_effect text NOT NULL,
    risk text NOT NULL,
    policy_decision text NOT NULL,
    policy_reason text NOT NULL,
    approval_status text,
    approval_decided_by text,
    approval_decided_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    closed_at timestamptz,
    CONSTRAINT agent_tool_proposals_name_valid
        CHECK (
            tool_name ~ '^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$'
        ),
    CONSTRAINT agent_tool_proposals_arguments_is_object
        CHECK (jsonb_typeof(arguments) = 'object'),
    CONSTRAINT agent_tool_proposals_reason_not_blank
        CHECK (length(trim(reason)) > 0 AND length(reason) <= 2048),
    CONSTRAINT agent_tool_proposals_expected_effect_not_blank
        CHECK (
            length(trim(expected_effect)) > 0
            AND length(expected_effect) <= 2048
        ),
    CONSTRAINT agent_tool_proposals_risk_allowed
        CHECK (risk IN ('read', 'write', 'destructive', 'privileged')),
    CONSTRAINT agent_tool_proposals_policy_decision_allowed
        CHECK (
            policy_decision IN ('allow', 'require_approval', 'deny')
        ),
    CONSTRAINT agent_tool_proposals_policy_reason_not_blank
        CHECK (length(trim(policy_reason)) > 0),
    CONSTRAINT agent_tool_proposals_approval_status_allowed
        CHECK (
            approval_status IS NULL
            OR approval_status IN ('pending', 'approved', 'rejected')
        ),
    CONSTRAINT agent_tool_proposals_policy_approval_consistent
        CHECK (
            (
                policy_decision = 'require_approval'
                AND approval_status IS NOT NULL
            )
            OR (
                policy_decision <> 'require_approval'
                AND approval_status IS NULL
            )
        ),
    CONSTRAINT agent_tool_proposals_approval_metadata_consistent
        CHECK (
            (
                approval_status IS NULL
                AND approval_decided_by IS NULL
                AND approval_decided_at IS NULL
            )
            OR (
                approval_status = 'pending'
                AND approval_decided_by IS NULL
                AND approval_decided_at IS NULL
            )
            OR (
                approval_status IN ('approved', 'rejected')
                AND approval_decided_by IS NOT NULL
                AND length(trim(approval_decided_by)) > 0
                AND approval_decided_at IS NOT NULL
            )
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_agent_tool_proposals_run_call
    ON agent_tool_proposals (run_id, tool_call_id);

CREATE UNIQUE INDEX IF NOT EXISTS ux_agent_tool_proposals_run_call_name
    ON agent_tool_proposals (run_id, tool_call_id, tool_name);

CREATE UNIQUE INDEX IF NOT EXISTS ux_agent_tool_proposals_active_run
    ON agent_tool_proposals (run_id)
    WHERE closed_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_agent_tool_proposals_run_created_at
    ON agent_tool_proposals (run_id, created_at);

CREATE TABLE IF NOT EXISTS agent_tool_results (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL,
    tool_call_id uuid NOT NULL,
    tool_name text NOT NULL,
    succeeded boolean NOT NULL,
    output text NOT NULL DEFAULT '',
    error text,
    truncated boolean NOT NULL DEFAULT false,
    duration_ms integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT agent_tool_results_proposal_fk
        FOREIGN KEY (run_id, tool_call_id, tool_name)
        REFERENCES agent_tool_proposals (run_id, tool_call_id, tool_name)
        ON DELETE CASCADE,
    CONSTRAINT agent_tool_results_name_valid
        CHECK (
            tool_name ~ '^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$'
        ),
    CONSTRAINT agent_tool_results_duration_non_negative
        CHECK (duration_ms >= 0),
    CONSTRAINT agent_tool_results_output_bounded
        CHECK (length(output) <= 32768),
    CONSTRAINT agent_tool_results_error_bounded
        CHECK (error IS NULL OR length(error) <= 32768),
    CONSTRAINT agent_tool_results_success_consistent
        CHECK (
            (succeeded AND error IS NULL)
            OR (
                NOT succeeded
                AND error IS NOT NULL
                AND length(trim(error)) > 0
            )
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_agent_tool_results_tool_call
    ON agent_tool_results (tool_call_id);

CREATE INDEX IF NOT EXISTS ix_agent_tool_results_run_created_at
    ON agent_tool_results (run_id, created_at);

COMMIT;
