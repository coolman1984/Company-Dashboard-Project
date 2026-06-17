/**
 * Company Dashboard v4.2 - dynamic SQLite and CFO outlook analytics server.
 *
 * Every dashboard endpoint queries pl_detail.db at request time. Precomputed
 * JSON is retained only as a cache-only fallback when SQLite is unavailable.
 */
const http = require('http');
const fs = require('fs');
const path = require('path');
const url = require('url');
const crypto = require('crypto');
const os = require('os');
const { spawnSync } = require('child_process');

const PORT = Number(process.env.PORT) || 3001;
const HOST = process.env.HOST || '127.0.0.1';
const ACCESS_TOKEN = process.env.ACCESS_TOKEN || null;
const PROJECT_ROOT = path.resolve(__dirname);
const PROJECT_ROOT_PREFIX = PROJECT_ROOT.endsWith(path.sep) ? PROJECT_ROOT : PROJECT_ROOT + path.sep;
const DB_PATH = path.join(__dirname, 'pl_detail.db');
const API_DATA_DIR = path.join(__dirname, 'api_data');
const CHART_JS_PATH = path.join(__dirname, 'chart.umd.min.js');
const PUBLIC_FILES = new Set(['index.html', 'app.js', 'i18n.js']);

if (fs.existsSync(CHART_JS_PATH)) {
    PUBLIC_FILES.add('chart.umd.min.js');
}
if (fs.existsSync(path.join(__dirname, 'cairo.ttf'))) {
    PUBLIC_FILES.add('cairo.ttf');
}

const VALID_DIMENSIONS = ['region_desc', 'country_name', 'm_group_desc', 'customer_name', 'class'];
const VALID_METRICS = ['net_sales', 'cost_of_goods_sold', 'gross_margin', 'operating_expense', 'operating_profit', 'net_income'];
const HARDCODED_VERSIONS = ['Actual', 'T06', 'T07'];

const reportDefs = [
    { name: 'yearly_pl', title: 'Yearly P&L Summary', description: 'Group-wide P&L by fiscal year (Actual).',
      sql: 'SELECT * FROM v_yearly_pl ORDER BY year' },
    { name: 'regional_pl', title: 'Regional P&L', description: 'P&L by region and year (Actual).',
      sql: 'SELECT * FROM v_regional_pl ORDER BY year, net_sales DESC' },
    { name: 'product_group_pl', title: 'Product Group P&L', description: 'P&L by product group and year (Actual).',
      sql: 'SELECT * FROM v_mgroup_pl ORDER BY year, net_sales DESC' },
    { name: 'country_pl', title: 'Country P&L', description: 'P&L by country and year (Actual).',
      sql: 'SELECT * FROM v_country_pl ORDER BY year, net_sales DESC' },
    { name: 'customer_pl', title: 'Customer P&L', description: 'P&L by customer and year (Actual).',
      sql: 'SELECT * FROM v_customer_pl ORDER BY year, net_sales DESC' },
    { name: 'yoy_variance', title: 'Year-over-Year Variance', description: 'YoY change in key P&L lines (Actual).',
      sql: 'SELECT * FROM v_yoy_variance ORDER BY year' },
    { name: 'import_validation', title: 'Import Validation Report', description: 'Row counts, duplicate grain, and source-lineage coverage.',
      sql: `
        SELECT 'Summary' AS category, 'Total rows in ledger' AS item, CAST(COUNT(*) AS TEXT) AS value, 'OK' AS status FROM pl_detail
        UNION ALL
        SELECT 'Lineage', 'Rows with source lineage', CAST((SELECT COUNT(*) FROM row_lineage) AS TEXT) || ' / ' || CAST((SELECT COUNT(*) FROM pl_detail) AS TEXT),
               CASE WHEN (SELECT COUNT(*) FROM row_lineage) = (SELECT COUNT(*) FROM pl_detail) THEN 'OK' ELSE 'WARN' END
        UNION ALL
        SELECT 'Lineage', 'Source files', CAST(COUNT(*) AS TEXT), CASE WHEN COUNT(*) > 0 THEN 'OK' ELSE 'WARN' END FROM source_file
        UNION ALL
        SELECT 'Lineage', 'Import runs', CAST(COUNT(*) AS TEXT), CASE WHEN COUNT(*) > 0 THEN 'OK' ELSE 'WARN' END FROM import_run
        UNION ALL
        SELECT 'Quality', 'Duplicate grain combinations', CAST(COUNT(*) AS TEXT), CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'WARN' END FROM (
            SELECT year, version, period, region_desc, m_group_desc, country_name, customer_name
            FROM pl_detail
            GROUP BY year, version, period, region_desc, m_group_desc, country_name, customer_name
            HAVING COUNT(*) > 1
        )
        UNION ALL
        SELECT 'Quality', 'Null critical fields', CAST(COUNT(*) AS TEXT), CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'WARN' END
        FROM pl_detail
        WHERE year IS NULL OR version IS NULL OR period IS NULL OR region_desc IS NULL OR m_group_desc IS NULL OR net_sales IS NULL
      ` },
    { name: 'outlook_pl', title: 'Full-Year Outlook vs Prior Year', description: 'Forecast full-year P&L (Actual P01-P05 + T06 P06 + T07 P07-P12) versus prior-year actual.',
      sql: `
        WITH outlook AS (
            SELECT 
                SUM(net_sales) AS net_sales,
                SUM(cost_of_goods_sold) AS cogs,
                SUM(gross_margin) AS gross_margin,
                SUM(operating_expense) AS opex,
                SUM(operating_profit) AS operating_profit,
                SUM(profit_before_tax) AS profit_before_tax,
                SUM(corporate_tax) AS corporate_tax,
                SUM(net_income) AS net_income
            FROM pl_detail
            WHERE year = (SELECT MAX(year) FROM pl_detail WHERE year IS NOT NULL)
              AND (
                (version = 'Actual' AND CAST(ROUND((period - CAST(period AS INTEGER)) * 1000) AS INTEGER) BETWEEN 1 AND 5)
                OR (version = 'T06' AND CAST(ROUND((period - CAST(period AS INTEGER)) * 1000) AS INTEGER) = 6)
                OR (version = 'T07' AND CAST(ROUND((period - CAST(period AS INTEGER)) * 1000) AS INTEGER) BETWEEN 7 AND 12)
              )
        ),
        prior AS (
            SELECT 
                SUM(net_sales) AS net_sales,
                SUM(cost_of_goods_sold) AS cogs,
                SUM(gross_margin) AS gross_margin,
                SUM(operating_expense) AS opex,
                SUM(operating_profit) AS operating_profit,
                SUM(profit_before_tax) AS profit_before_tax,
                SUM(corporate_tax) AS corporate_tax,
                SUM(net_income) AS net_income
            FROM pl_detail
            WHERE year = (SELECT MAX(year) - 1 FROM pl_detail WHERE year IS NOT NULL)
              AND version = 'Actual'
        )
        SELECT 'Net Sales' AS line_item, o.net_sales AS outlook, p.net_sales AS prior_year, o.net_sales - p.net_sales AS variance,
               CASE WHEN p.net_sales != 0 THEN ROUND((o.net_sales - p.net_sales) * 100.0 / ABS(p.net_sales), 2) ELSE NULL END AS variance_pct
        FROM outlook o, prior p
        UNION ALL
        SELECT 'COGS', o.cogs, p.cogs, o.cogs - p.cogs, CASE WHEN p.cogs != 0 THEN ROUND((o.cogs - p.cogs) * 100.0 / ABS(p.cogs), 2) ELSE NULL END FROM outlook o, prior p
        UNION ALL
        SELECT 'Gross Margin', o.gross_margin, p.gross_margin, o.gross_margin - p.gross_margin, CASE WHEN p.gross_margin != 0 THEN ROUND((o.gross_margin - p.gross_margin) * 100.0 / ABS(p.gross_margin), 2) ELSE NULL END FROM outlook o, prior p
        UNION ALL
        SELECT 'Operating Expense', o.opex, p.opex, o.opex - p.opex, CASE WHEN p.opex != 0 THEN ROUND((o.opex - p.opex) * 100.0 / ABS(p.opex), 2) ELSE NULL END FROM outlook o, prior p
        UNION ALL
        SELECT 'Operating Profit', o.operating_profit, p.operating_profit, o.operating_profit - p.operating_profit, CASE WHEN p.operating_profit != 0 THEN ROUND((o.operating_profit - p.operating_profit) * 100.0 / ABS(p.operating_profit), 2) ELSE NULL END FROM outlook o, prior p
        UNION ALL
        SELECT 'Profit Before Tax', o.profit_before_tax, p.profit_before_tax, o.profit_before_tax - p.profit_before_tax, CASE WHEN p.profit_before_tax != 0 THEN ROUND((o.profit_before_tax - p.profit_before_tax) * 100.0 / ABS(p.profit_before_tax), 2) ELSE NULL END FROM outlook o, prior p
        UNION ALL
        SELECT 'Corporate Tax', o.corporate_tax, p.corporate_tax, o.corporate_tax - p.corporate_tax, CASE WHEN p.corporate_tax != 0 THEN ROUND((o.corporate_tax - p.corporate_tax) * 100.0 / ABS(p.corporate_tax), 2) ELSE NULL END FROM outlook o, prior p
        UNION ALL
        SELECT 'Net Income', o.net_income, p.net_income, o.net_income - p.net_income, CASE WHEN p.net_income != 0 THEN ROUND((o.net_income - p.net_income) * 100.0 / ABS(p.net_income), 2) ELSE NULL END FROM outlook o, prior p
      ` },
    { name: 'outlook_monthly', title: 'Monthly Outlook Progression', description: 'Net sales and gross margin by month, flagged actual vs outlook.',
      sql: `
        SELECT 
            CAST(ROUND((period - CAST(period AS INTEGER)) * 1000) AS INTEGER) AS period_number,
            'P' || PRINTF('%02d', CAST(ROUND((period - CAST(period AS INTEGER)) * 1000) AS INTEGER)) AS period_label,
            CASE WHEN version = 'Actual' THEN 'actual' ELSE 'outlook' END AS status,
            SUM(net_sales) AS net_sales,
            SUM(gross_margin) AS gross_margin
        FROM pl_detail
        WHERE year = (SELECT MAX(year) FROM pl_detail WHERE year IS NOT NULL)
          AND (
            (version = 'Actual' AND CAST(ROUND((period - CAST(period AS INTEGER)) * 1000) AS INTEGER) BETWEEN 1 AND 5)
            OR (version = 'T06' AND CAST(ROUND((period - CAST(period AS INTEGER)) * 1000) AS INTEGER) = 6)
            OR (version = 'T07' AND CAST(ROUND((period - CAST(period AS INTEGER)) * 1000) AS INTEGER) BETWEEN 7 AND 12)
          )
        GROUP BY period_number, version
        ORDER BY period_number
      ` },
];
const REPORT_DEFINITIONS = reportDefs;
const HARDCODED_YEARS = [2022, 2023, 2024, 2025, 2026];
const MAX_LIMIT = 500;

