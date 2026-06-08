/**
 * PL Financial Analysis Dashboard - v2.0
 * Pre-computed static backend for instant API responses.
 * Data caching, lazy loading, error handling, toast notifications.
 */
const API = '';
const YEARS = [2022, 2023, 2024, 2025, 2026];
const C = { blue: '#3b82f6', green: '#059669', red: '#dc2626', orange: '#d97706', purple: '#7c3aed', teal: '#0d9488', gray: '#6b7280' };
const yearColors = ['#3b82f6', '#059669', '#d97706', '#7c3aed', '#dc2626'];

// PL Data from Sheet3 pivot (embedded for instant overview)
const PL = {
    'Net Sales': [1353213602.60, 1180194368.29, 1247757859.42, 1322784901.44, 1380306588.75],
    'Cost of Goods Sold': [1043100561.96, 867388388.22, 983655749.07, 1062132471.48, 1246671103.88],
    'Gross Margin': [310113040.64, 312805980.07, 264102110.35, 260652429.96, 133635484.87],
    'Operating Expense': [142798312.08, 133798945.98, 164632661.07, 149159606.32, 172522351.03],
    'Operating Profit': [167314728.56, 179007034.09, 99469449.28, 111492823.64, -38886866.16],
    'Net Income': [78159959.08, 119641588.33, -121986318.03, 114969216.64, -56453267.60],
    'Overhead': [317903926.21, 261799426.21, 458519716.71, 218027675.92, 293981243.53],
};

// ===== Utility Functions =====
function fmtM(n) {
    if (n == null) return '--';
    const a = Math.abs(n);
    if (a >= 1e9) return (n / 1e9).toFixed(2) + 'B';
    if (a >= 1e6) return (n / 1e6).toFixed(2) + 'M';
    if (a >= 1e3) return (n / 1e3).toFixed(1) + 'K';
    return n.toFixed(2);
}

function fmtFull(n) {
    return n == null ? '--' : n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtPct(n) {
    return n == null ? '--' : (n * 100).toFixed(1) + '%';
}

function pctChg(a, b) {
    if (!a || a === 0) return null;
    return (b - a) / Math.abs(a);
}

function showToast(msg, isError) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.className = 'toast' + (isError ? ' error' : '');
    setTimeout(function() { t.classList.add('show'); }, 10);
    setTimeout(function() { t.classList.remove('show'); }, 3000);
}

// Safe fetch with timeout and error handling
async function safeFetch(url, timeoutMs) {
    timeoutMs = timeoutMs || 10000;
    const controller = new AbortController();
    const timer = setTimeout(function() { controller.abort(); }, timeoutMs);
    try {
        const resp = await fetch(url, { signal: controller.signal });
        clearTimeout(timer);
        if (!resp.ok) {
            const errData = await resp.json().catch(function() { return {}; });
            throw new Error(errData.error || 'HTTP ' + resp.status);
        }
        return await resp.json();
    } catch (e) {
        clearTimeout(timer);
        if (e.name === 'AbortError') throw new Error('Request timed out');
        throw e;
    }
}

// ===== TABS with Lazy Loading =====
var tabLoaded = { overview: true, regional: false, product: false, drilldown: false };

document.querySelectorAll('.tab').forEach(function(t) {
    t.addEventListener('click', function() {
        document.querySelectorAll('.tab').forEach(function(x) { x.classList.remove('active'); });
        document.querySelectorAll('.panel').forEach(function(x) { x.classList.remove('active'); });
        t.classList.add('active');
        var tabName = t.dataset.tab;
        document.getElementById('panel-' + tabName).classList.add('active');

        // Lazy-load data on first tab visit
        if (!tabLoaded[tabName]) {
            if (tabName === 'regional') loadRegional();
            else if (tabName === 'product') loadProductAnalysis();
            else if (tabName === 'drilldown') loadDrilldown();
            tabLoaded[tabName] = true;
        }
    });
});

