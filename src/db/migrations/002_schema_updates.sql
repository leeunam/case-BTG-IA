-- ═══════════════════════════════════════════════════════════════════════════
-- Migration 002 — Source cleanup + schema additions
-- Run against existing databases that already have migration 001 applied.
-- Safe to re-run: uses IF NOT EXISTS / ON CONFLICT / DO NOTHING guards.
-- ═══════════════════════════════════════════════════════════════════════════

-- ───────────────────────────────────────────────────────────────────────────
-- 1. Remove deprecated / incorrect sources
-- ───────────────────────────────────────────────────────────────────────────

DELETE FROM source WHERE code IN (
    'cvm_sdi',      -- wrong system: RAD is for public companies, not investment funds
    'anbima',       -- removed: CVM covers all necessary primary offer data for FIIs
    'btg_digital',  -- removed: internal competitor source
    'clube_fii',    -- removed: unstructured, low reliability
    'xp_digital'    -- removed: internal competitor source
);

-- ───────────────────────────────────────────────────────────────────────────
-- 2. Add correct sources
-- ───────────────────────────────────────────────────────────────────────────

INSERT INTO source (code, name, base_url, method, reliability_score, is_canonical) VALUES
    ('cvm_fundos_portal', 'CVM Portal de Fundos',     'https://fundos.cvm.gov.br',  'html', 0.95, TRUE),
    ('b3_ifix',           'B3 IFIX (via Yahoo Finance)', 'https://finance.yahoo.com', 'api',  0.90, FALSE)
ON CONFLICT (code) DO NOTHING;

-- ───────────────────────────────────────────────────────────────────────────
-- 3. offer — add IPO/sequence/rite fields
-- ───────────────────────────────────────────────────────────────────────────

ALTER TABLE offer
    ADD COLUMN IF NOT EXISTS is_ipo            BOOLEAN,
    ADD COLUMN IF NOT EXISTS offer_sequence    INT,
    ADD COLUMN IF NOT EXISTS distribution_rite VARCHAR(30);
-- distribution_rite values: 'rito_ordinario' | 'rito_automatico' | 'esforcos_restritos'

CREATE INDEX IF NOT EXISTS idx_offer_is_ipo            ON offer(is_ipo);
CREATE INDEX IF NOT EXISTS idx_offer_distribution_rite ON offer(distribution_rite);

-- Backfill: sequence 1 = IPO, 2+ = follow-on (approximate — collector should set correctly going forward)
UPDATE offer o
SET offer_sequence = sub.seq
FROM (
    SELECT id, ROW_NUMBER() OVER (PARTITION BY vehicle_id ORDER BY registered_at ASC NULLS LAST) AS seq
    FROM offer
    WHERE vehicle_id IS NOT NULL
) sub
WHERE o.id = sub.id AND o.offer_sequence IS NULL;

UPDATE offer SET is_ipo = (offer_sequence = 1) WHERE is_ipo IS NULL AND offer_sequence IS NOT NULL;

-- ───────────────────────────────────────────────────────────────────────────
-- 4. vehicle — add fund_type + gestor/administrador FK shortcuts
-- ───────────────────────────────────────────────────────────────────────────

ALTER TABLE vehicle
    ADD COLUMN IF NOT EXISTS fund_type         VARCHAR(20),
    ADD COLUMN IF NOT EXISTS gestor_id         INT REFERENCES participant(id),
    ADD COLUMN IF NOT EXISTS administrador_id  INT REFERENCES participant(id);
-- fund_type values: 'tijolo' | 'papel' | 'fof' | 'desenvolvimento' | 'hibrido' | 'outros'

CREATE INDEX IF NOT EXISTS idx_vehicle_fund_type     ON vehicle(fund_type);
CREATE INDEX IF NOT EXISTS idx_vehicle_gestor        ON vehicle(gestor_id);
CREATE INDEX IF NOT EXISTS idx_vehicle_administrador ON vehicle(administrador_id);

-- ───────────────────────────────────────────────────────────────────────────
-- 5. alert_log — extend allowed types (comment only — no constraint to update)
-- ───────────────────────────────────────────────────────────────────────────
-- New alert types added in this migration:
--   data_inconsistency  → DY divergence > 0.5pp between two secondary sources
--   collection_failed   → extraction_run.status = 'failed' now also writes alert_log
--   source_stale        → source not updated within expected window
-- These are written by the pipeline; no schema change required.