let VALID_VERSIONS = [...HARDCODED_VERSIONS];
let VALID_YEARS = [...HARDCODED_YEARS];
let OUTLOOK_YEAR = null;
let OUTLOOK_ACTUAL_PERIODS = 5;  // number of Actual periods already closed (P01-this)
const PERIOD_NUMBER_SQL = 'CAST(ROUND((period - CAST(period AS INTEGER)) * 1000) AS INTEGER)';
const OUTLOOK_PERIOD_SQL = function () {
    return `(
    (version = 'Actual' AND ${PERIOD_NUMBER_SQL} BETWEEN 1 AND ${OUTLOOK_ACTUAL_PERIODS})
    OR (version = 'T06' AND ${PERIOD_NUMBER_SQL} = ${OUTLOOK_ACTUAL_PERIODS + 1})
    OR (version = 'T07' AND ${PERIOD_NUMBER_SQL} BETWEEN ${OUTLOOK_ACTUAL_PERIODS + 2} AND 12)
)`;
};

const METRIC_SELECT = [
    'SUM(net_sales) AS net_sales',
    'SUM(cost_of_goods_sold) AS cogs',
    'SUM(gross_margin) AS gross_margin',
    'SUM(operating_expense) AS opex',
    'SUM(operating_profit) AS operating_profit',
    'SUM(net_income) AS net_income'
].join(', ');

const FULL_METRIC_SELECT = [
    METRIC_SELECT,
    'SUM(s_gross_sales_amt) AS gross_sales',
    'SUM(s_return_amt) AS returns',
    'SUM(sales_deduction) AS sales_deduction',
    'SUM(material_cost) AS material_cost',
    'SUM(sales_expense) AS sales_expense',
    'SUM(profit_before_tax) AS profit_before_tax',
    'SUM(corporate_tax) AS corporate_tax',
    'SUM(royalty) AS royalty'
].join(', ');

const MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.ttf': 'font/ttf'
};

let db = null;
let dbAvailable = false;

try {
    const Database = require('better-sqlite3');
    db = new Database(DB_PATH, { readonly: true, fileMustExist: true });
    db.pragma('query_only = ON');
    db.pragma('temp_store = MEMORY');
    db.pragma('cache_size = -64000');
    dbAvailable = true;
    console.log(`SQLite connected in read-only mode: ${DB_PATH}`);

    const dbYears = db.prepare(
        'SELECT DISTINCT year FROM pl_detail ORDER BY year'
    ).all().map(r => r.year);
    if (dbYears.length > 0) VALID_YEARS = dbYears;

    const dbVersions = db.prepare(
        'SELECT DISTINCT version FROM pl_detail ORDER BY version'
    ).all().map(r => r.version);
    if (dbVersions.length > 0) VALID_VERSIONS = dbVersions;

    const outlookCandidate = db.prepare(`
        SELECT year FROM pl_detail
        WHERE version IN ('T06', 'T07')
        GROUP BY year
        ORDER BY year DESC
        LIMIT 1
    `).all();
    if (outlookCandidate.length > 0) {
        OUTLOOK_YEAR = outlookCandidate[0].year;
    } else {
        const latestActual = db.prepare(
            'SELECT MAX(year) AS year FROM pl_detail'
        ).all();
        OUTLOOK_YEAR = latestActual[0] && latestActual[0].year
            ? latestActual[0].year
            : HARDCODED_YEARS[HARDCODED_YEARS.length - 1];
    }

    const actualCount = db.prepare(`
        SELECT COUNT(DISTINCT ${PERIOD_NUMBER_SQL}) AS cnt
        FROM pl_detail
        WHERE year = ? AND version = 'Actual'
    `).get(OUTLOOK_YEAR);
    OUTLOOK_ACTUAL_PERIODS = actualCount && actualCount.cnt ? actualCount.cnt : 5;

    console.log(
        `Years: ${VALID_YEARS.map(String).join(',')}  |  ` +
        `Versions: ${VALID_VERSIONS.join(',')}  |  ` +
        `Outlook year: ${OUTLOOK_YEAR} (Actual P01-P${String(OUTLOOK_ACTUAL_PERIODS).padStart(2, '0')})`
    );
} catch (error) {
    console.warn(`WARN: SQLite unavailable: ${error.message}`);
}

