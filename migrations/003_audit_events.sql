CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    event_name TEXT NOT NULL,
    request_id TEXT NOT NULL REFERENCES requests(request_id),
    decision_code TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS audit_request_idx ON audit_events(request_id);
