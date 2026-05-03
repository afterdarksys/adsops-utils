-- Agent identity and token tables

CREATE TABLE IF NOT EXISTS agents (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id      VARCHAR(100) NOT NULL UNIQUE,  -- human-readable, e.g. "kai_nakamura"
    type          VARCHAR(20)  NOT NULL CHECK (type IN ('agent', 'service')),
    display_name  VARCHAR(255) NOT NULL,
    capabilities  TEXT[]       NOT NULL DEFAULT '{}',
    role          VARCHAR(20)  NOT NULL DEFAULT 'viewer'
                                CHECK (role IN ('viewer', 'operator', 'approver', 'admin')),
    active        BOOLEAN      NOT NULL DEFAULT TRUE,
    webhook_url   TEXT,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_tokens (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id     UUID         NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    token_hash   VARCHAR(255) NOT NULL UNIQUE,
    label        VARCHAR(255) NOT NULL DEFAULT '',
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    expires_at   TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    revoked_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_agent_tokens_agent_id ON agent_tokens(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_tokens_token_hash ON agent_tokens(token_hash);

-- Additive column on tickets — assigned_to remains, this adds type discrimination
ALTER TABLE tickets
    ADD COLUMN IF NOT EXISTS assigned_to_type VARCHAR(20)
        CHECK (assigned_to_type IN ('user', 'agent', 'service'));
