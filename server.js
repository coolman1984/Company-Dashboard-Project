/**
 * PL Financial Analysis Server v2 — Pre-computed Static JSON Backend
 * 
 * All dashboard data is pre-computed as JSON files in api_data/ directory.
 * This server serves static JSON files with fs.readFileSync() for INSTANT responses.
 * No Python subprocess needed for any API call.
 * 
 * To refresh data: python precompute_data.py
 */
const http = require('http');
const fs = require('fs');
const path = require('path');
const url = require('url');

const PORT = 3001;
const API_DATA_DIR = path.join(__dirname, 'api_data');
const PROJECT_ROOT = path.resolve(__dirname);

// Pre-load all JSON data into memory for instant access
const cache = {};

function loadData() {
    if (!fs.existsSync(API_DATA_DIR)) {
        console.warn('WARN: api_data/ directory not found. Run: python precompute_data.py');
        console.warn('Server starting with empty cache — some endpoints will return empty data.');
        return 0;
    }
    
    const files = fs.readdirSync(API_DATA_DIR).filter(f => f.endsWith('.json'));
    let count = 0;
    files.forEach(f => {
        const key = f.replace('.json', '');
        try {
            const data = JSON.parse(fs.readFileSync(path.join(API_DATA_DIR, f), 'utf-8'));
            // Add field aliases: cogs -> cost_of_goods_sold, opex -> operating_expense
            if (Array.isArray(data)) {
                data.forEach(function(row) {
                    if (row.cogs !== undefined) row.cost_of_goods_sold = row.cogs;
                    if (row.opex !== undefined) row.operating_expense = row.opex;
                });
            }
            cache[key] = data;
            count++;
        } catch (e) {
            console.error(`  WARN: Failed to load ${f}: ${e.message}`);
        }
    });
    console.log(`Loaded ${count} pre-computed data files into memory`);
    return count;
}

// Load all data at startup
const dataCount = loadData();
if (dataCount === 0) {
    console.warn('WARN: No data files loaded! Run: python precompute_data.py');
    console.warn('Server starting with empty cache.');
}

const MIME_TYPES = {
    '.html': 'text/html',
    '.css': 'text/css',
    '.js': 'application/javascript',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.svg': 'image/svg+xml',
};

function serveStatic(filePath, res) {
    const safePath = path.resolve(filePath);
    if (!safePath.startsWith(PROJECT_ROOT)) {
        res.writeHead(403);
        res.end('Forbidden');
        return;
    }
    const ext = path.extname(safePath);
    const contentType = MIME_TYPES[ext] || 'application/octet-stream';
    fs.readFile(safePath, (err, data) => {
        if (err) {
            res.writeHead(404);
            res.end('Not found');
        } else {
            res.writeHead(200, { 'Content-Type': contentType });
            res.end(data);
        }
    });
}

function jsonResponse(res, data) {
    res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'public, max-age=300' });
    res.end(JSON.stringify(data));
}

function errorResponse(res, code, msg) {
    res.writeHead(code, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: msg }));
}

