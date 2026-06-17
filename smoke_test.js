const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');

const port = 32100 + Math.floor(Math.random() * 500);
const baseUrl = `http://127.0.0.1:${port}`;
const server = spawn(process.execPath, ['server.js'], {
    cwd: __dirname,
    env: { ...process.env, PORT: String(port) },
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true
});

let serverOutput = '';
server.stdout.on('data', chunk => { serverOutput += chunk.toString(); });
server.stderr.on('data', chunk => { serverOutput += chunk.toString(); });

async function waitForServer() {
    for (let attempt = 0; attempt < 40; attempt++) {
        try {
            const response = await fetch(`${baseUrl}/api/status`);
            if (response.ok) return;
        } catch (error) {
            // The process is still starting.
        }
        await new Promise(resolve => setTimeout(resolve, 250));
    }
    throw new Error(`Server did not start.\n${serverOutput}`);
}

async function getJson(path) {
    const response = await fetch(baseUrl + path);
    const body = await response.json();
    return { response, body };
}

async function run() {
    await waitForServer();

    const home = await fetch(baseUrl + '/');
    assert.equal(home.status, 200);
    const homeHtml = await home.text();
    assert.match(homeHtml, /Company Finance Command Center/);
    assert.match(homeHtml, /app-shell/);
    assert.match(homeHtml, /globalRegion/);

    assert.equal((await fetch(baseUrl + '/app.js')).status, 200);
    assert.equal((await fetch(baseUrl + '/favicon.ico')).status, 204);
    assert.equal((await fetch(baseUrl + '/pl_detail.db')).status, 404);
    assert.equal((await fetch(baseUrl + '/server.js')).status, 404);
    assert.equal((await fetch(baseUrl + '/PL%202022~2026.xlsb')).status, 404);

    const status = await getJson('/api/status');
    assert.equal(status.response.status, 200);
    assert.equal(status.body.status, 'ok');
    assert.equal(status.body.backend, 'sqlite-live');
    assert.equal('databasePath' in status.body, false);
    assert.equal('cacheKeys' in status.body, false);

    const filters = await getJson('/api/filters');
    assert.equal(filters.response.status, 200);
    assert.ok(filters.body.years.includes(2026));
    assert.ok(filters.body.versions.includes('Actual'));
    assert.ok(filters.body.regions.length > 0);

    // Use a real region value from the database so the suite passes against any
    // locale (English or Arabic seed) — never hard-code dimension names.
    const region = filters.body.regions[0];
    const regionQ = encodeURIComponent(region);

    const regionalFilters = await getJson(`/api/filters?region=${regionQ}`);
    assert.equal(regionalFilters.response.status, 200);
    assert.ok(regionalFilters.body.countries.length > 0);

    const freshness = await getJson('/api/data-freshness');
    assert.equal(freshness.response.status, 200);
    assert.equal(freshness.body.years['2026'].Actual.periodCount, 5);
    assert.equal(freshness.body.years['2026'].T06.periodCount, 1);
    assert.equal(freshness.body.years['2026'].T07.periodCount, 6);

    const scenario = await getJson('/api/scenario-pl');
    assert.equal(scenario.response.status, 200);
    assert.ok(scenario.body.some(row => row.year === 2026 && row.actual_net_sales != null));

    const executive = await getJson('/api/executive-outlook');
    assert.equal(executive.response.status, 200);
    assert.equal(executive.body.monthly.length, 12);
    assert.equal(executive.body.monthly.filter(row => row.status === 'actual').length, 5);
    assert.equal(executive.body.monthly.filter(row => row.status === 'outlook').length, 7);
    assert.ok(executive.body.outlook.net_sales > 0);
    assert.ok(executive.body.priorYear.net_sales > 0);
    assert.ok(executive.body.concentration.customers.length > 0);
    assert.ok(executive.body.profitability.length > 0);
    const monthlyRevenue = executive.body.monthly.reduce((sum, row) => sum + row.net_sales, 0);
    assert.ok(Math.abs(monthlyRevenue - executive.body.outlook.net_sales) < 0.01);

    const executiveRegion = await getJson(`/api/executive-outlook?region=${regionQ}`);
    assert.equal(executiveRegion.response.status, 200);
    assert.equal(executiveRegion.body.monthly.length, 12);
    assert.ok(executiveRegion.body.outlook.net_sales < executive.body.outlook.net_sales);

    const yearly = await getJson(`/api/yearly-pl?version=Actual&region=${regionQ}`);
    assert.equal(yearly.response.status, 200);
    assert.ok(yearly.body.length > 0);
    assert.ok(yearly.body.every(row => row.net_sales != null));

    const product = await getJson(`/api/mgroup-pl?version=Actual&year=2025&region=${regionQ}`);
    assert.equal(product.response.status, 200);
    assert.ok(product.body.length > 0);

    const country = await getJson(`/api/country-pl?version=Actual&region=${regionQ}`);
    assert.equal(country.response.status, 200);
    assert.ok(country.body.length > 0);

    const customer = await getJson(`/api/customer-pl?version=Actual&year=2025&region=${regionQ}&limit=10`);
    assert.equal(customer.response.status, 200);
    assert.ok(customer.body.length > 0);

    const topProducts = await getJson(`/api/top-products?version=Actual&year=2025&region=${regionQ}&limit=10`);
    assert.equal(topProducts.response.status, 200);
    assert.ok(topProducts.body.length > 0);

    const drilldown = await getJson('/api/drilldown?dimension=class&year1=2026&year2=2022&metric=net_sales');
    assert.equal(drilldown.response.status, 200);
    assert.ok(drilldown.body.length > 0);

    const invalid = await getJson('/api/drilldown?dimension=not_a_column&year1=2025&year2=2026&metric=net_sales');
    assert.equal(invalid.response.status, 400);

    const reports = await getJson('/api/reports');
    assert.equal(reports.response.status, 200);
    assert.equal(reports.body.reports.length, 9);
    assert.ok(reports.body.reports.some(report => report.name === 'import_validation'));
    // The reports list advertises which export formats this server can fulfil.
    assert.ok(reports.body.exportFormats, 'reports response must advertise exportFormats');
    assert.equal(reports.body.exportFormats.csv, true);
    assert.equal(typeof reports.body.exportFormats.xlsx, 'boolean');
    assert.equal(typeof reports.body.exportFormats.pdf, 'boolean');

    // Office exports degrade gracefully: when a format is unavailable the server
    // returns a clean 503 with a machine-readable code, never a raw 500 traceback.
    for (const format of ['xlsx', 'pdf']) {
        const dl = await fetch(baseUrl + `/api/reports/download?name=yearly_pl&format=${format}`);
        if (reports.body.exportFormats[format]) {
            assert.equal(dl.status, 200, `${format} export should succeed when available`);
        } else {
            assert.equal(dl.status, 503, `${format} export should return 503 when unavailable`);
            const body = await dl.json();
            assert.equal(body.code, 'export_unavailable');
        }
    }

    const reportJson = await getJson('/api/reports/generate?name=import_validation');
    assert.equal(reportJson.response.status, 200);
    assert.ok(reportJson.body.rows.some(row => row.category === 'Lineage'));

    const health = await getJson('/api/import-health');
    assert.equal(health.response.status, 200);
    assert.ok(health.body.summary, 'import-health must include a summary');
    assert.ok(['OK', 'WARN'].includes(health.body.summary.overall));
    assert.ok(Array.isArray(health.body.checks) && health.body.checks.length > 0);
    assert.ok(health.body.checks.some(c => c.category === 'Lineage'));
    assert.ok(Array.isArray(health.body.history));

    // Interactive what-if levers: a no-op scenario reproduces the baseline exactly,
    // and a real lever moves net income.
    const nl = await getJson('/api/nl-query?q=' + encodeURIComponent('net sales by region'));
    assert.equal(nl.response.status, 200);
    assert.equal(nl.body.metric, 'net_sales');
    assert.equal(nl.body.query.group_by, 'region_desc');
    assert.ok(Array.isArray(nl.body.rows) && nl.body.rows.length > 0);
    assert.ok(typeof nl.body.interpretation === 'string' && nl.body.interpretation.length > 0);
    const nlBad = await fetch(baseUrl + '/api/nl-query');
    assert.equal(nlBad.status, 400);

    const compare = await getJson('/api/scenario-compare');
    assert.equal(compare.response.status, 200);
    assert.deepEqual(compare.body.scenarios, ['Conservative', 'Base', 'Aggressive']);
    assert.ok(compare.body.rows.length > 0);
    const niCmp = compare.body.rows.find(r => r.line_item === 'Net Income');
    assert.ok(niCmp && niCmp.Base === niCmp.baseline);

    // One-click board pack: 200 when export libs are present, else a clean 503.
    const pack = await fetch(baseUrl + '/api/reports/board-pack?format=pdf');
    if (reports.body.exportFormats.pdf) {
        assert.equal(pack.status, 200);
        assert.match(pack.headers.get('content-disposition') || '', /board-pack\.pdf/);
    } else {
        assert.equal(pack.status, 503);
    }

    const ack = await getJson('/api/guardian/ack');
    assert.equal(ack.response.status, 200);
    assert.equal(ack.body.ok, true);

    const sensitivity = await getJson('/api/sensitivity?delta=5');
    assert.equal(sensitivity.response.status, 200);
    assert.ok(Array.isArray(sensitivity.body.rows) && sensitivity.body.rows.length === 3);
    assert.ok(sensitivity.body.most_sensitive);
    // ranked by absolute swing
    const sw = sensitivity.body.rows.map(r => Math.abs(r.swing));
    for (let i = 1; i < sw.length; i++) assert.ok(sw[i - 1] >= sw[i]);

    const anomalies = await getJson('/api/anomalies');
    assert.equal(anomalies.response.status, 200);
    assert.ok(typeof anomalies.body.count === 'number');
    assert.ok(Array.isArray(anomalies.body.anomalies));
    assert.ok(anomalies.body.by_severity && typeof anomalies.body.by_severity === 'object');
    // Each anomaly must be source-traceable.
    anomalies.body.anomalies.forEach(a => {
        assert.ok(a.type && a.severity && a.source && a.source.metric);
    });

    const wiki = await getJson('/api/wiki/search?q=margin&limit=5');
    assert.equal(wiki.response.status, 200);
    assert.ok(Array.isArray(wiki.body.matches));
    if (wiki.body.matches.length) {
        const note = await getJson('/api/wiki/note?id=' + encodeURIComponent(wiki.body.matches[0].note));
        assert.equal(note.response.status, 200);
        assert.ok(typeof note.body.body === 'string' && note.body.title);
        const missing = await fetch(baseUrl + '/api/wiki/note?id=__no_such_note__');
        assert.equal(missing.status, 404);
    }

    const narrative = await getJson('/api/executive-narrative');
    assert.equal(narrative.response.status, 200);
    assert.ok(narrative.body.headline && typeof narrative.body.headline.net_income === 'number');
    assert.ok(['up', 'down', 'flat'].includes(narrative.body.headline.net_income_dir));
    assert.ok(Array.isArray(narrative.body.topChanges));
    assert.ok(Array.isArray(narrative.body.risks));
    assert.ok(narrative.body.sourceConfidence && ['OK', 'WARN'].includes(narrative.body.sourceConfidence.overall));

    const whatifFlat = await getJson('/api/scenario-whatif?ns=0&cogs=0&opex=0&tax=22');
    assert.equal(whatifFlat.response.status, 200);
    assert.ok(Array.isArray(whatifFlat.body.rows) && whatifFlat.body.rows.length > 0);
    const niFlat = whatifFlat.body.rows.find(r => r.line_item === 'Net Income');
    assert.ok(niFlat && Math.abs(niFlat.scenario - niFlat.baseline) < 0.01);

    const whatif = await getJson('/api/scenario-whatif?ns=10&opex=-5&tax=22&scales=true');
    assert.equal(whatif.response.status, 200);
    const ni = whatif.body.rows.find(r => r.line_item === 'Net Income');
    assert.ok(ni && ni.scenario > ni.baseline, 'positive sales + lower opex should lift net income');

    const reportCsv = await fetch(baseUrl + '/api/reports/download?name=yearly_pl&format=csv');
    assert.equal(reportCsv.status, 200);
    assert.match(reportCsv.headers.get('content-disposition') || '', /yearly_pl\.csv/);
    assert.match(await reportCsv.text(), /net_sales/);

    console.log('Smoke tests passed.');
}

run()
    .catch(error => {
        console.error(error);
        process.exitCode = 1;
    })
    .finally(() => {
        server.kill('SIGTERM');
    });