// ===== OVERVIEW KPIs =====
(function() {
    var g = document.getElementById('kpiGrid');
    var li = 4, pi = 3;
    var kpis = [
        { label: 'Net Sales 2026', value: fmtM(PL['Net Sales'][li]), sub: (pctChg(PL['Net Sales'][pi], PL['Net Sales'][li]) > 0 ? '▲ ' : '▼ ') + Math.abs(pctChg(PL['Net Sales'][pi], PL['Net Sales'][li]) * 100).toFixed(1) + '% vs 2025', pos: pctChg(PL['Net Sales'][pi], PL['Net Sales'][li]) > 0, cls: '' },
        { label: 'Gross Margin 2026', value: fmtM(PL['Gross Margin'][li]), sub: (pctChg(PL['Gross Margin'][pi], PL['Gross Margin'][li]) > 0 ? '▲ ' : '▼ ') + Math.abs(pctChg(PL['Gross Margin'][pi], PL['Gross Margin'][li]) * 100).toFixed(1) + '% vs 2025', pos: PL['Gross Margin'][li] > 0, cls: PL['Gross Margin'][li] > 0 ? 'success' : 'danger' },
        { label: 'Operating Profit 2026', value: fmtM(PL['Operating Profit'][li]), sub: PL['Operating Profit'][li] >= 0 ? 'Positive' : 'Negative', pos: PL['Operating Profit'][li] > 0, cls: PL['Operating Profit'][li] > 0 ? 'success' : 'danger' },
        { label: 'Net Income 2026', value: fmtM(PL['Net Income'][li]), sub: PL['Net Income'][li] >= 0 ? 'Profit' : 'Loss', pos: PL['Net Income'][li] > 0, cls: PL['Net Income'][li] > 0 ? 'success' : 'danger' },
        { label: 'Revenue CAGR (5Y)', value: ((Math.pow(PL['Net Sales'][4] / PL['Net Sales'][0], 0.25) - 1) * 100).toFixed(1) + '%', sub: 'Compound Annual Growth Rate', pos: Math.pow(PL['Net Sales'][4] / PL['Net Sales'][0], 0.25) - 1 > 0, cls: 'warning' },
        { label: 'Gross Margin % 2026', value: fmtPct(PL['Gross Margin'][4] / PL['Net Sales'][4]), sub: 'vs ' + fmtPct(PL['Gross Margin'][3] / PL['Net Sales'][3]) + ' in 2025', pos: PL['Gross Margin'][4] / PL['Net Sales'][4] > PL['Gross Margin'][3] / PL['Net Sales'][3], cls: 'warning' },
    ];
    g.innerHTML = kpis.map(function(k) {
        return '<div class="kpi-card ' + k.cls + '"><div class="kpi-label">' + k.label + '</div><div class="kpi-value">' + k.value + '</div><div class="kpi-sub ' + (k.pos ? 'pos' : 'neg') + '">' + k.sub + '</div></div>';
    }).join('');
})();

// ===== CHART 1: Revenue & Cost =====
new Chart(document.getElementById('revenueCostChart'), {
    type: 'bar',
    data: {
        labels: YEARS,
        datasets: [
            { label: 'Net Sales', data: PL['Net Sales'].map(function(v) { return v / 1e6; }), backgroundColor: C.blue, borderRadius: 5, barPercentage: 0.7 },
            { label: 'COGS', data: PL['Cost of Goods Sold'].map(function(v) { return v / 1e6; }), backgroundColor: C.red, borderRadius: 5, barPercentage: 0.7 },
            { label: 'Gross Margin', data: PL['Gross Margin'].map(function(v) { return v / 1e6; }), backgroundColor: C.green, borderRadius: 5, barPercentage: 0.7 }
        ]
    },
    options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'top', labels: { usePointStyle: true, padding: 14 } }, tooltip: { callbacks: { label: function(c) { return c.dataset.label + ': $' + c.parsed.y.toFixed(1) + 'M'; } } } },
        scales: { y: { beginAtZero: true, title: { display: true, text: '$ Millions' }, ticks: { callback: function(v) { return '$' + v + 'M'; } } } }
    }
});

