CREATE TABLE IF NOT EXISTS customer_communications (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    channel VARCHAR(20) NOT NULL DEFAULT 'WHATSAPP',
    event_type VARCHAR(40) NOT NULL,
    recipient VARCHAR(80) NOT NULL,
    message TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'OPENED',
    created_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_customer_communications_order_id
    ON customer_communications(order_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_customer_communications_event_type
    ON customer_communications(event_type, created_at DESC);