const server = http.createServer((req, res) => {
    const parsed = url.parse(req.url, true);
    const pathname = parsed.pathname;
    const startTime = Date.now();
    
    // CORS headers
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    
    res.on('finish', () => {
        const ms = Date.now() - startTime;
        console.log(`${res.statusCode} ${req.method} ${pathname} — ${ms}ms`);
    });
    
    if (req.method === 'OPTIONS') {
        res.writeHead(200);
        res.end();
        return;
    }
    
    // ===== API Routes — all served from in-memory cache (instant) =====
    if (pathname.startsWith('/api/')) {
        try {
            // 1. Summary
            if (pathname === '/api/summary') {
                return jsonResponse(res, cache['summary'] || { error: 'summary data not found' });
            }
            
            // 2. Yearly PL
            if (pathname === '/api/yearly-pl') {
                return jsonResponse(res, cache['yearly-pl'] || []);
            }
            
            // 3. Regional PL
            if (pathname === '/api/regional-pl') {
                return jsonResponse(res, cache['regional-pl'] || []);
            }
            
            // 4. Product group PL
            if (pathname === '/api/mgroup-pl') {
                return jsonResponse(res, cache['mgroup-pl'] || []);
            }
            
            // Scenario PL (Actual vs Forecast)
            if (pathname === '/api/scenario-pl') {
                return jsonResponse(res, cache['scenario-pl'] || []);
            }
            
            // 5. Country PL (optional region filter)
            if (pathname === '/api/country-pl') {
                const region = parsed.query.region;
                let data = cache['country-pl'] || [];
                if (region && data.length) {
                    data = data.filter(r => r.region_desc === region);
                }
                return jsonResponse(res, data);
            }
            
            // 6. Customer PL (optional year filter)
            if (pathname === '/api/customer-pl') {
                const year = parseInt(parsed.query.year);
                const limit = parseInt(parsed.query.limit) || 20;
                let data = cache['customer-pl'] || [];
                if (year && data.length) {
                    data = data.filter(r => r.year === year);
                }
                return jsonResponse(res, data.slice(0, limit));
            }
            
            // 7. YoY Variance
            if (pathname === '/api/yoy-variance') {
                return jsonResponse(res, cache['yoy-variance'] || []);
            }
            
            // 8. Drill-down — served from pre-computed files or computed from cached view data
            if (pathname === '/api/drilldown') {
                const dimension = parsed.query.dimension || 'region_desc';
                const year1 = parseInt(parsed.query.year1) || 2024;
                const year2 = parseInt(parsed.query.year2) || 2025;
                const metric = parsed.query.metric || 'net_sales';
                
                const validDims = ['region_desc', 'country_name', 'm_group_desc', 'customer_name', 'class'];
                const validMetrics = ['net_sales', 'cost_of_goods_sold', 'gross_margin', 'operating_expense', 'operating_profit', 'net_income'];
                
                if (!validDims.includes(dimension) || !validMetrics.includes(metric)) {
                    return errorResponse(res, 400, 'Invalid dimension or metric');
                }
                
                // If year1 > year2, fetch the pre-computed file for (year2, year1) and invert it
                const invertYears = year1 > year2;
                const y1 = invertYears ? year2 : year1;
                const y2 = invertYears ? year1 : year2;
                
                // Try pre-computed file first
                const cacheKey = `drilldown_${dimension}_${metric}_${y1}_${y2}`;
                if (cache[cacheKey]) {
                    let data = cache[cacheKey];
                    if (invertYears) {
                        data = data.map(function(row) {
                            const newRow = Object.assign({}, row);
                            const val1 = row.val_year1;
                            const val2 = row.val_year2;
                            newRow.val_year1 = val2;
                            newRow.val_year2 = val1;
                            newRow.change = val1 - val2;
                            newRow.pct_change = val2 !== 0 ? Math.round(newRow.change / Math.abs(val2) * 10000) / 100 : null;
                            return newRow;
                        });
                        // Re-sort by absolute change DESC after inverting
                        data = data.slice().sort(function(a, b) { return Math.abs(b.change) - Math.abs(a.change); });
                    }
                    return jsonResponse(res, data);
                }
                
                // Fallback: compute from cached view data on-the-fly
                // This handles any year pair / dimension / metric combination
                const viewMap = {
                    'region_desc': 'regional-pl',
                    'country_name': 'country-pl',
                    'm_group_desc': 'mgroup-pl',
                    'customer_name': 'customer-pl',
                };
                
                const viewKey = viewMap[dimension];
                if (viewKey && cache[viewKey]) {
                    const allData = cache[viewKey];
                    // Group by dimension value
                    const groups = {};
                    allData.forEach(function(row) {
                        if (row.year !== year1 && row.year !== year2) return;
                        const key = row[dimension];
                        if (!key) return;
                        if (!groups[key]) groups[key] = { dimension: key, val_year1: 0, val_year2: 0 };
                        if (row.year === year1) groups[key].val_year1 += (row[metric] || 0);
                        if (row.year === year2) groups[key].val_year2 += (row[metric] || 0);
                    });
                    
                    // Compute change and sort
                    const result = Object.values(groups)
                        .filter(function(g) { return g.val_year1 !== 0 || g.val_year2 !== 0; })
                        .map(function(g) {
                            g.change = g.val_year2 - g.val_year1;
                            g.pct_change = g.val_year1 !== 0 ? Math.round(g.change / Math.abs(g.val_year1) * 10000) / 100 : null;
                            return g;
                        })
                        .sort(function(a, b) { return Math.abs(b.change) - Math.abs(a.change); })
                        .slice(0, 30);
                    
                    return jsonResponse(res, result);
                }
                
                // Class dimension fallback: query directly from yearly-pl grouped by class
                if (dimension === 'class' && cache['yearly-pl']) {
                    const classCacheKey = `drilldown_class_fallback_${metric}_${year1}_${year2}`;
                    if (cache[classCacheKey]) {
                        return jsonResponse(res, cache[classCacheKey]);
                    }
                    // Compute on-the-fly from regional-pl data if available
                    const fallbackView = cache['regional-pl'] || cache['country-pl'];
                    if (fallbackView) {
                        const groups = {};
                        fallbackView.forEach(function(row) {
                            if (row.year !== year1 && row.year !== year2) return;
                            const key = row.class || row.region_desc || 'All';
                            if (!groups[key]) groups[key] = { dimension: key, val_year1: 0, val_year2: 0 };
                            if (row.year === year1) groups[key].val_year1 += (row[metric] || 0);
                            if (row.year === year2) groups[key].val_year2 += (row[metric] || 0);
                        });
                        const result = Object.values(groups)
                            .filter(function(g) { return g.val_year1 !== 0 || g.val_year2 !== 0; })
                            .map(function(g) {
                                g.change = g.val_year2 - g.val_year1;
                                g.pct_change = g.val_year1 !== 0 ? Math.round(g.change / Math.abs(g.val_year1) * 10000) / 100 : null;
                                return g;
                            })
                            .sort(function(a, b) { return Math.abs(b.change) - Math.abs(a.change); })
                            .slice(0, 30);
                        return jsonResponse(res, result);
                    }
                    return jsonResponse(res, []);
                }

                return errorResponse(res, 404, `No data available for ${dimension}/${metric}/${year1}-${year2}`);
            }
            
            // 9. Top products for a year
            if (pathname === '/api/top-products') {
                const year = parseInt(parsed.query.year) || 2026;
                const cacheKey = `top_products_${year}`;
                return jsonResponse(res, cache[cacheKey] || []);
            }
            
            // 10. Data status / health check
            if (pathname === '/api/status') {
                return jsonResponse(res, {
                    status: 'ok',
                    cachedFiles: Object.keys(cache).length,
                    cacheKeys: Object.keys(cache).sort(),
                    serverVersion: '2.0-static'
                });
            }
            
            // Unknown endpoint
            return errorResponse(res, 404, 'Unknown API endpoint. Available: /api/summary, /api/yearly-pl, /api/regional-pl, /api/mgroup-pl, /api/country-pl, /api/customer-pl, /api/yoy-variance, /api/drilldown, /api/top-products, /api/status');
            
        } catch (err) {
            console.error('API Error:', err.message);
            return errorResponse(res, 500, err.message);
        }
    }
    
    // Static files
    if (pathname === '/') {
        serveStatic(path.join(__dirname, 'index.html'), res);
    } else {
        serveStatic(path.join(__dirname, pathname), res);
    }
});

server.listen(PORT, () => {
    console.log(`PL Analysis Server v2 running at http://localhost:${PORT}`);
    console.log(`Backend: Pre-computed static JSON (${Object.keys(cache).length} files in memory)`);
    console.log(`API endpoints (all instant, no Python subprocess):`);
    console.log(`  GET /api/summary       - Database summary & filter options`);
    console.log(`  GET /api/yearly-pl     - Yearly P&L summary`);
    console.log(`  GET /api/regional-pl   - Regional P&L by year`);
    console.log(`  GET /api/mgroup-pl     - Product group P&L by year`);
    console.log(`  GET /api/country-pl    - Country P&L (?region=X)`);
    console.log(`  GET /api/customer-pl   - Customer P&L (?year=X&limit=N)`);
    console.log(`  GET /api/yoy-variance  - Year-over-year variance`);
    console.log(`  GET /api/drilldown     - Variance drill-down (?dimension=X&year1=X&year2=X&metric=X)`);
    console.log(`  GET /api/top-products  - Top products per year (?year=X)`);
    console.log(`  GET /api/status        - Server status & cache info`);
});