// ===== CHART 2: Margins =====
new Chart(document.getElementById('marginChart'), {
    type: 'line',
    data: {
        labels: YEARS,
        datasets: [
            { label: 'Gross Margin %', data: YEARS.map(function(_, i) { return PL['Gross Margin'][i] / PL['Net Sales'][i] * 100; }), borderColor: C.green, tension: 0.3, pointRadius: 5, borderWidth: 2.5, fill: false },
            { label: 'Operating Margin %', data: YEARS.map(function(_, i) { return PL['Operating Profit'][i] / PL['Net Sales'][i] * 100; }), borderColor: C.blue, tension: 0.3, pointRadius: 5, borderWidth: 2.5, fill: false },
            { label: 'Net Income %', data: YEARS.map(function(_, i) { return PL['Net Income'][i] / PL['Net Sales'][i] * 100; }), borderColor: C.purple, tension: 0.3, pointRadius: 5, borderWidth: 2.5, fill: false }
        ]
    },
    options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'top', labels: { usePointStyle: true, padding: 14 } }, tooltip: { callbacks: { label: function(c) { return c.dataset.label + ': ' + c.parsed.y.toFixed(1) + '%'; } } } },
        scales: { y: { title: { display: true, text: 'Margin %' }, ticks: { callback: function(v) { return v + '%'; } } } }
    }
});

// ===== CHART 3: Net Income =====
var niVals = PL['Net Income'].map(function(v) { return v / 1e6; });
new Chart(document.getElementById('netIncomeChart'), {
    type: 'bar',
    data: { labels: YEARS, datasets: [{ label: 'Net Income', data: niVals, backgroundColor: niVals.map(function(v) { return v >= 0 ? C.green : C.red; }), borderRadius: 5, barPercentage: 0.6 }] },
    options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: function(c) { return '$' + c.parsed.y.toFixed(1) + 'M'; } } } },
        scales: { y: { title: { display: true, text: '$ Millions' }, ticks: { callback: function(v) { return '$' + v + 'M'; } } } }
    }
});

// ===== CHART 4: Cost Structure =====
new Chart(document.getElementById('costStructChart'), {
    type: 'bar',
    data: {
        labels: YEARS,
        datasets: [
            { label: 'COGS %', data: YEARS.map(function(_, i) { return PL['Cost of Goods Sold'][i] / PL['Net Sales'][i] * 100; }), backgroundColor: C.red, borderRadius: 4 },
            { label: 'OpEx %', data: YEARS.map(function(_, i) { return PL['Operating Expense'][i] / PL['Net Sales'][i] * 100; }), backgroundColor: C.orange, borderRadius: 4 },
            { label: 'Overhead %', data: YEARS.map(function(_, i) { return PL['Overhead'][i] / PL['Net Sales'][i] * 100; }), backgroundColor: C.purple, borderRadius: 4 }
        ]
    },
    options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'top', labels: { usePointStyle: true, padding: 14 } }, tooltip: { callbacks: { label: function(c) { return c.dataset.label + ': ' + c.parsed.y.toFixed(1) + '%'; } } } },
        scales: { y: { title: { display: true, text: '% of Net Sales' }, ticks: { callback: function(v) { return v + '%'; } } } }
    }
});

// ===== PL TABLE =====
(function() {
    var t = document.getElementById('plTable');
    var h = '<thead><tr><th>P&L Line Item</th>';
    YEARS.forEach(function(y) { h += '<th>FY ' + y + '</th>'; });
    for (var i = 1; i < YEARS.length; i++) h += '<th>' + YEARS[i - 1] + '→' + YEARS[i] + ' %</th>';
    h += '</tr></thead><tbody>';
    var items = [
        { n: 'Net Sales', k: 'Net Sales', t: 'r' },
        { n: 'Cost of Goods Sold', k: 'Cost of Goods Sold', t: 'c' },
        { n: 'Gross Margin', k: 'Gross Margin', t: 's' },
        { n: 'Operating Expense', k: 'Operating Expense', t: 'c' },
        { n: 'Operating Profit', k: 'Operating Profit', t: 's' },
        { n: 'Overhead', k: 'Overhead', t: 'c' },
        { n: 'Net Income', k: 'Net Income', t: 't' },
    ];
    items.forEach(function(it) {
        var rc = it.t === 't' ? 'total' : it.t === 's' ? 'subtotal' : '';
        h += '<tr class="' + rc + '"><td>' + it.n + '</td>';
        YEARS.forEach(function(_, i) {
            var v = PL[it.k][i];
            h += '<td class="' + (v < 0 ? 'neg' : '') + '">' + fmtFull(v) + '</td>';
        });
        for (var i = 1; i < YEARS.length; i++) {
            var c = pctChg(PL[it.k][i - 1], PL[it.k][i]);
            if (c !== null) {
                var p = c * 100;
                h += '<td class="' + (p >= 0 ? 'pos' : 'neg') + '" style="font-weight:600;font-size:11px">' + (p >= 0 ? '▲' : '▼') + ' ' + Math.abs(p).toFixed(1) + '%</td>';
            } else {
                h += '<td>--</td>';
            }
        }
        h += '</tr>';
    });
    h += '</tbody>';
    t.innerHTML = h;
})();

