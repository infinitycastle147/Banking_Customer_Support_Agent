PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS synthetic_transactions (
    transaction_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS disputes (
    dispute_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    transaction_id TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    status TEXT NOT NULL,
    version INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS requests (
    request_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    verification_reference TEXT NOT NULL,
    verification_method TEXT NOT NULL,
    verified_at TEXT NOT NULL,
    action TEXT NOT NULL,
    target_id TEXT NOT NULL,
    expected_version INTEGER NOT NULL,
    reason_code TEXT NOT NULL,
    customer_statement TEXT NOT NULL,
    consent_reference TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    command_digest TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    state TEXT NOT NULL,
    result_code TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (customer_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS outbox (
    event_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL UNIQUE REFERENCES requests(request_id),
    state TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS dispute_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    dispute_id TEXT NOT NULL REFERENCES disputes(dispute_id),
    request_id TEXT NOT NULL UNIQUE REFERENCES requests(request_id),
    action TEXT NOT NULL,
    customer_statement TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL UNIQUE REFERENCES requests(request_id),
    customer_id TEXT NOT NULL,
    dispute_id TEXT NOT NULL,
    requested_action TEXT NOT NULL,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS requests_customer_created_idx
    ON requests(customer_id, created_at);
CREATE INDEX IF NOT EXISTS requests_target_created_idx
    ON requests(customer_id, target_id, created_at);
CREATE INDEX IF NOT EXISTS outbox_state_idx ON outbox(state);
