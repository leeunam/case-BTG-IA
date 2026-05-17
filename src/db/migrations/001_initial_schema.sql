-- ═══════════════════════════════════════════════════════════════════════════
-- BTG FII Analyzer — Schema inicial
-- Supabase já tem pgvector habilitado por padrão.
-- ═══════════════════════════════════════════════════════════════════════════

CREATE EXTENSION IF NOT EXISTS vector;

-- ───────────────────────────────────────────────────────────────────────────
-- CLASSIFICAÇÃO
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS asset_class (
    id   SERIAL PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    name TEXT        NOT NULL
);

INSERT INTO asset_class (code, name) VALUES
    ('FII',           'Fundo de Investimento Imobiliário'),
    ('STOCK',         'Ação'),
    ('DEBENTURE',     'Debênture'),
    ('CRI',           'Certificado de Recebíveis Imobiliários'),
    ('CRA',           'Certificado de Recebíveis do Agronegócio'),
    ('FIDC',          'Fundo de Investimento em Direitos Creditórios'),
    ('NOTA_COMERCIAL','Nota Comercial')
ON CONFLICT (code) DO NOTHING;

CREATE TABLE IF NOT EXISTS security_type (
    id             SERIAL PRIMARY KEY,
    asset_class_id INT  NOT NULL REFERENCES asset_class(id),
    code           VARCHAR(30) UNIQUE NOT NULL,
    name           TEXT NOT NULL
);

INSERT INTO security_type (asset_class_id, code, name)
SELECT ac.id, v.code, v.name
FROM (VALUES
    ('FII',   'fii_ipo',         'IPO de FII'),
    ('FII',   'fii_follow_on',   'Follow-on de FII'),
    ('FII',   'fii_restricted',  'Oferta Restrita de FII (ICVM 476)'),
    ('STOCK', 'stock_ipo',       'IPO de Ação'),
    ('STOCK', 'stock_follow_on', 'Follow-on de Ação')
) AS v(ac_code, code, name)
JOIN asset_class ac ON ac.code = v.ac_code
ON CONFLICT (code) DO NOTHING;