// ===== DATA CACHING =====
var regionalDataCache = null;
var mgroupDataCache = null;

// ===== REGIONAL ANALYSIS =====
var regChart = null;

async function loadRegional() {
    var metric = document.getElementById('regMetric').value;

    try {
        // Fetch only once, then cache
        if (!regionalDataCache) {
            regionalDataCache = await safeFetch(API + '/api/regional-pl');
        }
        var data = regionalDataCache;
        var regions = [];
        var seen = {};
        data.forEach(function(r) {
            if (r.region_desc && !seen[r.region_desc]) {
                seen[r.region_desc] = true;
                regions.push(r.region_desc);
            }
        });

        var datasets = YEARS.map(function(y, i) {
            return {
                label: String(y),
                data: regions.map(function(r) {
                    var row = data.find(function(d) { return d.year === y && d.region_desc === r; });
                    return row ? (row[metric] || 0) / 1e6 : 0;
                }),
                backgroundColor: yearColors[i],
                borderRadius: 3,
                barPercentage: 0.8
            };
        });

        if (regChart) regChart.destroy();
        regChart = new Chart(document.getElementById('regionalChart'), {
            type: 'bar',
            data: { labels: regions, datasets: datasets },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { position: 'top', labels: { usePointStyle: true, padding: 10 } }, tooltip: { callbacks: { label: function(c) { return c.dataset.label + ': $' + c.parsed.y.toFixed(1) + 'M'; } } } },
                scales: { y: { title: { display: true, text: '$ Millions' }, ticks: { callback: function(v) { return '$' + v + 'M'; } } }, x: { ticks: { font: { size: 11 } } } }
            }
        });

        // Table
        var tb = document.getElementById('regionalTable');
        var th = '<thead><tr><th>Region</th>';
        YEARS.forEach(function(y) { th += '<th>FY ' + y + '</th>'; });
        th += '</tr></thead><tbody>';
        regions.forEach(function(r) {
            th += '<tr><td>' + r + '</td>';
            YEARS.forEach(function(y) {
                var row = data.find(function(d) { return d.year === y && d.region_desc === r; });
                var v = row ? (row[metric] || 0) : 0;
                th += '<td class="' + (v < 0 ? 'neg' : '') + '">' + fmtM(v) + '</td>';
            });
            th += '</tr>';
        });
        th += '</tbody>';
        tb.innerHTML = th;
    } catch (e) {
        console.error('Regional load error:', e);
        showToast('Failed to load regional data: ' + e.message, true);
    }
}

// Metric change: instant re-render from cache
document.getElementById('regMetric').addEventListener('change', function() {
    if (regionalDataCache) loadRegional();
});

// ===== PRODUCT ANALYSIS =====
var prodChart = null, prodMarginChart = null;