const fallbackCache = {};

function loadFallbackCache() {
    if (!fs.existsSync(API_DATA_DIR)) return;
    fs.readdirSync(API_DATA_DIR)
        .filter(file => file.endsWith('.json'))
        .forEach(file => {
            try {
                fallbackCache[file.slice(0, -5)] = JSON.parse(
                    fs.readFileSync(path.join(API_DATA_DIR, file), 'utf8')
                );
            } catch (error) {
                console.warn(`WARN: Could not load fallback ${file}: ${error.message}`);
            }
        });
}

loadFallbackCache();

function securityHeaders(res) {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('Referrer-Policy', 'no-referrer');
    res.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
    res.setHeader('Content-Security-Policy', [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "font-src 'self'",
        "img-src 'self' data:",
        "connect-src 'self'"
    ].join('; '));
}

function normalizeAliases(data) {
    if (Array.isArray(data)) {
        return data.map(normalizeAliases);
    }
    if (!data || typeof data !== 'object') return data;

    const normalized = {};
    Object.keys(data).forEach(key => {
        normalized[key] = normalizeAliases(data[key]);
    });
    if (normalized.cogs !== undefined) normalized.cost_of_goods_sold = normalized.cogs;
    if (normalized.cost_of_goods_sold !== undefined) normalized.cogs = normalized.cost_of_goods_sold;
    if (normalized.opex !== undefined) normalized.operating_expense = normalized.opex;
    if (normalized.operating_expense !== undefined) normalized.opex = normalized.operating_expense;
    return normalized;
}

// Defensive: a corrupt source value could surface as NaN/Infinity from SQLite.
// JSON.stringify already turns those into null, but we do it explicitly so the
// behaviour is intentional and consistent across all responses.
function finiteReplacer(key, value) {
    return (typeof value === 'number' && !Number.isFinite(value)) ? null : value;
}

function jsonResponse(res, data, statusCode = 200) {
    res.writeHead(statusCode, {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'no-store'
    });
    res.end(JSON.stringify(normalizeAliases(data), finiteReplacer));
}

function errorResponse(res, statusCode, message) {
    jsonResponse(res, { error: message }, statusCode);
}

function csvEscape(value) {
    if (value === null || value === undefined) return '';
    return '"' + String(value).replace(/"/g, '""') + '"';
}

function sendDownload(res, filename, contentType, data) {
    res.writeHead(200, {
        'Content-Type': contentType,
        'Content-Disposition': `attachment; filename="${filename}"`,
        'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff'
    });
    res.end(data);
}

function reportEnvelope(def) {
    const rows = runDynamic(def.sql);
    const columns = rows.length > 0 ? Object.keys(rows[0]) : [];
    return {
        report: def.name,
        title: def.title,
        description: def.description,
        generated_at: new Date().toISOString(),
        source: { database: path.basename(DB_PATH), rows_in_ledger: getSummary().totalRows },
        columns: columns,
        row_count: rows.length,
        rows: rows
    };
}

function reportCsvBuffer(envelope) {
    const lines = [];
    lines.push(envelope.columns.map(csvEscape).join(','));
    envelope.rows.forEach(row => {
        lines.push(envelope.columns.map(column => csvEscape(row[column])).join(','));
    });
    return Buffer.from('\ufeff' + lines.join('\n'), 'utf8');
}

// Office exports (xlsx/pdf) need optional Python libraries (openpyxl / reportlab).
// Probe once and cache so a clean install degrades gracefully — the UI hides the
// buttons it can't fulfil and the API returns a clear "needs setup" 503 instead
// of a raw 500 traceback.
let _exportCapabilities = null;
function getExportCapabilities() {
    if (_exportCapabilities) return _exportCapabilities;
    const fallback = { json: true, csv: true, xlsx: false, pdf: false };
    try {
        const result = spawnSync('python3', ['-m', 'reports.cli', '--capabilities'],
            { cwd: PROJECT_ROOT, encoding: 'utf8', timeout: 15000 });
        if (result.status === 0 && result.stdout) {
            const caps = JSON.parse(result.stdout.trim());
            _exportCapabilities = { json: true, csv: true, xlsx: !!caps.xlsx, pdf: !!caps.pdf };
            return _exportCapabilities;
        }
    } catch (error) {
        // fall through to the CSV-only fallback below
    }
    _exportCapabilities = fallback;
    return _exportCapabilities;
}

function reportOfficeBuffer(name, format) {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cdash-report-'));
    try {
        const result = spawnSync('python3', [
            '-m', 'reports.cli', '--db', DB_PATH, '--out', tmpDir,
            '--report', name, '--format', format
        ], { cwd: PROJECT_ROOT, encoding: 'utf8', timeout: 120000 });
        if (result.status !== 0) {
            const details = (result.stderr || result.stdout || '').trim();
            throw new Error(details || `reports.cli exited with ${result.status}`);
        }
        const filePath = path.join(tmpDir, `${name}.${format}`);
        if (!fs.existsSync(filePath)) throw new Error(`report file was not generated: ${filePath}`);
        return fs.readFileSync(filePath);
    } finally {
        fs.rmSync(tmpDir, { recursive: true, force: true });
    }
}

// Import health & history — surfaces source-confidence in the UI so a challenged
// number can be defended on screen. The validation checks are computed live from
// the database; the run history is read from per-client workspace manifests when
// a real client import has been performed (absent for the synthetic seed).
function readImportHistory() {
    const runs = [];
    const wsRoot = path.join(PROJECT_ROOT, 'workspaces');
    try {
        if (!fs.existsSync(wsRoot)) return runs;
        for (const client of fs.readdirSync(wsRoot)) {
            const manifest = path.join(wsRoot, client, 'import_history.json');
            if (!fs.existsSync(manifest)) continue;
            try {
                const data = JSON.parse(fs.readFileSync(manifest, 'utf8'));
                (data.runs || []).forEach(r => runs.push({
                    client_id: data.client_id || client,
                    run_id: r.run_id || null,
                    timestamp: r.timestamp || null,
                    status: r.status || 'unknown',
                    row_count: r.row_count != null ? r.row_count : null,
                    warnings: Array.isArray(r.warnings) ? r.warnings.length : 0
                }));
            } catch (error) {
                // skip a malformed manifest rather than failing the whole panel
            }
        }
    } catch (error) {
        // no workspaces directory — synthetic / pre-import state
    }
    runs.sort((a, b) => String(b.timestamp).localeCompare(String(a.timestamp)));
    return runs.slice(0, 50);
}

function serveStatic(filePath, res) {
    const safePath = path.resolve(filePath);
    if (safePath !== PROJECT_ROOT && !safePath.startsWith(PROJECT_ROOT_PREFIX)) {
        res.writeHead(403);
        res.end('Forbidden');
        return;
    }
    fs.readFile(safePath, (error, data) => {
        if (error) {
            res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
            res.end('Not found');
            return;
        }
        res.writeHead(200, {
            'Content-Type': MIME_TYPES[path.extname(safePath)] || 'application/octet-stream',
            'X-Content-Type-Options': 'nosniff'
        });
        res.end(data);
    });
}

function parseInteger(value, fallback = null) {
    if (value === undefined || value === null || value === '') return fallback;
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) ? parsed : fallback;
}

