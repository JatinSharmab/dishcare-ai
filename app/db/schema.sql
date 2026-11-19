CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    balance_paise INTEGER NOT NULL DEFAULT 0
        CHECK (balance_paise >= 0),
    enabled INTEGER NOT NULL DEFAULT 1
        CHECK (enabled IN (0, 1))
);

CREATE TABLE IF NOT EXISTS packs (
    pack_code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    monthly_fee_paise INTEGER NOT NULL
        CHECK (monthly_fee_paise >= 0)
);

CREATE TABLE IF NOT EXISTS channels (
    channel_code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    monthly_fee_paise INTEGER NOT NULL
        CHECK (monthly_fee_paise >= 0)
);

CREATE TABLE IF NOT EXISTS subscriptions (
    customer_id TEXT PRIMARY KEY,
    pack_code TEXT NOT NULL,
    status TEXT NOT NULL
        CHECK (status IN ('active', 'inactive', 'cancelled')),
    expiry_date TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (pack_code) REFERENCES packs(pack_code)
);

CREATE TABLE IF NOT EXISTS customer_channels (
    customer_id TEXT NOT NULL,
    channel_code TEXT NOT NULL,
    PRIMARY KEY (customer_id, channel_code),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (channel_code) REFERENCES channels(channel_code)
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    amount_paise INTEGER NOT NULL
        CHECK (amount_paise > 0),
    status TEXT NOT NULL
        CHECK (status IN ('success', 'failed', 'pending')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS complaints (
    complaint_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'in_progress', 'resolved')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS technician_bookings (
    booking_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    visit_date TEXT NOT NULL,
    slot TEXT NOT NULL,
    issue TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'booked'
        CHECK (status IN ('booked', 'completed', 'cancelled')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (customer_id, visit_date, slot),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS retention_offers (
    offer_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    description TEXT NOT NULL,
    discount_paise INTEGER NOT NULL
        CHECK (discount_paise >= 0),
    valid_until TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE INDEX IF NOT EXISTS idx_payments_customer
ON payments(customer_id);

CREATE INDEX IF NOT EXISTS idx_complaints_customer
ON complaints(customer_id);

CREATE INDEX IF NOT EXISTS idx_bookings_customer
ON technician_bookings(customer_id);