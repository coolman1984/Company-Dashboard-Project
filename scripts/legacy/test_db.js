const Database = require('better-sqlite3');
const db = new Database('./pl_detail.db', { readonly: true });

// Check indexes
const indexes = db.prepare("SELECT name, sql FROM sqlite_master WHERE type='index'").all();
console.log('=== Existing Indexes ===');
indexes.forEach(i => console.log(i.name, ':', i.sql));

// Check views
const views = db.prepare("SELECT name FROM sqlite_master WHERE type='view'").all();
console.log('\n=== Existing Views ===');
views.forEach(v => console.log(v.name));

// Benchmark with version filter
let t1 = Date.now();
let r = db.prepare("SELECT region_desc, year, SUM(net_sales) as net_sales, SUM(cost_of_goods_sold) as cogs, SUM(gross_margin) as gross_margin, SUM(operating_expense) as opex, SUM(operating_profit) as operating_profit, SUM(net_income) as net_income FROM pl_detail WHERE version='Actual' GROUP BY region_desc, year ORDER BY region_desc, year").all();
console.log('\nRegional query (Actual only):', Date.now() - t1, 'ms,', r.length, 'rows');

// Benchmark drilldown-style query
t1 = Date.now();
r = db.prepare("SELECT region_desc as dimension, SUM(CASE WHEN year=2025 THEN net_sales ELSE 0 END) as val_year1, SUM(CASE WHEN year=2026 THEN net_sales ELSE 0 END) as val_year2 FROM pl_detail WHERE version='Actual' AND year IN (2025,2026) GROUP BY region_desc ORDER BY ABS(SUM(CASE WHEN year=2026 THEN net_sales ELSE 0 END) - SUM(CASE WHEN year=2025 THEN net_sales ELSE 0 END)) DESC").all();
console.log('Drilldown query:', Date.now() - t1, 'ms,', r.length, 'rows');
r.forEach(row => {
    row.change = row.val_year2 - row.val_year1;
    row.pct_change = row.val_year1 !== 0 ? Math.round(row.change / Math.abs(row.val_year1) * 10000) / 100 : null;
});
console.log('Sample drilldown:', JSON.stringify(r[0]));

// Get distinct versions
const versions = db.prepare("SELECT DISTINCT version FROM pl_detail ORDER BY version").all();
console.log('\nVersions:', versions.map(v => v.version).join(', '));

// Get distinct years
const years = db.prepare("SELECT DISTINCT year FROM pl_detail ORDER BY year").all();
console.log('Years:', years.map(y => y.year).join(', '));

db.close();
