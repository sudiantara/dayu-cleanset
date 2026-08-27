-- ============================================
-- DAYU CLEANSET LAUNDRY
-- Order Traveler / Hotel Fields
-- Normal / Express / Promo / Special Discount
-- ============================================


-- =========================
-- LOCATION
-- =========================

ALTER TABLE orders
ADD COLUMN hotel_name VARCHAR(150);

ALTER TABLE orders
ADD COLUMN room_number VARCHAR(50);

ALTER TABLE orders
ADD COLUMN location_notes TEXT;


-- =========================
-- SERVICE SPEED
-- =========================

ALTER TABLE orders
ADD COLUMN service_speed VARCHAR(20)
NOT NULL DEFAULT 'NORMAL';


-- =========================
-- REQUESTED FINISH TIME
-- =========================

ALTER TABLE orders
ADD COLUMN requested_finish_at TIMESTAMPTZ;


-- =========================
-- PROMO
-- =========================

ALTER TABLE orders
ADD COLUMN instagram_followed BOOLEAN
NOT NULL DEFAULT FALSE;

ALTER TABLE orders
ADD COLUMN google_reviewed BOOLEAN
NOT NULL DEFAULT FALSE;

ALTER TABLE orders
ADD COLUMN promo_discount NUMERIC(12,2)
NOT NULL DEFAULT 0;


-- =========================
-- SPECIAL / NEGOTIATED DISCOUNT
-- =========================

ALTER TABLE orders
ADD COLUMN special_discount NUMERIC(12,2)
NOT NULL DEFAULT 0;

ALTER TABLE orders
ADD COLUMN special_discount_reason TEXT;


-- =========================
-- VALIDATION
-- =========================

ALTER TABLE orders
ADD CONSTRAINT orders_service_speed_check
CHECK (
    service_speed IN ('NORMAL', 'EXPRESS')
);

ALTER TABLE orders
ADD CONSTRAINT orders_promo_discount_non_negative
CHECK (
    promo_discount >= 0
);

ALTER TABLE orders
ADD CONSTRAINT orders_special_discount_non_negative
CHECK (
    special_discount >= 0
);