function parseLimit(value, fallback = 50) {
    return Math.min(Math.max(parseInteger(value, fallback), 1), MAX_LIMIT);
}

// Default year selection derived from the live data, never hard-coded.
function latestYear() {
    return VALID_YEARS[VALID_YEARS.length - 1];
}

function priorYear(year) {
    const idx = VALID_YEARS.indexOf(year);
    return idx > 0 ? VALID_YEARS[idx - 1] : year - 1;
}

function periodRange(start, end) {
    const out = [];
    for (let p = start; p <= end; p += 1) out.push(p);
    return out;
}

// Constant-time comparison so the access token can't be probed by timing.
function tokenMatches(provided, expected) {
    const a = Buffer.from(String(provided));
    const b = Buffer.from(String(expected));
    return a.length === b.length && crypto.timingSafeEqual(a, b);
}

function validateVersion(version) {
    if (!VALID_VERSIONS.includes(version)) {
        throw new Error(`Invalid version. Use: ${VALID_VERSIONS.join(', ')}`);
    }
}

function validateYear(year) {
    if (year !== null && !VALID_YEARS.includes(year)) {
        throw new Error(`Invalid year. Use: ${VALID_YEARS.join(', ')}`);
    }
}

function buildWhere(query, options = {}) {
    const clauses = [];
    const params = [];
    const version = query.version || options.defaultVersion || null;
    const year = parseInteger(query.year);

    if (version) {
        validateVersion(version);
        clauses.push('version = ?');
        params.push(version);
    }
    if (year !== null) {
        validateYear(year);
        clauses.push('year = ?');
        params.push(year);
    }

    const filters = [
        ['region', 'region_desc'],
        ['country', 'country_name'],
        ['product', 'm_group_desc'],
        ['customer', 'customer_name'],
        ['class', 'class']
    ];

    filters.forEach(([queryKey, column]) => {
        const value = query[queryKey];
        if (value) {
            clauses.push(`${column} = ?`);
            params.push(value);
        }
    });

    return {
        sql: clauses.length ? `WHERE ${clauses.join(' AND ')}` : '',
        params
    };
}

function runDynamic(sql, params = []) {
    if (!dbAvailable) throw new Error('SQLite database is unavailable');
    return db.prepare(sql).all(...params);
}

function fallback(key, defaultValue = []) {
    return fallbackCache[key] || defaultValue;
}

function getDataFreshness() {
    if (!dbAvailable) {
        return { source: 'fallback-cache', years: {}, note: 'SQLite metadata unavailable.' };
    }
    const rows = runDynamic(`
        SELECT year, version,
               COUNT(DISTINCT period) AS period_count,
               MIN(period) AS min_period,
               MAX(period) AS max_period,
               COUNT(*) AS row_count
        FROM pl_detail
        GROUP BY year, version
        ORDER BY year, version
    `);
    const years = {};
    rows.forEach(row => {
        if (!years[row.year]) years[row.year] = {};
        const periodNumber = row.max_period == null
            ? null
            : Number(String(row.max_period).split('.').pop());
        years[row.year][row.version] = {
            periodCount: row.period_count,
            minPeriod: row.min_period,
            maxPeriod: row.max_period,
            maxPeriodNumber: periodNumber,
            rowCount: row.row_count,
            isFullYear: row.period_count >= 12
        };
    });
    return {
        source: 'sqlite-live',
        years,
        note: `FY${OUTLOOK_YEAR} Actual covers P01-P${String(OUTLOOK_ACTUAL_PERIODS).padStart(2, '0')}, T06 covers P${String(OUTLOOK_ACTUAL_PERIODS + 1).padStart(2, '0')}, and T07 covers P${String(OUTLOOK_ACTUAL_PERIODS + 2).padStart(2, '0')}-P12.`
    };
}

function getYearly(query) {
    const where = buildWhere(query, { defaultVersion: 'Actual' });
    return runDynamic(`
        SELECT year, ${FULL_METRIC_SELECT}
        FROM pl_detail
        ${where.sql}
        GROUP BY year
        ORDER BY year
    `, where.params);
}

function getDimensionData(query, dimension, select = METRIC_SELECT) {
    const where = buildWhere(query, { defaultVersion: 'Actual' });
    return runDynamic(`
        SELECT ${dimension}, year, ${select}
        FROM pl_detail
        ${where.sql}
        GROUP BY ${dimension}, year
        ORDER BY year, net_sales DESC
    `, where.params);
}

function getScenario(query) {
    const scenarioQuery = { ...query };
    delete scenarioQuery.version;
    const where = buildWhere(scenarioQuery);
    const rows = runDynamic(`
        SELECT year, version, ${METRIC_SELECT}
        FROM pl_detail
        ${where.sql}
        GROUP BY year, version
        ORDER BY year, version
    `, where.params);
    const byYear = {};
    rows.forEach(row => {
        if (!byYear[row.year]) byYear[row.year] = { year: row.year };
        const prefix = row.version.toLowerCase();
        byYear[row.year][`${prefix}_net_sales`] = row.net_sales;
        byYear[row.year][`${prefix}_cogs`] = row.cogs;
        byYear[row.year][`${prefix}_gross_margin`] = row.gross_margin;
        byYear[row.year][`${prefix}_opex`] = row.opex;
        byYear[row.year][`${prefix}_operating_profit`] = row.operating_profit;
        byYear[row.year][`${prefix}_net_income`] = row.net_income;
    });
    return Object.values(byYear).sort((a, b) => a.year - b.year);
}

function getExecutiveFilter(query) {
    const filterQuery = { ...query };
    delete filterQuery.year;
    delete filterQuery.version;
    return buildWhere(filterQuery);
}

function appendCondition(where, condition) {
    return where.sql ? `${where.sql} AND ${condition}` : `WHERE ${condition}`;
}

function metricSnapshot(row = {}) {
    return {
        net_sales: Number(row.net_sales || 0),
        cogs: Number(row.cogs || 0),
        gross_margin: Number(row.gross_margin || 0),
        opex: Number(row.opex || 0),
        operating_profit: Number(row.operating_profit || 0),
        profit_before_tax: Number(row.profit_before_tax || 0),
        corporate_tax: Number(row.corporate_tax || 0),
        net_income: Number(row.net_income || 0)
    };
}

