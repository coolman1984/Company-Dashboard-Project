-- ============================================================================
-- Company Dashboard - canonical SQLite schema (single source of truth)
-- ============================================================================
-- This DDL defines the pl_detail ledger plus the analytical indexes and views
-- the server relies on. It is OS-independent and is applied by both the
-- synthetic seeder (seed_db.py) and any production ingestion path.
--
-- Period encoding: `period` is stored as REAL = year + period_number / 1000
-- (e.g. 2026.001 = FY2026 P01, 2026.012 = FY2026 P12). The server decodes the
-- period number with CAST(ROUND((period - CAST(period AS INTEGER)) * 1000)).
--
-- Version coverage convention:
--   Actual -> realised periods
--   T06    -> the single forecast bridge period P06
--   T07    -> the forward outlook periods P07-P12
-- ============================================================================

DROP TABLE IF EXISTS pl_detail;

CREATE TABLE pl_detail (
    "class"                TEXT,
    region_desc            TEXT,
    country_name           TEXT,
    customer_name          TEXT,
    m_group_desc           TEXT,
    year                   INTEGER,
    class_code             TEXT,
    version                TEXT,
    product_number         TEXT,
    sender_ba              TEXT,
    customer_code          TEXT,
    country_code           TEXT,
    profit_center          TEXT,
    valuation_class        REAL,
    period                 REAL,
    currency               TEXT,
    qty_gross              REAL,
    qty_return             REAL,
    qty_net                REAL,
    s_rrp                  REAL,
    reference_price        REAL,
    dealer_discount        REAL,
    s_base_margin          REAL,
    s_contract_margin      REAL,
    s_additional_margin    REAL,
    s_special_margin       REAL,
    s_gross_sales          REAL,
    s_gross_sales_amt      REAL,
    s_other_sales          REAL,
    s_oth_sales_tax_inc    REAL,
    s_internal_sales_amt   REAL,
    s_return_amt           REAL,
    s_return_amt_alt       REAL,
    ref_sales              REAL,
    s_ifc                  REAL,
    s_fob_sales_amt        REAL,
    sales_deduction        REAL,
    s_sales_allowance      REAL,
    s_rebate               REAL,
    s_cash_discount        REAL,
    s_price_protection     REAL,
    s_coop                 REAL,
    s_sale_deduction_tax   REAL,
    net_sales              REAL,
    cost_of_goods_sold     REAL,
    material_cost          REAL,
    gross_margin           REAL,
    operating_expense      REAL,
    sales_expense          REAL,
    operating_profit       REAL,
    profit_before_tax      REAL,
    corporate_tax          REAL,
    corp_tax               REAL,
    net_income             REAL,
    sa_hq_sales_comm       REAL,
    sa_corp_promotion      REAL,
    royalty                REAL,
    sa_royalty_3rd_party   REAL,
    sa_royalty_hq          REAL
);

DROP TABLE IF EXISTS row_lineage;
DROP TABLE IF EXISTS source_file;
DROP TABLE IF EXISTS import_run;

CREATE TABLE import_run (
    import_run_id          TEXT PRIMARY KEY,
    client_id              TEXT,
    started_at             TEXT NOT NULL,
    source                 TEXT NOT NULL,
    mapping_name           TEXT,
    mapping_path           TEXT,
    mapping_sha256         TEXT,
    row_count              INTEGER NOT NULL DEFAULT 0,
    status                 TEXT NOT NULL DEFAULT 'success',
    notes                  TEXT
);

CREATE TABLE source_file (
    source_file_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    import_run_id          TEXT NOT NULL,
    filename               TEXT NOT NULL,
    relpath                TEXT,
    sha256                 TEXT,
    extractor              TEXT,
    document_type          TEXT,
    FOREIGN KEY(import_run_id) REFERENCES import_run(import_run_id)
);

CREATE TABLE row_lineage (
    ledger_rowid           INTEGER PRIMARY KEY,
    import_run_id          TEXT NOT NULL,
    source_file_id         INTEGER NOT NULL,
    sheet_name             TEXT,
    source_row             INTEGER,
    raw_file               TEXT,
    source_reference       TEXT,
    FOREIGN KEY(import_run_id) REFERENCES import_run(import_run_id),
    FOREIGN KEY(source_file_id) REFERENCES source_file(source_file_id),
    FOREIGN KEY(ledger_rowid) REFERENCES pl_detail(rowid)
);

-- ----------------------------------------------------------------------------
-- Indexes (created after bulk load in production; safe to define up front here)
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_year          ON pl_detail (year);
CREATE INDEX IF NOT EXISTS idx_region        ON pl_detail (region_desc);
CREATE INDEX IF NOT EXISTS idx_country       ON pl_detail (country_name);
CREATE INDEX IF NOT EXISTS idx_customer      ON pl_detail (customer_name);
CREATE INDEX IF NOT EXISTS idx_mgroup        ON pl_detail (m_group_desc);
CREATE INDEX IF NOT EXISTS idx_class         ON pl_detail ("class");
CREATE INDEX IF NOT EXISTS idx_version       ON pl_detail (version);
CREATE INDEX IF NOT EXISTS idx_period        ON pl_detail (period);
CREATE INDEX IF NOT EXISTS idx_profit_center ON pl_detail (profit_center);
CREATE INDEX IF NOT EXISTS idx_product       ON pl_detail (product_number);
CREATE INDEX IF NOT EXISTS idx_year_region   ON pl_detail (year, region_desc);
CREATE INDEX IF NOT EXISTS idx_year_mgroup   ON pl_detail (year, m_group_desc);
CREATE INDEX IF NOT EXISTS idx_year_customer ON pl_detail (year, customer_name);
CREATE INDEX IF NOT EXISTS lineage_import_run_lookup ON row_lineage (import_run_id);
CREATE INDEX IF NOT EXISTS lineage_source_file_lookup ON row_lineage (source_file_id);
CREATE INDEX IF NOT EXISTS source_file_run_lookup ON source_file (import_run_id);