async function loadProductAnalysis() {
    var y1 = parseInt(document.getElementById('prodYear').value);
    var y2 = parseInt(document.getElementById('prodYear2').value);
    var metric = document.getElementById('prodMetric').value;

    try {
        // Fetch only once, then cache
        if (!mgroupDataCache) {
            mgroupDataCache = await safeFetch(API + '/api/mgroup-pl');
        }
        var data = mgroupDataCache;
        var y1Data = data.filter(function(d) { return d.year === y1; }).sort(function(a, b) { return (b[metric] || 0) - (a[metric] || 0); }).slice(0, 15);
        var y2Data = data.filter(function(d) { return d.year === y2; });
        var labels = y1Data.map(function(d) { return d.m_group_desc; });
        var y2Vals = labels.map(function(l) {
            var r = y2Data.find(function(d) { return d.m_group_desc === l; });
            return r ? (r[metric] || 0) / 1e6 : 0;
        });

        if (prodChart) prodChart.destroy();
        prodChart = new Chart(document.getElementById('productChart'), {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    { label: String(y1), data: y1Data.map(function(d) { return (d[metric] || 0) / 1e6; }), backgroundColor: C.blue, borderRadius: 3 },
                    { label: String(y2), data: y2Vals, backgroundColor: C.orange, borderRadius: 3 }
                ]
            },
            options: {
                indexAxis: 'y', responsive: true, maintainAspectRatio: false,
                plugins: { legend: { position: 'top', labels: { usePointStyle: true } }, tooltip: { callbacks: { label: function(c) { return c.dataset.label + ': $' + c.parsed.x.toFixed(1) + 'M'; } } } },
                scales: { x: { title: { display: true, text: '$ Millions' }, ticks: { callback: function(v) { return '$' + v + 'M'; } } } }
            }
        });

        // Margin chart
        var marginData = y1Data.map(function(d) { return d.net_sales !== 0 ? d.gross_margin / d.net_sales * 100 : 0; });
        if (prodMarginChart) prodMarginChart.destroy();
        prodMarginChart = new Chart(document.getElementById('productMarginChart'), {
            type: 'bar',
            data: { labels: labels, datasets: [{ label: 'Gross Margin % ' + y1, data: marginData, backgroundColor: marginData.map(function(v) { return v >= 0 ? C.green : C.red; }), borderRadius: 3 }] },
            options: {
                indexAxis: 'y', responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { callbacks: { label: function(c) { return c.parsed.x.toFixed(1) + '%'; } } } },
                scales: { x: { title: { display: true, text: 'Gross Margin %' }, ticks: { callback: function(v) { return v + '%'; } } } }
            }
        });

        // Table
        var tb = document.getElementById('productTable');
        var th = '<thead><tr><th>Product Group</th><th>FY ' + y1 + ' Net Sales</th><th>FY ' + y2 + ' Net Sales</th><th>Change</th><th>Change %</th><th>FY ' + y1 + ' GM%</th><th>FY ' + y1 + ' Opx%</th></tr></thead><tbody>';
        y1Data.forEach(function(d) {
            var r2 = y2Data.find(function(x) { return x.m_group_desc === d.m_group_desc; });
            var v2 = r2 ? r2[metric] : 0;
            var chg = (d[metric] || 0) - v2;
            var chgPct = v2 !== 0 ? chg / Math.abs(v2) * 100 : null;
            th += '<tr>';
            th += '<td>' + d.m_group_desc + '</td>';
            th += '<td>' + fmtM(d.net_sales) + '</td>';
            th += '<td>' + fmtM(r2 ? r2.net_sales : 0) + '</td>';
            th += '<td class="' + (chg >= 0 ? 'pos' : 'neg') + '">' + fmtM(chg) + '</td>';
            th += '<td class="' + (chgPct >= 0 ? 'pos' : 'neg') + '">' + (chgPct !== null ? (chgPct >= 0 ? '+' : '') + chgPct.toFixed(1) + '%' : '--') + '</td>';
            th += '<td>' + (d.net_sales ? fmtPct(d.gross_margin / d.net_sales) : '--') + '</td>';
            th += '<td>' + (d.net_sales ? fmtPct(d.operating_profit / d.net_sales) : '--') + '</td>';
            th += '</tr>';
        });
        th += '</tbody>';
        tb.innerHTML = th;
    } catch (e) {
        console.error('Product load error:', e);
        showToast('Failed to load product data: ' + e.message, true);
    }
}

// ===== DRILL-DOWN ANALYSIS =====
var ddChart = null;