function getExecutiveOutlook(query) {
    const where = getExecutiveFilter(query);
    const reqYear = parseInteger(query.ovYear);
    const selectedYear = (reqYear && VALID_YEARS.includes(reqYear)) ? reqYear : OUTLOOK_YEAR;
    const priorYearNum = selectedYear - 1;
    const isOutlookYear = selectedYear === OUTLOOK_YEAR;

    const outlookSql = OUTLOOK_PERIOD_SQL();
    const monthlyWhere = isOutlookYear
        ? appendCondition(where, `year = ${selectedYear} AND ${outlookSql}`)
        : appendCondition(where, `year = ${selectedYear} AND version = 'Actual'`);

    const actualYtdWhere = isOutlookYear
        ? appendCondition(where, `year = ${selectedYear} AND version = 'Actual'`)
        : monthlyWhere;

    const priorWhere = appendCondition(where, `year = ${priorYearNum} AND version = 'Actual'`);

    const monthly = runDynamic(`
        SELECT ${PERIOD_NUMBER_SQL} AS period_number,
               version,
               ${FULL_METRIC_SELECT}
        FROM pl_detail
        ${monthlyWhere}
        GROUP BY period_number, version
        ORDER BY period_number
    `, where.params).map(row => ({
        ...row,
        period_label: `P${String(row.period_number).padStart(2, '0')}`,
        status: row.version === 'Actual' ? 'actual' : 'outlook'
    }));

    const actualYtd = metricSnapshot(runDynamic(`
        SELECT ${FULL_METRIC_SELECT}
        FROM pl_detail
        ${actualYtdWhere}
    `, where.params)[0]);

    const outlook = metricSnapshot(runDynamic(`
        SELECT ${FULL_METRIC_SELECT}
        FROM pl_detail
        ${monthlyWhere}
    `, where.params)[0]);

    const priorYear = metricSnapshot(runDynamic(`
        SELECT ${FULL_METRIC_SELECT}
        FROM pl_detail
        ${priorWhere}
    `, where.params)[0]);

    const concentration = {};
    const concentrationDimensions = [
        ['customers', 'customer_name'],
        ['products', 'm_group_desc'],
        ['regions', 'region_desc']
    ];

    concentrationDimensions.forEach(([key, column]) => {
        concentration[key] = runDynamic(`
            SELECT COALESCE(${column}, 'Unassigned') AS label,
                   ${METRIC_SELECT}
            FROM pl_detail
            ${monthlyWhere}
            GROUP BY ${column}
            HAVING net_sales != 0
            ORDER BY net_sales DESC
            LIMIT 10
        `, where.params);
    });

    const profitability = runDynamic(`
        WITH product_outlook AS (
            SELECT COALESCE(m_group_desc, 'Unassigned') AS label,
                   ${METRIC_SELECT}
            FROM pl_detail
            ${monthlyWhere}
            GROUP BY m_group_desc
        ),
        product_prior AS (
            SELECT COALESCE(m_group_desc, 'Unassigned') AS label,
                   SUM(net_sales) AS prior_net_sales,
                   SUM(gross_margin) AS prior_gross_margin,
                   SUM(operating_profit) AS prior_operating_profit
            FROM pl_detail
            ${priorWhere}
            GROUP BY m_group_desc
        )
        SELECT o.*,
               COALESCE(p.prior_net_sales, 0) AS prior_net_sales,
               COALESCE(p.prior_gross_margin, 0) AS prior_gross_margin,
               COALESCE(p.prior_operating_profit, 0) AS prior_operating_profit
        FROM product_outlook o
        LEFT JOIN product_prior p ON p.label = o.label
        WHERE o.net_sales != 0
        ORDER BY o.net_sales DESC
        LIMIT 20
    `, [...where.params, ...where.params]);

    const productRisk = runDynamic(`
        WITH product_outlook AS (
            SELECT m_group_desc,
                   SUM(net_sales) AS net_sales,
                   SUM(gross_margin) AS gross_margin,
                   SUM(operating_profit) AS operating_profit
            FROM pl_detail
            ${monthlyWhere}
            GROUP BY m_group_desc
        )
        SELECT COUNT(*) AS product_count,
               SUM(CASE WHEN gross_margin < 0 THEN 1 ELSE 0 END) AS negative_gm_products,
               SUM(CASE WHEN operating_profit < 0 THEN 1 ELSE 0 END) AS loss_making_products,
               SUM(CASE WHEN gross_margin < 0 THEN net_sales ELSE 0 END) AS negative_gm_revenue,
               SUM(CASE WHEN operating_profit < 0 THEN net_sales ELSE 0 END) AS loss_making_revenue,
               SUM(net_sales) AS total_revenue
        FROM product_outlook
    `, where.params)[0] || {};

    return {
        coverage: {
            year: selectedYear,
            priorYear: priorYearNum,
            isOutlookYear,
            actualPeriods: isOutlookYear ? periodRange(1, OUTLOOK_ACTUAL_PERIODS) : null,
            outlookPeriods: isOutlookYear ? periodRange(OUTLOOK_ACTUAL_PERIODS + 1, 12) : null,
            definition: isOutlookYear
                ? `Actual P01-P${String(OUTLOOK_ACTUAL_PERIODS).padStart(2, '0')} + ` +
                  `T06 P${String(OUTLOOK_ACTUAL_PERIODS + 1).padStart(2, '0')} + ` +
                  `T07 P${String(OUTLOOK_ACTUAL_PERIODS + 2).padStart(2, '0')}-P12`
                : `FY${selectedYear} Full Year Actual`
        },
        monthly,
        actualYtd,
        outlook,
        priorYear,
        concentration,
        profitability,
        productRisk
    };
}

// Executive briefing — a one-page decision view composed from the outlook:
// what changed, what's at risk, what to do, and how trustworthy the numbers are.
// It only re-shapes data the outlook already computes; no new P&L logic.
function getExecutiveNarrative(query) {
    const eo = getExecutiveOutlook(query);
    const num = v => (typeof v === 'number' && isFinite(v)) ? v : (Number(v) || 0);
    const dir = d => d > 0.5 ? 'up' : (d < -0.5 ? 'down' : 'flat');
    const outlook = eo.outlook || {};
    const prior = eo.priorYear || {};
    const risk = eo.productRisk || {};

    const nsNow = num(outlook.net_sales), nsPrior = num(prior.net_sales);
    const niNow = num(outlook.net_income), niPrior = num(prior.net_income);
    const opNow = num(outlook.operating_profit), opPrior = num(prior.operating_profit);
    const gmPctNow = nsNow ? num(outlook.gross_margin) / nsNow * 100 : 0;
    const gmPctPrior = nsPrior ? num(prior.gross_margin) / nsPrior * 100 : 0;

    const movers = (eo.profitability || []).map(p => {
        const dop = num(p.operating_profit) - num(p.prior_operating_profit);
        return { label: p.label, delta_operating_profit: dop,
                 delta_net_sales: num(p.net_sales) - num(p.prior_net_sales), direction: dir(dop) };
    }).filter(m => m.label && m.delta_operating_profit !== 0);
    movers.sort((a, b) => Math.abs(b.delta_operating_profit) - Math.abs(a.delta_operating_profit));

    const custs = (eo.concentration && eo.concentration.customers) || [];
    const top1 = custs.length ? num(custs[0].net_sales) : 0;
    const top5 = custs.slice(0, 5).reduce((s, c) => s + num(c.net_sales), 0);
    const top1Share = nsNow ? top1 / nsNow * 100 : 0;
    const top5Share = nsNow ? top5 / nsNow * 100 : 0;

    const risks = [];
    if (num(risk.loss_making_products) > 0) {
        risks.push({ type: 'loss_making', severity: 'high',
            count: num(risk.loss_making_products), amount: num(risk.loss_making_revenue) });
    }
    if (num(risk.negative_gm_products) > 0) {
        risks.push({ type: 'negative_gm', severity: 'high',
            count: num(risk.negative_gm_products), amount: num(risk.negative_gm_revenue) });
    }
    if (top5Share >= 40) {
        risks.push({ type: 'concentration', severity: top5Share >= 60 ? 'high' : 'medium',
            pct: top5Share, top1_pct: top1Share, top1_label: custs.length ? custs[0].label : null });
    }
    if (gmPctNow + 0.3 < gmPctPrior) {
        risks.push({ type: 'margin', severity: (gmPctPrior - gmPctNow) >= 2 ? 'high' : 'medium',
            pct: gmPctNow, prior_pct: gmPctPrior, drop: gmPctPrior - gmPctNow });
    }

    let warnings = 0, coverage = 100, totalRows = 0;
    try {
        const def = REPORT_DEFINITIONS.find(r => r.name === 'import_validation');
        if (def) {
            const checks = reportEnvelope(def).rows;
            warnings = checks.filter(c => String(c.status).toUpperCase() === 'WARN').length;
            const lin = checks.find(c => /lineage/i.test(String(c.category)) && /%/.test(String(c.value)));
            const m = lin && String(lin.value).match(/([\d.]+)%/);
            if (m) coverage = Number(m[1]);
            const rowsCheck = checks.find(c => /total rows/i.test(String(c.item)));
            if (rowsCheck) totalRows = Number(rowsCheck.value) || 0;
        }
    } catch (error) {
        // leave defaults — the briefing still renders without source confidence
    }

    return {
        coverage: eo.coverage,
        headline: {
            net_income: niNow, prior_net_income: niPrior,
            net_income_delta: niNow - niPrior, net_income_dir: dir(niNow - niPrior),
            net_sales: nsNow, prior_net_sales: nsPrior,
            net_sales_delta: nsNow - nsPrior, net_sales_dir: dir(nsNow - nsPrior),
            operating_profit: opNow, operating_profit_delta: opNow - opPrior,
            operating_profit_dir: dir(opNow - opPrior),
            gm_pct: gmPctNow, prior_gm_pct: gmPctPrior, gm_pct_delta: gmPctNow - gmPctPrior
        },
        topChanges: movers.slice(0, 5),
        risks,
        sourceConfidence: {
            lineage_coverage_pct: coverage, warnings, total_rows: totalRows,
            overall: warnings > 0 ? 'WARN' : 'OK'
        }
    };
}

