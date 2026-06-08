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
    assert.match(await home.text(), /Data coverage:/);

    assert.equal((await fetch(baseUrl + '/app.js')).status, 200);
    assert.equal((await fetch(baseUrl + '/favicon.ico')).status, 204);
    assert.equal((await fetch(baseUrl + '/pl_detail.db')).status, 404);
    assert.equal((await fetch(baseUrl + '/server.js')).status, 404);
    assert.equal((await fetch(baseUrl + '/PL%202022~2026.xlsb')).status, 404);

    const status = await getJson('/api/status');
    assert.equal(status.response.status, 200);
    assert.equal(status.body.status, 'ok');
    assert.equal('databasePath' in status.body, false);
    assert.equal('cacheKeys' in status.body, false);

    const freshness = await getJson('/api/data-freshness');
    assert.equal(freshness.response.status, 200);
    assert.equal(freshness.body.years['2026'].Actual.periodCount, 5);
    assert.equal(freshness.body.years['2026'].T06.periodCount, 1);
    assert.equal(freshness.body.years['2026'].T07.periodCount, 6);

    const scenario = await getJson('/api/scenario-pl');
    assert.equal(scenario.response.status, 200);
    assert.ok(scenario.body.some(row => row.year === 2026 && row.actual_net_sales != null));

    const drilldown = await getJson('/api/drilldown?dimension=class&year1=2026&year2=2022&metric=net_sales');
    assert.equal(drilldown.response.status, 200);
    assert.ok(drilldown.body.length > 0);

    const invalid = await getJson('/api/drilldown?dimension=not_a_column&year1=2025&year2=2026&metric=net_sales');
    assert.equal(invalid.response.status, 400);

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
