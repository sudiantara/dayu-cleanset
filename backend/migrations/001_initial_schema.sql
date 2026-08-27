-- ============================================
-- DAYU CLEANSET LAUNDRY
-- Initial Database Schema
-- ============================================

-- =========================
-- USERS
-- =========================
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'STAFF',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- =========================
-- CUSTOMERS
-- =========================
CREATE TABLE customers (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    phone VARCHAR(30) NOT NULL,
    address TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- =========================
-- SERVICES
-- =========================
CREATE TABLE services (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    pricing_type VARCHAR(20) NOT NULL,
    price NUMERIC(12,2) NOT NULL DEFAULT 0,
    unit VARCHAR(20) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- =========================
-- ORDERS
-- =========================
CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,

    order_number VARCHAR(30) UNIQUE NOT NULL,

    customer_id BIGINT NOT NULL
        REFERENCES customers(id),

    status VARCHAR(30) NOT NULL DEFAULT 'NEW',

    pickup_type VARCHAR(30) NOT NULL DEFAULT 'CUSTOMER_DROP',

    total_weight NUMERIC(10,2) DEFAULT 0,

    subtotal NUMERIC(12,2) NOT NULL DEFAULT 0,
    discount NUMERIC(12,2) NOT NULL DEFAULT 0,
    total NUMERIC(12,2) NOT NULL DEFAULT 0,

    payment_status VARCHAR(20) NOT NULL DEFAULT 'UNPAID',

    notes TEXT,

    created_by BIGINT
        REFERENCES users(id),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);


-- =========================
-- ORDER ITEMS
-- =========================
CREATE TABLE order_items (
    id BIGSERIAL PRIMARY KEY,

    order_id BIGINT NOT NULL
        REFERENCES orders(id)
        ON DELETE CASCADE,

    service_id BIGINT NOT NULL
        REFERENCES services(id),

    description TEXT,

    quantity NUMERIC(10,2) NOT NULL DEFAULT 1,

    weight NUMERIC(10,2),

    price NUMERIC(12,2) NOT NULL DEFAULT 0,

    subtotal NUMERIC(12,2) NOT NULL DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- =========================
-- ORDER STATUS HISTORY
-- =========================
CREATE TABLE order_status_history (
    id BIGSERIAL PRIMARY KEY,

    order_id BIGINT NOT NULL
        REFERENCES orders(id)
        ON DELETE CASCADE,

    status VARCHAR(30) NOT NULL,

    note TEXT,

    changed_by BIGINT
        REFERENCES users(id),

    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- =========================
-- PAYMENTS
-- =========================
CREATE TABLE payments (
    id BIGSERIAL PRIMARY KEY,

    order_id BIGINT NOT NULL
        REFERENCES orders(id)
        ON DELETE CASCADE,

    amount NUMERIC(12,2) NOT NULL,

    payment_method VARCHAR(30) NOT NULL,

    reference_number VARCHAR(100),

    notes TEXT,

    paid_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    created_by BIGINT
        REFERENCES users(id)
);