function getPortfolio(query) {
    const yearNum = parseInteger(query.year, latestYear());
    const priorYearNum = parseInteger(query.priorYear, priorYear(yearNum));
    validateYear(yearNum);
    validateYear(priorYearNum);

    const rows = runDynamic(`
        WITH current_year AS (
            SELECT COALESCE(m_group_desc, 'Unassigned') AS label,
                   SUM(net_sales) AS net_sales,
                   SUM(gross_margin) AS gross_margin,
                   SUM(operating_profit) AS operating_profit,
                   SUM(cost_of_goods_sold) AS cogs
            FROM pl_detail
            WHERE year = ? AND version = 'Actual'
            GROUP BY m_group_desc HAVING net_sales != 0
        ),
        prior_year AS (
            SELECT COALESCE(m_group_desc, 'Unassigned') AS label,
                   SUM(net_sales) AS prior_net_sales,
                   SUM(gross_margin) AS prior_gross_margin
            FROM pl_detail
            WHERE year = ? AND version = 'Actual'
            GROUP BY m_group_desc
        )
        SELECT c.*, COALESCE(p.prior_net_sales, 0) AS prior_net_sales,
                    COALESCE(p.prior_gross_margin, 0) AS prior_gross_margin
        FROM current_year c
        LEFT JOIN prior_year p ON c.label = p.label
        ORDER BY c.net_sales DESC LIMIT 30
    `, [yearNum, priorYearNum]);

    return { year: yearNum, priorYear: priorYearNum, products: rows };
}

function getFilters(query) {
    const region = query.region || null;
    const countries = region
        ? runDynamic(
            'SELECT DISTINCT country_name AS value FROM pl_detail WHERE region_desc = ? AND country_name IS NOT NULL ORDER BY country_name',
            [region]
        )
        : runDynamic('SELECT DISTINCT country_name AS value FROM pl_detail WHERE country_name IS NOT NULL ORDER BY country_name');

    return {
        versions: runDynamic('SELECT DISTINCT version AS value FROM pl_detail ORDER BY version').map(row => row.value),
        years: runDynamic('SELECT DISTINCT year AS value FROM pl_detail ORDER BY year').map(row => row.value),
        regions: runDynamic('SELECT DISTINCT region_desc AS value FROM pl_detail WHERE region_desc IS NOT NULL ORDER BY region_desc').map(row => row.value),
        countries: countries.map(row => row.value),
        classes: runDynamic('SELECT DISTINCT class AS value FROM pl_detail WHERE class IS NOT NULL ORDER BY class').map(row => row.value)
    };
}

function getSummary() {
    const row = db.prepare(`
        SELECT COUNT(*) AS totalRows,
               COUNT(DISTINCT region_desc) AS regionCount,
               COUNT(DISTINCT country_name) AS countryCount,
               COUNT(DISTINCT customer_name) AS customerCount,
               COUNT(DISTINCT m_group_desc) AS productGroupCount,
               MIN(year) AS minYear,
               MAX(year) AS maxYear
        FROM pl_detail
    `).get();
    return {
        ...row,
        databaseSizeBytes: fs.statSync(DB_PATH).size,
        backend: 'sqlite-live'
    };
}

function getDrilldown(query) {
    const dimension = query.dimension || 'region_desc';
    const metric = query.metric || 'net_sales';
    const year2 = parseInteger(query.year2, latestYear());
    const year1 = parseInteger(query.year1, priorYear(year2));
    const limit = parseLimit(query.limit, 50);

    if (!VALID_DIMENSIONS.includes(dimension)) {
        throw new Error(`Invalid dimension. Use: ${VALID_DIMENSIONS.join(', ')}`);
    }
    if (!VALID_METRICS.includes(metric)) {
        throw new Error(`Invalid metric. Use: ${VALID_METRICS.join(', ')}`);
    }
    validateYear(year1);
    validateYear(year2);
    if (year1 === year2) throw new Error('year1 and year2 must be different');

    const filterQuery = { ...query };
    delete filterQuery.year;
    delete filterQuery.year1;
    delete filterQuery.year2;
    delete filterQuery.dimension;
    delete filterQuery.metric;
    delete filterQuery.limit;
    const where = buildWhere(filterQuery, { defaultVersion: 'Actual' });
    const extraWhere = where.sql ? `${where.sql} AND year IN (?, ?)` : 'WHERE year IN (?, ?)';
  const params = [year1, year2, ...where.params, year1, year2, limit];

    const rows = runDynamic(`
        SELECT ${dimension} AS dimension,
               SUM(CASE WHEN year = ? THEN ${metric} ELSE 0 END) AS val_year1,
               SUM(CASE WHEN year = ? THEN ${metric} ELSE 0 END) AS val_year2
        FROM pl_detail
        ${extraWhere}
        GROUP BY ${dimension}
        HAVING val_year1 != 0 OR val_year2 != 0
        ORDER BY ABS(val_year2 - val_year1) DESC
        LIMIT ?
    `, params);

    return rows.map(row => {
        const change = row.val_year2 - row.val_year1;
        return {
            ...row,
            change,
            pct_change: row.val_year1 !== 0
                ? Math.round(change / Math.abs(row.val_year1) * 10000) / 100
                : null
        };
    });
}

function getTopProducts(query) {
    const limit = parseLimit(query.limit, 30);
    const where = buildWhere(query, { defaultVersion: 'Actual' });
    return runDynamic(`
        SELECT product_number, m_group_desc, ${METRIC_SELECT}
        FROM pl_detail
        ${where.sql}
        GROUP BY product_number, m_group_desc
        HAVING net_sales != 0
        ORDER BY net_sales DESC
        LIMIT ?
    `, [...where.params, limit]);
}

