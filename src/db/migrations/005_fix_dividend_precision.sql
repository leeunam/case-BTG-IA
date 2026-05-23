-- Migration 005 — Fix dividend_payment.value_per_unit numeric overflow
-- NUMERIC(12,8) overflows for values >= 10000; change to NUMERIC(18,4).
-- Brazilian FII dividends are typically R$0.01–R$10/cota; 4 decimal places is sufficient.

ALTER TABLE dividend_payment
    ALTER COLUMN value_per_unit TYPE NUMERIC(18, 4);