-- ───────────────────────────────────────────────────────────────────────────
-- ENTIDADES
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS issuer (
    id         SERIAL PRIMARY KEY,
    cnpj       VARCHAR(18) UNIQUE,
    name       TEXT        NOT NULL,
    type       VARCHAR(30),           -- gestora | administradora | emissor_direto
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS vehicle (
    id             SERIAL  PRIMARY KEY,
    issuer_id      INT     REFERENCES issuer(id),
    asset_class_id INT     NOT NULL REFERENCES asset_class(id),
    ticker         VARCHAR(10),
    cvm_code       VARCHAR(20),
    name           TEXT    NOT NULL,
    segment        VARCHAR(50),       -- logistica | shoppings | lajes | papel | hibrido | fof | outros
    is_active      BOOLEAN DEFAULT TRUE,
    extra          JSONB   DEFAULT '{}',
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    updated_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_vehicle_ticker   ON vehicle(ticker)   WHERE ticker   IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_vehicle_cvm_code ON vehicle(cvm_code) WHERE cvm_code IS NOT NULL;
CREATE        INDEX IF NOT EXISTS idx_vehicle_ac       ON vehicle(asset_class_id);

-- ───────────────────────────────────────────────────────────────────────────
-- OFERTAS
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS offer (
    id                        SERIAL  PRIMARY KEY,
    vehicle_id                INT     REFERENCES vehicle(id),
    security_type_id          INT     REFERENCES security_type(id),
    cvm_registration          VARCHAR(80) UNIQUE,
    cvm_process_number        VARCHAR(80),
    status                    VARCHAR(20) NOT NULL DEFAULT 'unknown',
    -- pending | active | closed | cancelled | unknown
    started_at                DATE,
    ends_at                   DATE,
    registered_at             DATE,
    total_volume              NUMERIC(22, 2),
    unit_price                NUMERIC(14, 4),
    total_units               BIGINT,
    distribution_regime       VARCHAR(50),
    -- garantia_firme | melhores_esforcos
    bookbuilding              BOOLEAN,
    target_audience           VARCHAR(30),
    -- profissional | qualificado | geral
    financial_terms_available BOOLEAN DEFAULT TRUE,
    financial_terms_note      TEXT,
    extra                     JSONB   DEFAULT '{}',
    created_at                TIMESTAMPTZ DEFAULT NOW(),
    updated_at                TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_offer_vehicle      ON offer(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_offer_status       ON offer(status);
CREATE INDEX IF NOT EXISTS idx_offer_started_at   ON offer(started_at);
CREATE INDEX IF NOT EXISTS idx_offer_registered   ON offer(registered_at);

CREATE TABLE IF NOT EXISTS tranche (
    id             SERIAL PRIMARY KEY,
    offer_id       INT    NOT NULL REFERENCES offer(id) ON DELETE CASCADE,
    name           VARCHAR(60),       -- institucional | varejo | fundo_exclusivo
    volume         NUMERIC(22, 2),
    units          BIGINT,
    min_investment NUMERIC(16, 2)
);

-- ───────────────────────────────────────────────────────────────────────────
-- PARTICIPANTES
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS participant (
    id         SERIAL PRIMARY KEY,
    cnpj       VARCHAR(18) UNIQUE,
    name       TEXT NOT NULL,
    short_name VARCHAR(60),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS participant_role (
    id             SERIAL PRIMARY KEY,
    offer_id       INT NOT NULL REFERENCES offer(id)        ON DELETE CASCADE,
    participant_id INT NOT NULL REFERENCES participant(id),
    role           VARCHAR(40) NOT NULL,
    -- coordinator_leader | coordinator | distributor | manager | administrator | auditor | legal
    UNIQUE (offer_id, participant_id, role)
);

CREATE INDEX IF NOT EXISTS idx_pr_offer       ON participant_role(offer_id);
CREATE INDEX IF NOT EXISTS idx_pr_participant ON participant_role(participant_id);

-- ───────────────────────────────────────────────────────────────────────────
-- DOCUMENTOS
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS document (
    id                SERIAL PRIMARY KEY,
    offer_id          INT REFERENCES offer(id)   ON DELETE CASCADE,
    vehicle_id        INT REFERENCES vehicle(id),
    type              VARCHAR(50),
    -- prospecto_preliminar | prospecto_definitivo | lamina | fato_relevante | anuncio_encerramento
    source_url        TEXT,
    local_path        TEXT,
    extracted_at      TIMESTAMPTZ,
    extraction_status VARCHAR(20) DEFAULT 'pending',
    -- pending | done | failed | partial
    page_count        INT,
    extra             JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_document_offer ON document(offer_id);

-- ───────────────────────────────────────────────────────────────────────────
-- FONTES E AUDITORIA
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS source (
    id                SERIAL PRIMARY KEY,
    code              VARCHAR(30) UNIQUE NOT NULL,
    name              TEXT        NOT NULL,
    base_url          TEXT,
    method            VARCHAR(20),
    -- api | csv | html | jina | playwright | pdf_llm
    reliability_score NUMERIC(3, 2) DEFAULT 0.80,
    is_canonical      BOOLEAN DEFAULT FALSE
);

INSERT INTO source (code, name, base_url, method, reliability_score, is_canonical) VALUES
    ('cvm_dados_abertos', 'CVM Dados Abertos',    'https://dados.cvm.gov.br',                           'csv',        1.00, TRUE),
    ('cvm_sdi',           'CVM SDI (Documentos)', 'https://www.rad.cvm.gov.br',                         'html',       0.95, TRUE),
    ('b3_listings',       'B3 FII Listings',      'https://sistemaswebb3-listados.b3.com.br',           'api',        0.95, TRUE),
    ('anbima',            'ANBIMA',               'https://data.anbima.com.br',                         'api',        0.90, FALSE),
    ('bcb_sgs',           'BCB SGS',              'https://api.bcb.gov.br',                             'api',        1.00, FALSE),
    ('bcb_focus',         'BCB Relatório Focus',  'https://olinda.bcb.gov.br',                          'api',        1.00, FALSE),
    ('fundamentus',       'Fundamentus FII',      'https://www.fundamentus.com.br',                    'html',       0.85, FALSE),
    ('funds_explorer',    'Funds Explorer',       'https://www.fundsexplorer.com.br',                   'playwright', 0.80, FALSE),
    ('status_invest',     'Status Invest',        'https://statusinvest.com.br',                        'playwright', 0.75, FALSE),
    ('fiis_com_br',       'FIIs.com.br',          'https://fiis.com.br',                                'html',       0.75, FALSE),
    ('btg_digital',       'BTG Digital',          'https://www.btgpactual.com',                         'jina',       0.70, FALSE),
    ('clube_fii',         'Clube FII',            'https://www.clubefii.com.br',                        'playwright', 0.70, FALSE)
ON CONFLICT (code) DO NOTHING;

CREATE TABLE IF NOT EXISTS extraction_run (
    id                SERIAL PRIMARY KEY,
    source_id         INT    NOT NULL REFERENCES source(id),
    started_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at       TIMESTAMPTZ,
    status            VARCHAR(20) DEFAULT 'running',
    -- running | success | partial | failed
    records_collected INT DEFAULT 0,
    records_new       INT DEFAULT 0,
    records_updated   INT DEFAULT 0,
    error_log         TEXT
);

CREATE INDEX IF NOT EXISTS idx_run_source  ON extraction_run(source_id);
CREATE INDEX IF NOT EXISTS idx_run_started ON extraction_run(started_at);

-- ───────────────────────────────────────────────────────────────────────────
-- SÉRIES TEMPORAIS
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS daily_snapshot (
    id            SERIAL PRIMARY KEY,
    vehicle_id    INT    NOT NULL REFERENCES vehicle(id),
    snapshot_date DATE   NOT NULL,
    dy_12m        NUMERIC(10, 4),
    dy_6m         NUMERIC(10, 4),
    dy_3m         NUMERIC(10, 4),
    pvp           NUMERIC(12, 4),  -- widened: Fundamentus has outliers above 9999
    price         NUMERIC(12, 2),
    pl_total      NUMERIC(22, 2),
    vacancy_rate  NUMERIC(6, 2),
    source_id     INT REFERENCES source(id),
    extra         JSONB DEFAULT '{}',
    UNIQUE (vehicle_id, snapshot_date, source_id)
);

CREATE INDEX IF NOT EXISTS idx_snapshot_vehicle_date ON daily_snapshot(vehicle_id, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_snapshot_date         ON daily_snapshot(snapshot_date);

CREATE TABLE IF NOT EXISTS market_metric (
    id          SERIAL PRIMARY KEY,
    code        VARCHAR(20) NOT NULL,
    -- CDI | SELIC | IPCA | IPCA_PROJ | CDI_PROJ | IFIX
    metric_date DATE        NOT NULL,
    value       NUMERIC(14, 6) NOT NULL,
    source_id   INT REFERENCES source(id),
    UNIQUE (code, metric_date, source_id)
);

CREATE INDEX IF NOT EXISTS idx_metric_code_date ON market_metric(code, metric_date);

-- ───────────────────────────────────────────────────────────────────────────
-- ALERTAS
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS alert_log (
    id         SERIAL PRIMARY KEY,
    type       VARCHAR(40) NOT NULL,
    -- new_offer | status_change | new_player | concentration | data_gap
    offer_id   INT REFERENCES offer(id),
    vehicle_id INT REFERENCES vehicle(id),
    detail     JSONB   DEFAULT '{}',
    is_read    BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alert_type    ON alert_log(type);
CREATE INDEX IF NOT EXISTS idx_alert_created ON alert_log(created_at);
CREATE INDEX IF NOT EXISTS idx_alert_unread  ON alert_log(is_read) WHERE NOT is_read;

-- ───────────────────────────────────────────────────────────────────────────
-- EMBEDDINGS — pgvector (Fase 2: schema criado agora, populado depois)
-- ───────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS embedding (
    id           SERIAL PRIMARY KEY,
    offer_id     INT  REFERENCES offer(id)     ON DELETE CASCADE,
    vehicle_id   INT  REFERENCES vehicle(id),
    document_id  INT  REFERENCES document(id),
    content      TEXT NOT NULL,
    embedding    VECTOR(1536),
    section_type VARCHAR(30),
    -- cover | risk | terms | financial | summary | comparative | other
    metadata     JSONB DEFAULT '{}',
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_embedding_offer ON embedding(offer_id);
-- ANN index: create AFTER loading data (needs rows to build lists)
-- CREATE INDEX ON embedding USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