function handleApi(pathname, query, res) {
    if (pathname === '/api/status') {
        return jsonResponse(res, {
            status: 'ok',
            backend: dbAvailable ? 'sqlite-live' : 'fallback-cache',
            database: dbAvailable ? 'connected' : 'unavailable',
            cachedFiles: Object.keys(fallbackCache).length,
            serverVersion: '4.2-cfo'
        });
    }

    if (!dbAvailable) {
        const fallbackRoutes = {
            '/api/summary': ['summary', {}],
            '/api/filters': ['filters', {}],
            '/api/data-freshness': ['data-freshness', { source: 'fallback-cache', years: {}, note: 'SQLite metadata unavailable.' }],
            '/api/yearly-pl': ['yearly-pl', []],
            '/api/regional-pl': ['regional-pl', []],
            '/api/mgroup-pl': ['mgroup-pl', []],
            '/api/country-pl': ['country-pl', []],
            '/api/customer-pl': ['customer-pl', []],
            '/api/yoy-variance': ['yoy-variance', []],
            '/api/scenario-pl': ['scenario-pl', []]
        };
        if (fallbackRoutes[pathname]) {
            const [key, defaultValue] = fallbackRoutes[pathname];
            return jsonResponse(res, fallback(key, defaultValue));
        }
        return errorResponse(res, 503, 'SQLite is unavailable; this dynamic endpoint cannot run.');
    }

    if (pathname === '/api/summary') return jsonResponse(res, getSummary());
    if (pathname === '/api/data-freshness') return jsonResponse(res, getDataFreshness());
    if (pathname === '/api/filters') return jsonResponse(res, getFilters(query));
    if (pathname === '/api/yearly-pl') return jsonResponse(res, getYearly(query));
    if (pathname === '/api/regional-pl') return jsonResponse(res, getDimensionData(query, 'region_desc'));
    if (pathname === '/api/mgroup-pl') return jsonResponse(res, getDimensionData(query, 'm_group_desc'));
    if (pathname === '/api/country-pl') return jsonResponse(res, getDimensionData(query, 'country_name'));

    if (pathname === '/api/customer-pl') {
        const limit = parseLimit(query.limit, 50);
        const rows = getDimensionData(query, 'customer_name');
        rows.sort((a, b) => Math.abs(b.net_sales) - Math.abs(a.net_sales));
        return jsonResponse(res, rows.slice(0, limit));
    }

    if (pathname === '/api/yoy-variance') {
        const rows = getYearly(query);
        return jsonResponse(res, rows.map((row, index) => {
            const previous = rows[index - 1];
            if (!previous) return { ...row, previous_year: null };
            return {
                ...row,
                previous_year: previous.year,
                net_sales_change: row.net_sales - previous.net_sales,
                gross_margin_change: row.gross_margin - previous.gross_margin,
                operating_profit_change: row.operating_profit - previous.operating_profit,
                net_income_change: row.net_income - previous.net_income
            };
        }));
    }

    if (pathname === '/api/scenario-pl') return jsonResponse(res, getScenario(query));
    if (pathname === '/api/executive-outlook') return jsonResponse(res, getExecutiveOutlook(query));
    if (pathname === '/api/executive-narrative') return jsonResponse(res, getExecutiveNarrative(query));
    if (pathname === '/api/drilldown') return jsonResponse(res, getDrilldown(query));
    if (pathname === '/api/top-products') return jsonResponse(res, getTopProducts(query));
    if (pathname === '/api/portfolio') return jsonResponse(res, getPortfolio(query));

    if (pathname === '/api/query') {
        const dimension = query.dimension;
        if (!VALID_DIMENSIONS.includes(dimension)) {
            throw new Error(`Invalid dimension. Use: ${VALID_DIMENSIONS.join(', ')}`);
        }
        const limit = parseLimit(query.limit, 100);
        const rows = getDimensionData(query, dimension);
        return jsonResponse(res, rows.slice(0, limit));
    }

    if (pathname === '/api/scenario-whatif') {
        // Interactive what-if levers — reuse the tested Python scenario engine
        // (reports/scenario.py) so the dashboard never re-implements the P&L math.
        const pct = value => {
            const n = Number(value);
            return Number.isFinite(n) ? Math.max(-95, Math.min(500, n)) : 0;
        };
        let tax = Number(query.tax);
        if (!Number.isFinite(tax)) tax = 22;
        tax = Math.max(0, Math.min(95, tax)) / 100;   // UI sends a percent; engine wants a rate
        const scales = query.scales === undefined ? true : (query.scales === 'true' || query.scales === '1');
        const config = {
            name: 'Interactive what-if',
            adjustments: [
                { metric: 'net_sales', change_pct: pct(query.ns) },
                { metric: 'cost_of_goods_sold', change_pct: pct(query.cogs) },
                { metric: 'operating_expense', change_pct: pct(query.opex) }
            ],
            tax_rate: tax,
            cogs_scales_with_revenue: scales
        };
        try {
            const result = spawnSync('python3', ['-m', 'reports.scenario', '--eval-stdin', '--db', DB_PATH],
                { cwd: PROJECT_ROOT, encoding: 'utf8', input: JSON.stringify(config), timeout: 30000 });
            if (result.status !== 0) {
                const details = (result.stderr || result.stdout || '').trim();
                return errorResponse(res, 500, `Scenario evaluation failed: ${details || result.status}`);
            }
            return jsonResponse(res, JSON.parse(result.stdout));
        } catch (error) {
            return errorResponse(res, 500, `Scenario evaluation failed: ${error.message}`);
        }
    }

    if (pathname === '/api/nl-query') {
        // Offline natural-language query — deterministic parser, no network/LLM.
        const q = String(query.q || '').trim();
        if (!q) return errorResponse(res, 400, 'Missing query (q).');
        try {
            const result = spawnSync('python3', ['-m', 'reports.nlquery', '--eval-stdin', '--db', DB_PATH],
                { cwd: PROJECT_ROOT, encoding: 'utf8', input: q, timeout: 30000 });
            if (result.status !== 0) {
                const details = (result.stderr || result.stdout || '').trim();
                return errorResponse(res, 500, `Query failed: ${details || result.status}`);
            }
            return jsonResponse(res, JSON.parse(result.stdout));
        } catch (error) {
            return errorResponse(res, 500, `Query failed: ${error.message}`);
        }
    }

    if (pathname === '/api/sensitivity') {
        // "Which lever moves profit most?" — reuses the scenario engine.
        let delta = Number(query.delta);
        if (!Number.isFinite(delta)) delta = 5;
        delta = Math.max(1, Math.min(50, delta));
        try {
            const result = spawnSync('python3', ['-m', 'reports.sensitivity', '--db', DB_PATH, '--delta', String(delta), '--json'],
                { cwd: PROJECT_ROOT, encoding: 'utf8', timeout: 30000 });
            if (result.status !== 0) {
                const details = (result.stderr || result.stdout || '').trim();
                return errorResponse(res, 500, `Sensitivity analysis failed: ${details || result.status}`);
            }
            return jsonResponse(res, JSON.parse(result.stdout));
        } catch (error) {
            return errorResponse(res, 500, `Sensitivity analysis failed: ${error.message}`);
        }
    }

    if (pathname === '/api/anomalies') {
        // The "passive guardian": deterministic, source-traceable anomaly
        // detection. Reuses the tested Python engine (reports/anomaly.py).
        try {
            const result = spawnSync('python3', ['-m', 'reports.anomaly', '--db', DB_PATH, '--json'],
                { cwd: PROJECT_ROOT, encoding: 'utf8', timeout: 30000 });
            if (result.status !== 0) {
                const details = (result.stderr || result.stdout || '').trim();
                return errorResponse(res, 500, `Anomaly detection failed: ${details || result.status}`);
            }
            return jsonResponse(res, JSON.parse(result.stdout));
        } catch (error) {
            return errorResponse(res, 500, `Anomaly detection failed: ${error.message}`);
        }
    }

    if (pathname === '/api/wiki/search') {
        // Knowledge-base search — delegates to the tested brain engine. Args are
        // passed as argv (no shell), and note ids are dictionary keys (no path
        // traversal), so user input can't reach the filesystem unsafely.
        const q = String(query.q || '').trim();
        if (!q) return jsonResponse(res, { query: '', match_count: 0, matches: [] });
        const limit = parseLimit(query.limit, 10);
        const result = spawnSync('python3', ['-m', 'brain.cli', '--search', q, '--limit', String(limit)],
            { cwd: PROJECT_ROOT, encoding: 'utf8', timeout: 20000 });
        if (result.status !== 0) {
            return errorResponse(res, 500, `Wiki search failed: ${(result.stderr || '').trim() || result.status}`);
        }
        try {
            return jsonResponse(res, JSON.parse(result.stdout));
        } catch (error) {
            return errorResponse(res, 500, 'Wiki search returned malformed output');
        }
    }

    if (pathname === '/api/wiki/note') {
        const id = String(query.id || '').trim();
        if (!id) return errorResponse(res, 400, 'Missing note id');
        const result = spawnSync('python3', ['-m', 'brain.cli', '--note', id],
            { cwd: PROJECT_ROOT, encoding: 'utf8', timeout: 20000 });
        let body;
        try {
            body = JSON.parse(result.stdout);
        } catch (error) {
            return errorResponse(res, 500, 'Wiki note returned malformed output');
        }
        if (body && body.error) return errorResponse(res, 404, body.error);
        return jsonResponse(res, body);
    }

    if (pathname === '/api/reports') {
        return jsonResponse(res, {
            reports: REPORT_DEFINITIONS.map(r => ({ name: r.name, title: r.title, description: r.description })),
            exportFormats: getExportCapabilities()
        });
    }

    if (pathname === '/api/import-health') {
        const def = REPORT_DEFINITIONS.find(r => r.name === 'import_validation');
        let checks = [];
        if (def) {
            try {
                checks = reportEnvelope(def).rows;
            } catch (error) {
                return errorResponse(res, 500, `Import health failed: ${error.message}`);
            }
        }
        const warn = checks.filter(c => String(c.status).toUpperCase() === 'WARN').length;
        const ok = checks.filter(c => String(c.status).toUpperCase() === 'OK').length;
        return jsonResponse(res, {
            summary: { ok, warn, total: checks.length, overall: warn > 0 ? 'WARN' : 'OK' },
            checks,
            history: readImportHistory()
        });
    }

    if (pathname === '/api/reports/generate') {
        const reportName = query.name;
        const def = REPORT_DEFINITIONS.find(r => r.name === reportName);
        if (!def) return errorResponse(res, 404, `Unknown report: ${reportName}. Use /api/reports to list.`);
        try {
            return jsonResponse(res, reportEnvelope(def));
        } catch (error) {
            return errorResponse(res, 500, `Report generation failed: ${error.message}`);
        }
    }

    if (pathname === '/api/reports/download') {
        const reportName = query.name;
        const format = String(query.format || 'csv').toLowerCase();
        const def = REPORT_DEFINITIONS.find(r => r.name === reportName);
        if (!def) return errorResponse(res, 404, `Unknown report: ${reportName}. Use /api/reports to list.`);
        if (!['csv', 'xlsx', 'pdf'].includes(format)) {
            return errorResponse(res, 400, 'Invalid format. Use csv, xlsx, or pdf.');
        }
        if (format !== 'csv' && !getExportCapabilities()[format]) {
            return jsonResponse(res, {
                error: `${format.toUpperCase()} export is not available on this server.`,
                code: 'export_unavailable',
                format: format,
                hint: format === 'xlsx'
                    ? 'Install report dependencies (pip install openpyxl) — see setup.sh or reports/requirements.txt. CSV export always works.'
                    : 'Install report dependencies (pip install reportlab) — see setup.sh or reports/requirements.txt. CSV export always works.'
            }, 503);
        }
        try {
            if (format === 'csv') {
                return sendDownload(res, `${reportName}.csv`, 'text/csv; charset=utf-8', reportCsvBuffer(reportEnvelope(def)));
            }
            const type = format === 'xlsx'
                ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                : 'application/pdf';
            return sendDownload(res, `${reportName}.${format}`, type, reportOfficeBuffer(reportName, format));
        } catch (error) {
            return errorResponse(res, 500, `Report download failed: ${error.message}`);
        }
    }

    return errorResponse(res, 404, 'Unknown API endpoint');
}

