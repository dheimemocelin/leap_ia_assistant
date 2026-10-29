CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS customers (
    id uuid PRIMARY KEY,
    tenant_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);

CREATE TABLE IF NOT EXISTS conversations (
    id uuid PRIMARY KEY,
    tenant_id text NOT NULL,
    customer_id uuid REFERENCES customers(id),
    channel text NOT NULL CHECK (channel IN ('web', 'whatsapp')),
    external_thread_ref text NOT NULL,
    status text NOT NULL DEFAULT 'open',
    assigned_team text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, channel, external_thread_ref)
);

CREATE TABLE IF NOT EXISTS messages (
    id uuid PRIMARY KEY,
    conversation_id uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    direction text NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    channel text NOT NULL,
    provider_message_id text,
    body_ciphertext text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (channel, provider_message_id)
);

CREATE TABLE IF NOT EXISTS events (
    id uuid PRIMARY KEY,
    tenant_id text NOT NULL,
    conversation_id uuid REFERENCES conversations(id) ON DELETE CASCADE,
    event_type text NOT NULL,
    actor text NOT NULL,
    correlation_id text NOT NULL,
    schema_version integer NOT NULL DEFAULT 1,
    payload_minimized jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS knowledge_documents (
    id uuid PRIMARY KEY,
    tenant_id text NOT NULL,
    source_ref text NOT NULL,
    domain text NOT NULL,
    version text NOT NULL,
    content_hash text NOT NULL,
    valid_from timestamptz NOT NULL,
    valid_until timestamptz,
    acl jsonb NOT NULL DEFAULT '{}'::jsonb,
    published boolean NOT NULL DEFAULT false,
    UNIQUE (tenant_id, source_ref, version)
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id uuid PRIMARY KEY,
    document_id uuid NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    ordinal integer NOT NULL,
    content text NOT NULL,
    embedding vector(1536),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (document_id, ordinal)
);
CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_hnsw
    ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS agent_runs (
    id uuid PRIMARY KEY,
    conversation_id uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    graph_version text NOT NULL,
    prompt_version text NOT NULL,
    model_id text NOT NULL,
    confidence text NOT NULL,
    source_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
    duration_ms integer,
    cost_microunits bigint,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS leads (
    id uuid PRIMARY KEY,
    tenant_id text NOT NULL,
    conversation_id uuid NOT NULL REFERENCES conversations(id),
    intent text NOT NULL,
    stage text NOT NULL DEFAULT 'new',
    fields_minimized jsonb NOT NULL DEFAULT '{}'::jsonb,
    score smallint CHECK (score BETWEEN 0 AND 100),
    crm_status text NOT NULL DEFAULT 'not_authorized',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS consents (
    id uuid PRIMARY KEY,
    lead_id uuid NOT NULL REFERENCES leads(id),
    purpose text NOT NULL,
    fields_allowed jsonb NOT NULL,
    notice_version text NOT NULL,
    source text NOT NULL,
    granted_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz
);

CREATE TABLE IF NOT EXISTS outbox_jobs (
    id uuid PRIMARY KEY,
    tenant_id text NOT NULL,
    destination text NOT NULL,
    aggregate_id uuid NOT NULL,
    idempotency_key text NOT NULL UNIQUE,
    payload_minimized jsonb NOT NULL,
    status text NOT NULL DEFAULT 'pending',
    attempts integer NOT NULL DEFAULT 0,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    last_error_code text,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Commercial catalog is distinct from technical manual RAG. Only approved,
-- currently valid records are exposed by sales tools.
CREATE TABLE IF NOT EXISTS commercial_vehicles (
    id text PRIMARY KEY,
    model text NOT NULL,
    version text NOT NULL,
    model_year integer CHECK (model_year BETWEEN 2000 AND 2100),
    powertrain text NOT NULL CHECK (powertrain IN ('BEV', 'REEV')),
    specifications jsonb NOT NULL DEFAULT '{}'::jsonb,
    features jsonb NOT NULL DEFAULT '[]'::jsonb,
    standard_equipment jsonb NOT NULL DEFAULT '[]'::jsonb,
    colors jsonb NOT NULL DEFAULT '[]'::jsonb,
    approval_status text NOT NULL DEFAULT 'draft'
      CHECK (approval_status IN ('draft', 'pending_review', 'approved', 'rejected', 'expired')),
    updated_at timestamptz NOT NULL,
    approved_at timestamptz,
    approved_by text,
    CHECK (approval_status <> 'approved' OR (approved_at IS NOT NULL AND approved_by IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS commercial_sources (
    id uuid PRIMARY KEY,
    vehicle_id text NOT NULL REFERENCES commercial_vehicles(id) ON DELETE CASCADE,
    source_url text NOT NULL,
    source_type text NOT NULL,
    retrieved_at timestamptz NOT NULL,
    notes text
);

CREATE TABLE IF NOT EXISTS vehicle_media (
    id text PRIMARY KEY,
    vehicle_id text NOT NULL REFERENCES commercial_vehicles(id) ON DELETE CASCADE,
    version text,
    model_year integer CHECK (model_year BETWEEN 2000 AND 2100),
    color text,
    category text NOT NULL CHECK (category IN ('exterior', 'interior', 'dashboard', 'trunk', 'detail')),
    source_url text NOT NULL,
    storage_uri text,
    rights_basis text NOT NULL,
    provenance text NOT NULL,
    retrieved_at timestamptz NOT NULL,
    approval_status text NOT NULL DEFAULT 'draft'
      CHECK (approval_status IN ('draft', 'pending_review', 'approved', 'rejected', 'expired')),
    approved_at timestamptz,
    approved_by text,
    CHECK (approval_status <> 'approved' OR
      (approved_at IS NOT NULL AND approved_by IS NOT NULL AND storage_uri IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS vehicle_media_search_idx
    ON vehicle_media (vehicle_id, version, model_year, color, category, approval_status);

CREATE TABLE IF NOT EXISTS commercial_offers (
    id text PRIMARY KEY,
    vehicle_id text NOT NULL REFERENCES commercial_vehicles(id) ON DELETE CASCADE,
    audience text,
    amount_brl integer NOT NULL CHECK (amount_brl > 0),
    valid_from date NOT NULL,
    valid_until date NOT NULL,
    source_url text NOT NULL,
    retrieved_at timestamptz NOT NULL,
    approval_status text NOT NULL DEFAULT 'pending_review'
      CHECK (approval_status IN ('draft', 'pending_review', 'approved', 'rejected', 'expired')),
    approved_at timestamptz,
    approved_by text,
    CHECK (valid_until >= valid_from),
    CHECK (approval_status <> 'approved' OR (approved_at IS NOT NULL AND approved_by IS NOT NULL))
);
