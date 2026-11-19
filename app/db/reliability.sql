CREATE TABLE IF NOT EXISTS operations (
    scope TEXT NOT NULL,
    operation_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,

    status TEXT NOT NULL
        CHECK (status IN ('processing', 'completed', 'unknown')),

    response_json TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (scope, operation_key)
);

CREATE TABLE IF NOT EXISTS processed_payment_events (
    event_id TEXT PRIMARY KEY,
    request_hash TEXT NOT NULL,
    payment_id TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (payment_id)
        REFERENCES payments(payment_id)
);

CREATE TABLE IF NOT EXISTS audit_events (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,

    actor_ref TEXT NOT NULL,
    action TEXT NOT NULL,
    outcome TEXT NOT NULL,
    request_id TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_operations_status
ON operations(status);

CREATE INDEX IF NOT EXISTS idx_audit_actor
ON audit_events(actor_ref);
CREATE TABLE IF NOT EXISTS idempotency_records (
    customer_id TEXT NOT NULL,
    operation_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    response_json TEXT NOT NULL,
    PRIMARY KEY (customer_id, operation_key)
);