const server = http.createServer((req, res) => {
    securityHeaders(res);

    if (ACCESS_TOKEN) {
        const provided = (url.parse(req.url, true).query.access_token || '');
        const headerToken = (req.headers['authorization'] || '').replace(/^Bearer\s+/i, '');
        if (!tokenMatches(provided, ACCESS_TOKEN) && !tokenMatches(headerToken, ACCESS_TOKEN)) {
            return errorResponse(res, 401, 'Access token required. Use ?access_token= or Authorization: Bearer header.');
        }
    }
    const parsed = url.parse(req.url, true);
    const pathname = parsed.pathname;
    const startedAt = Date.now();

    res.on('finish', () => {
        console.log(`${res.statusCode} ${req.method} ${pathname} ${Date.now() - startedAt}ms`);
    });

    if (req.method !== 'GET' && req.method !== 'HEAD') {
        return errorResponse(res, 405, 'Method not allowed');
    }

    if (pathname.startsWith('/api/')) {
        try {
            return handleApi(pathname, parsed.query, res);
        } catch (error) {
            const clientError = /Invalid|must be different/.test(error.message);
            console.error(`API error ${pathname}: ${error.message}`);
            return errorResponse(res, clientError ? 400 : 500, error.message);
        }
    }

    if (pathname === '/') {
        return serveStatic(path.join(PROJECT_ROOT, 'index.html'), res);
    }
    if (pathname === '/favicon.ico') {
        res.writeHead(204);
        res.end();
        return;
    }

    let decodedPath;
    try {
        decodedPath = decodeURIComponent(pathname).replace(/^[/\\]+/, '');
    } catch (error) {
        return errorResponse(res, 400, 'Invalid URL path');
    }
    if (!PUBLIC_FILES.has(decodedPath)) {
        res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
        res.end('Not found');
        return;
    }
    serveStatic(path.join(PROJECT_ROOT, decodedPath), res);
});

function shutdown(signal) {
    console.log(`${signal} received, shutting down`);
    if (db) db.close();
    server.close(() => process.exit(0));
    setTimeout(() => process.exit(1), 5000).unref();
}

process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));

server.listen(PORT, HOST, () => {
    console.log(`Company Dashboard v4.2 listening at http://${HOST}:${PORT}`);
    if (ACCESS_TOKEN) console.log('Access token required for all requests.');
    console.log(`Backend: ${dbAvailable ? 'live SQLite queries' : 'fallback cache only'}`);
});