async function loadDrilldown() {
    var y1 = parseInt(document.getElementById('ddYear1').value);
    var y2 = parseInt(document.getElementById('ddYear2').value);
    var dim = document.getElementById('ddDim').value;
    var metric = document.getElementById('ddMetric').value;
    var btn = document.getElementById('ddBtn');

    var dimLabels = { region_desc: 'Region', country_name: 'Country', m_group_desc: 'Product Group', customer_name: 'Customer', class: 'Class' };
    var metricLabels = { net_sales: 'Net Sales', cost_of_goods_sold: 'COGS', gross_margin: 'Gross Margin', operating_expense: 'Operating Expense', operating_profit: 'Operating Profit', net_income: 'Net Income' };

    // Validate: year1 must differ from year2
    if (y1 === y2) {
        showToast('Year 1 and Year 2 must be different', true);
        return;
    }

    btn.disabled = true;
    btn.textContent = 'Loading...';

    try {
        var data = await safeFetch(API + '/api/drilldown?dimension=' + dim + '&year1=' + y1 + '&year2=' + y2 + '&metric=' + metric);

        if (!data || data.length === 0) {
            showToast('No data found for this combination', true);
            btn.disabled = false;
            btn.textContent = 'Drill Down';
            return;
        }

        // Waterfall chart
        var top = data.slice(0, 20);
        var labels = top.map(function(d) { return d.dimension || 'N/A'; });
        var changes = top.map(function(d) { return d.change / 1e6; });

        if (ddChart) ddChart.destroy();
        ddChart = new Chart(document.getElementById('drilldownChart'), {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Change ' + y1 + '→' + y2,
                    data: changes,
                    backgroundColor: changes.map(function(v) { return v >= 0 ? C.green : C.red; }),
                    borderRadius: 3
                }]
            },
            options: {
                indexAxis: 'y', responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: function(c) { var v = c.parsed.x; return (v >= 0 ? '+' : '') + '$' + v.toFixed(1) + 'M'; } } }
                },
                scales: {
                    x: { title: { display: true, text: 'Change in ' + metricLabels[metric] + ' ($M)' }, ticks: { callback: function(v) { return '$' + v + 'M'; } } },
                    y: { ticks: { font: { size: 11 } } }
                }
            }
        });

        // Table
        var tb = document.getElementById('drilldownTable');
        var th = '<thead><tr><th>' + dimLabels[dim] + '</th><th>FY ' + y1 + '</th><th>FY ' + y2 + '</th><th>Change ($)</th><th>Change %</th><th>Impact</th></tr></thead><tbody>';
        var maxChg = 0;
        data.forEach(function(d) { if (Math.abs(d.change) > maxChg) maxChg = Math.abs(d.change); });

        data.forEach(function(d) {
            var chg = d.change;
            var pct = d.pct_change;
            var barW = maxChg ? Math.abs(chg) / maxChg * 100 : 0;
            th += '<tr>';
            th += '<td>' + (d.dimension || 'N/A') + '</td>';
            th += '<td>' + fmtM(d.val_year1) + '</td>';
            th += '<td>' + fmtM(d.val_year2) + '</td>';
            th += '<td class="' + (chg >= 0 ? 'pos' : 'neg') + '" style="font-weight:600">' + (chg >= 0 ? '+' : '') + fmtM(chg) + '</td>';
            th += '<td class="' + (pct >= 0 ? 'pos' : 'neg') + '">' + (pct !== null ? (pct >= 0 ? '+' : '') + pct.toFixed(1) + '%' : '--') + '</td>';
            th += '<td><span class="var-bar ' + (chg >= 0 ? 'pos' : 'neg') + '" style="width:' + barW + '%"></span></td>';
            th += '</tr>';
        });
        th += '</tbody>';
        tb.innerHTML = th;

        showToast('Loaded ' + data.length + ' items for ' + dimLabels[dim] + ' ' + metricLabels[metric] + ' ' + y1 + '→' + y2, false);
    } catch (e) {
        console.error('Drilldown error:', e);
        showToast('Drill-down failed: ' + e.message, true);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Drill Down';
    }
}
