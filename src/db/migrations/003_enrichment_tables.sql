-- ═══════════════════════════════════════════════════════════════════════════
-- Migration 003 — Enrichment tables for Status Invest and Funds Explorer
-- Safe to re-run: all statements use IF NOT EXISTS / ADD COLUMN IF NOT EXISTS.
-- ═══════════════════════════════════════════════════════════════════════════

-- ───────────────────────────────────────────────────────────────────────────
-- 1. dividend_payment — individual dividend payment records (Status Invest)
--    One row per (vehicle, ex_date, source). Enables custom DY for any window.
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS dividend_payment (
    id             SERIAL PRIMARY KEY,
    vehicle_id     INT            NOT NULL REFERENCES vehicle(id) ON DELETE CASCADE,
    ex_date        DATE           NOT NULL,
    payment_date   DATE,
    value_per_unit NUMERIC(12, 8) NOT NULL,
    dividend_type  VARCHAR(40)    NOT NULL DEFAULT 'rendimento',
    -- rendimento | amortizacao | juros_capital_proprio | rendimento_tributavel
    source_id      INT            REFERENCES source(id),
    UNIQUE (vehicle_id, ex_date, source_id)
);

CREATE INDEX IF NOT EXISTS idx_dividend_vehicle_date ON dividend_payment(vehicle_id, ex_date DESC);
CREATE INDEX IF NOT EXISTS idx_dividend_source       ON dividend_payment(source_id);

-- ───────────────────────────────────────────────────────────────────────────
-- 2. daily_snapshot — new columns for Funds Explorer enrichment
-- ───────────────────────────────────────────────────────────────────────────

ALTER TABLE daily_snapshot
    ADD COLUMN IF NOT EXISTS volume_daily    NUMERIC(22, 2),  -- average daily trading volume (BRL)
    ADD COLUMN IF NOT EXISTS nav_per_unit    NUMERIC(12, 4),  -- valor patrimonial da cota
    ADD COLUMN IF NOT EXISTS monthly_return  NUMERIC(8, 4);   -- rentabilidade no mês (%)
