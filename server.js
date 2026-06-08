/**
 * Company Dashboard v4 - dynamic SQLite analytics server.
 *
 * Every dashboard endpoint queries pl_detail.db at request time. Precomputed
 * JSON is retained only as a cache-only fallback when SQLite is unavailable.
 */
const http = require('http');
const fs = require('fs');
const path = require('path');
const url = require('url');

const PORT = Number(process.env.PORT) || 3001;
const PROJECT_ROOT = path.resolve(__dirname);
const PROJECT_ROOT_PREFIX = PROJECT_ROOT.endsWith(path.sep) ? PROJECT_ROOT : PROJECT_ROOT + path.sep;
const DB_PATH = path.join(__dirname, 'pl_detail.db');
const API_DATA_DIR = path.join(__dirname, 'api_data');
const PUBLIC_FILES = new Set(['index.html', 'app.js']);

const VALID_DIMENSIONS = ['region_desc', 'country_name', 'm_group_desc', 'customer_name', 'class'];
const VALID_METRICS = ['net_sales', 'cost_of_goods_sold', 'gross_margin', 'operating_expense', 'operating_profit', 'net_income'];
const VALID_VERSIONS = ['Actual', 'T06', 'T07'];
const VALID_YEARS = [2022, 2023, 2024, 2025, 2026];
const MAX_LIMIT = 500;

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
    '.js': 'application/javascript; charset=utf-8'
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
        "script-src 'self' https://cdn.jsdelivr.net",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src https://fonts.gstatic.com",
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

function jsonResponse(res, data, statusCode = 200) {
    res.writeHead(statusCode, {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'no-store'
    });
    res.end(JSON.stringify(normalizeAliases(data)));
}

function errorResponse(res, statusCode, message) {
    jsonResponse(res, { error: message }, statusCode);
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
        note: '2026 Actual covers P01-P05, T06 covers P06, and T07 covers P07-P12.'
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
    const year1 = parseInteger(query.year1, 2024);
    const year2 = parseInteger(query.year2, 2025);
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
    const params = [...where.params, year1, year2, year1, year2, limit];

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
            serverVersion: '4.0-dynamic'
        });
    }

    if (!dbAvailable) {
        const fallbackRoutes = {
            '/api/summary': ['summary', {}],
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
    if (pathname === '/api/drilldown') return jsonResponse(res, getDrilldown(query));
    if (pathname === '/api/top-products') return jsonResponse(res, getTopProducts(query));

    if (pathname === '/api/query') {
        const dimension = query.dimension;
        if (!VALID_DIMENSIONS.includes(dimension)) {
            throw new Error(`Invalid dimension. Use: ${VALID_DIMENSIONS.join(', ')}`);
        }
        const limit = parseLimit(query.limit, 100);
        const rows = getDimensionData(query, dimension);
        return jsonResponse(res, rows.slice(0, limit));
    }

    return errorResponse(res, 404, 'Unknown API endpoint');
}

const server = http.createServer((req, res) => {
    securityHeaders(res);
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

server.listen(PORT, () => {
    console.log(`Company Dashboard v4 listening at http://localhost:${PORT}`);
    console.log(`Backend: ${dbAvailable ? 'live SQLite queries' : 'fallback cache only'}`);
});
