CREATE TABLE IF NOT EXISTS synthetic_transaction_facts (
    transaction_id TEXT PRIMARY KEY REFERENCES synthetic_transactions(transaction_id),
    masked_account TEXT NOT NULL,
    merchant TEXT NOT NULL,
    amount TEXT NOT NULL,
    currency TEXT NOT NULL,
    status TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);
