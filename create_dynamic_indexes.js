const Database = require('better-sqlite3');
const db = new Database('./pl_detail.db');

console.log('Creating optimized covering indexes for dynamic queries...');

// Composite index for version+year (covers most GROUP BY queries)
const t1 = Date.now();
db.exec("CREATE INDEX IF NOT EXISTS idx_version_year ON pl_detail (version, year)");
console.log('idx_version_year:', Date.now() - t1, 'ms');

// Composite index for version+year+region (regional queries)
let t2 = Date.now();
db.exec("CREATE INDEX IF NOT EXISTS idx_version_year_region ON pl_detail (version, year, region_desc)");
console.log('idx_version_year_region:', Date.now() - t2, 'ms');

// Composite index for version+year+mgroup (product queries)
t2 = Date.now();
db.exec("CREATE INDEX IF NOT EXISTS idx_version_year_mgroup ON pl_detail (version, year, m_group_desc)");
console.log('idx_version_year_mgroup:', Date.now() - t2, 'ms');

// Composite index for version+year+country
t2 = Date.now();
db.exec("CREATE INDEX IF NOT EXISTS idx_version_year_country ON pl_detail (version, year, country_name)");
console.log('idx_version_year_country:', Date.now() - t2, 'ms');

// Composite index for version+year+customer
t2 = Date.now();
db.exec("CREATE INDEX IF NOT EXISTS idx_version_year_customer ON pl_detail (version, year, customer_name)");
console.log('idx_version_year_customer:', Date.now() - t2, 'ms');

// Composite index for version+year+class
t2 = Date.now();
db.exec("CREATE INDEX IF NOT EXISTS idx_version_year_class ON pl_detail (version, year, class)");
console.log('idx_version_year_class:', Date.now() - t2, 'ms');

console.log('\nTotal indexing time:', Date.now() - t1, 'ms');

// Now benchmark again
console.log('\n=== Benchmarks After Indexing ===');
let t = Date.now();
let r = db.prepare("SELECT region_desc, year, SUM(net_sales) as net_sales, SUM(cost_of_goods_sold) as cogs, SUM(gross_margin) as gross_margin, SUM(operating_expense) as opex, SUM(operating_profit) as operating_profit, SUM(net_income) as net_income FROM pl_detail WHERE version='Actual' GROUP BY region_desc, year ORDER BY region_desc, year").all();
console.log('Regional query:', Date.now() - t, 'ms,', r.length, 'rows');

t = Date.now();
r = db.prepare("SELECT region_desc as dimension, SUM(CASE WHEN year=2025 THEN net_sales ELSE 0 END) as val_year1, SUM(CASE WHEN year=2026 THEN net_sales ELSE 0 END) as val_year2 FROM pl_detail WHERE version='Actual' AND year IN (2025,2026) GROUP BY region_desc ORDER BY ABS(SUM(CASE WHEN year=2026 THEN net_sales ELSE 0 END) - SUM(CASE WHEN year=2025 THEN net_sales ELSE 0 END)) DESC").all();
console.log('Drilldown query:', Date.now() - t, 'ms,', r.length, 'rows');

t = Date.now();
r = db.prepare("SELECT year, SUM(net_sales) as net_sales, SUM(cost_of_goods_sold) as cogs, SUM(gross_margin) as gross_margin, SUM(operating_expense) as opex, SUM(operating_profit) as operating_profit, SUM(net_income) as net_income FROM pl_detail WHERE version='Actual' GROUP BY year ORDER BY year").all();
console.log('Yearly PL query:', Date.now() - t, 'ms,', r.length, 'rows');

db.close();
console.log('\nDone!');