-- ----------------------------------------------------------------------------
-- Analytical views (Actual-only roll-ups used as a fallback / convenience)
-- ----------------------------------------------------------------------------
DROP VIEW IF EXISTS v_yearly_pl;
CREATE VIEW v_yearly_pl AS
SELECT
    year,
    SUM(net_sales)          AS net_sales,
    SUM(cost_of_goods_sold) AS cogs,
    SUM(gross_margin)       AS gross_margin,
    SUM(operating_expense)  AS opex,
    SUM(operating_profit)   AS operating_profit,
    SUM(net_income)         AS net_income,
    SUM(s_gross_sales)      AS gross_sales,
    SUM(s_return_amt)       AS returns,
    SUM(sales_deduction)    AS sales_deduction,
    SUM(material_cost)      AS material_cost,
    SUM(sales_expense)      AS sales_expense,
    SUM(profit_before_tax)  AS profit_before_tax,
    SUM(corporate_tax)      AS corporate_tax,
    SUM(royalty)            AS royalty
FROM pl_detail
WHERE version = 'Actual'
GROUP BY year
ORDER BY year;

DROP VIEW IF EXISTS v_regional_pl;
CREATE VIEW v_regional_pl AS
SELECT
    year, region_desc,
    SUM(net_sales)          AS net_sales,
    SUM(cost_of_goods_sold) AS cogs,
    SUM(gross_margin)       AS gross_margin,
    SUM(operating_expense)  AS opex,
    SUM(operating_profit)   AS operating_profit,
    SUM(net_income)         AS net_income
FROM pl_detail
WHERE version = 'Actual'
GROUP BY year, region_desc
ORDER BY year, region_desc;

DROP VIEW IF EXISTS v_mgroup_pl;
CREATE VIEW v_mgroup_pl AS
SELECT
    year, m_group_desc,
    SUM(net_sales)          AS net_sales,
    SUM(cost_of_goods_sold) AS cogs,
    SUM(gross_margin)       AS gross_margin,
    SUM(operating_expense)  AS opex,
    SUM(operating_profit)   AS operating_profit,
    SUM(net_income)         AS net_income
FROM pl_detail
WHERE version = 'Actual'
GROUP BY year, m_group_desc
ORDER BY year, m_group_desc;

DROP VIEW IF EXISTS v_country_pl;
CREATE VIEW v_country_pl AS
SELECT
    year, region_desc, country_name,
    SUM(net_sales)          AS net_sales,
    SUM(cost_of_goods_sold) AS cogs,
    SUM(gross_margin)       AS gross_margin,
    SUM(operating_expense)  AS opex,
    SUM(operating_profit)   AS operating_profit,
    SUM(net_income)         AS net_income
FROM pl_detail
WHERE version = 'Actual'
GROUP BY year, region_desc, country_name
ORDER BY year, region_desc, country_name;

DROP VIEW IF EXISTS v_customer_pl;
CREATE VIEW v_customer_pl AS
SELECT
    year, customer_name, region_desc,
    SUM(net_sales)          AS net_sales,
    SUM(cost_of_goods_sold) AS cogs,
    SUM(gross_margin)       AS gross_margin,
    SUM(operating_expense)  AS opex,
    SUM(operating_profit)   AS operating_profit,
    SUM(net_income)         AS net_income
FROM pl_detail
WHERE version = 'Actual'
GROUP BY year, customer_name, region_desc
ORDER BY year, net_sales DESC;

DROP VIEW IF EXISTS v_yoy_variance;
CREATE VIEW v_yoy_variance AS
SELECT
    curr.year,
    curr.net_sales,
    prev.net_sales AS prev_net_sales,
    curr.net_sales - prev.net_sales AS net_sales_change,
    CASE WHEN prev.net_sales != 0
        THEN ROUND((curr.net_sales - prev.net_sales) / ABS(prev.net_sales) * 100, 2)
        ELSE NULL END AS net_sales_pct,
    curr.gross_margin,
    prev.gross_margin AS prev_gross_margin,
    curr.gross_margin - prev.gross_margin AS gross_margin_change,
    curr.operating_profit,
    prev.operating_profit AS prev_operating_profit,
    curr.operating_profit - prev.operating_profit AS operating_profit_change,
    curr.net_income,
    prev.net_income AS prev_net_income,
    curr.net_income - prev.net_income AS net_income_change
FROM v_yearly_pl curr
LEFT JOIN v_yearly_pl prev ON curr.year = prev.year + 1;
