-- ============================================
-- DAYU CLEANSET LAUNDRY
-- Step 23A - Expenses / Business Finance
-- ============================================

CREATE TABLE IF NOT EXISTS expenses (
    id BIGSERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    description VARCHAR(200) NOT NULL,
    amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    expense_date DATE NOT NULL DEFAULT CURRENT_DATE,
    notes TEXT,
    created_by BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_expenses_expense_date
    ON expenses(expense_date DESC);

CREATE INDEX IF NOT EXISTS idx_expenses_category
    ON expenses(category);
