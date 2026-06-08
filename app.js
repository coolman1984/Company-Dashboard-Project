/**
 * PL Financial Analysis Dashboard v3.1
 * Smart colors, year picker, quick insights, CSV export
 */
(function() {
'use strict';

var API = '';
var C = { blue: '#4361ee', green: '#06d6a0', red: '#ef476f', orange: '#ffd166', purple: '#7209b7', teal: '#4cc9f0', gray: '#6c757d', slate: '#415a77' };
var yearColors = ['#4361ee', '#06d6a0', '#ffd166', '#7209b7', '#ef476f'];

var tabLoaded = { overview: false, regional: false, product: false, drilldown: false };
var regionalDataCache = null, mgroupDataCache = null, yearlyDataCache = null;
var focusYear = 2026;
var charts = {};

// "Good direction" per metric: increase=good (1) or decrease=good (-1)
var metricDirection = {
    net_sales: 1, gross_margin: 1, operating_profit: 1, net_income: 1,
    profit_before_tax: 1, gross_sales: 1,
    cogs: -1, opex: -1, corporate_tax: -1, operating_expense: -1,
    cost_of_goods_sold: -1, sales_expense: -1, material_cost: -1,
    returns: -1, sales_deduction: -1
};

function fmtM(n) {
    if (n == null) return '--';
    var a = Math.abs(n);
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

function isGood(key, chg) {
    var dir = metricDirection[key] || 1;
    return dir * chg > 0;
}

function colorClass(key, chg) {
    if (chg === 0 || chg == null) return '';
    return isGood(key, chg) ? 'pos' : 'neg';
}

function showToast(msg, isError) {
    var t = document.getElementById('toast');
    t.textContent = msg;
    t.className = 'toast' + (isError ? ' error' : '');
    setTimeout(function() { t.classList.add('show'); }, 10);
    setTimeout(function() { t.classList.remove('show'); }, 3000);
}

function safeFetch(url, timeoutMs) {
    timeoutMs = timeoutMs || 10000;
    var controller = new AbortController();
    var timer = setTimeout(function() { controller.abort(); }, timeoutMs);
    return fetch(url, { signal: controller.signal }).then(function(resp) {
        clearTimeout(timer);
        if (!resp.ok) {
            return resp.json().catch(function() { return {}; }).then(function(errData) {
                throw new Error(errData.error || 'HTTP ' + resp.status);
            });
        }
        return resp.json();
    }).catch(function(e) {
        clearTimeout(timer);
        if (e.name === 'AbortError') throw new Error('Request timed out');
        throw e;
    });
}

function setStatus(ok, msg) {
    var dot = document.getElementById('statusDot');
    dot.className = 'status-dot ' + (ok ? 'ok' : 'err');
    var label = document.getElementById('statusLabel');
    if (label) label.textContent = msg;
}

// ===== TABS =====
document.querySelectorAll('.tab').forEach(function(t) {
    t.addEventListener('click', function() {
        document.querySelectorAll('.tab').forEach(function(x) { x.classList.remove('active'); });
        document.querySelectorAll('.panel').forEach(function(x) { x.classList.remove('active'); });
        t.classList.add('active');
        var tabName = t.dataset.tab;
        document.getElementById('panel-' + tabName).classList.add('active');
        if (!tabLoaded[tabName]) {
            if (tabName === 'overview') loadOverview();
            else if (tabName === 'regional') loadRegional();
            else if (tabName === 'product') loadProductAnalysis();
            else if (tabName === 'drilldown') loadDrilldown();
            tabLoaded[tabName] = true;
        }
    });
});

// ===== OVERVIEW =====
function loadOverview() {
    showLoading('kpiGrid');
    showLoading('plTable');
    document.getElementById('insightsContent').innerHTML = '<div class="loading">Analyzing...</div>';

    safeFetch(API + '/api/yearly-pl').then(function(data) {
        if (!data || !data.length) throw new Error('No yearly data');
        yearlyDataCache = data;
        renderKPIs(data, focusYear);
        renderCharts(data);
        renderPLTable(data);
        renderInsights(data);
        setStatus(true, 'Data loaded');
    }).catch(function(e) {
        showToast('Failed: ' + e.message, true);
        setStatus(false, 'Load failed');
        document.getElementById('kpiGrid').innerHTML = '<div class="loading">Failed to load. Is the server running?</div>';
    });
}

function showLoading(id) {
    document.getElementById(id).innerHTML = '<div class="loading"><span class="loading-spinner"></span>Loading...</div>';
}

function yearIndex(data, year) {
    for (var i = 0; i < data.length; i++) { if (data[i].year === year) return i; }
    return data.length - 1;
}

function renderKPIs(data, fy) {
    var li = yearIndex(data, fy);
    var pi = Math.max(0, li - 1);
    var d = data;

    var ns0 = d[0].net_sales, nsLi = d[li].net_sales, nsPi = d[pi].net_sales;
    var gmLi = d[li].gross_margin, gmPi = d[pi].gross_margin;
    var opLi = d[li].operating_profit;
    var niLi = d[li].net_income;

    var salesChg = pctChg(nsPi, nsLi);
    var gmChg = pctChg(gmPi, gmLi);
    var cagr = ns0 > 0 ? (Math.pow(nsLi / ns0, 1 / li) - 1) * 100 : 0;

    function arrow(v) { return v > 0 ? '▲' : v < 0 ? '▼' : ''; }

    var kpis = [
        { label: 'Net Sales ' + fy, value: fmtM(nsLi), sub: (salesChg !== null ? arrow(salesChg) + ' ' + Math.abs(salesChg * 100).toFixed(1) + '% vs ' + d[pi].year : 'N/A'), pos: salesChg !== null && salesChg > 0, cls: '' },
        { label: 'Gross Margin ' + fy, value: fmtM(gmLi), sub: (gmChg !== null ? arrow(gmChg) + ' ' + Math.abs(gmChg * 100).toFixed(1) + '% vs ' + d[pi].year : 'N/A'), pos: gmChg !== null && gmChg > 0, cls: gmLi >= 0 ? 'success' : 'danger' },
        { label: 'Operating Profit ' + fy, value: fmtM(opLi), sub: opLi >= 0 ? 'Profitable' : 'Operating Loss', pos: opLi >= 0, cls: opLi >= 0 ? 'success' : 'danger' },
        { label: 'Net Income ' + fy, value: fmtM(niLi), sub: niLi >= 0 ? 'Net Profit' : 'Net Loss', pos: niLi >= 0, cls: niLi >= 0 ? 'success' : 'danger' },
        { label: 'Rev. CAGR (' + d[0].year + '-' + fy + ')', value: cagr.toFixed(1) + '%', sub: 'Compound annual growth', pos: cagr > 0, cls: 'info' },
        { label: 'Gross Margin % ' + fy, value: fmtPct(gmLi / nsLi), sub: 'vs ' + fmtPct(gmPi / nsPi) + ' in ' + d[pi].year, pos: gmLi / nsLi > gmPi / nsPi, cls: 'info' },
    ];

    document.getElementById('kpiGrid').innerHTML = kpis.map(function(k) {
        return '<div class="kpi-card ' + k.cls + '">' +
            '<div class="kpi-label">' + k.label + '</div>' +
            '<div class="kpi-value">' + k.value + '</div>' +
            '<div class="kpi-sub ' + (k.pos ? 'pos' : 'neg') + '">' + k.sub + '</div>' +
        '</div>';
    }).join('');
}

function renderCharts(data) {
    var sales = data.map(function(r) { return r.net_sales / 1e6; });
    var cogs = data.map(function(r) { return r.cogs / 1e6; });
    var gm = data.map(function(r) { return r.gross_margin / 1e6; });
    var ni = data.map(function(r) { return r.net_income / 1e6; });
    var years = data.map(function(r) { return r.year; });

    destroyChart('revenueCostChart');
    destroyChart('marginChart');
    destroyChart('netIncomeChart');
    destroyChart('costStructChart');

    charts.revenueCost = new Chart(document.getElementById('revenueCostChart'), {
        type: 'bar',
        data: { labels: years, datasets: [
            { label: 'Net Sales', data: sales, backgroundColor: C.blue, borderRadius: 6, barPercentage: 0.7 },
            { label: 'COGS', data: cogs, backgroundColor: C.red, borderRadius: 6, barPercentage: 0.7 },
            { label: 'Gross Margin', data: gm, backgroundColor: C.green, borderRadius: 6, barPercentage: 0.7 }
        ]},
        options: makeBarOptions('$ Millions')
    });

    charts.margin = new Chart(document.getElementById('marginChart'), {
        type: 'line',
        data: { labels: years, datasets: [
            { label: 'GM %', data: data.map(function(_,i){ return data[i].net_sales ? data[i].gross_margin/data[i].net_sales*100 : 0; }), borderColor: C.green, backgroundColor: hexToRgba(C.green,0.1), tension: 0.35, pointRadius: 5, pointHoverRadius: 7, borderWidth: 3, fill: true },
            { label: 'Op %', data: data.map(function(_,i){ return data[i].net_sales ? data[i].operating_profit/data[i].net_sales*100 : 0; }), borderColor: C.blue, backgroundColor: hexToRgba(C.blue,0.1), tension: 0.35, pointRadius: 5, pointHoverRadius: 7, borderWidth: 3, fill: true },
            { label: 'NI %', data: data.map(function(_,i){ return data[i].net_sales ? data[i].net_income/data[i].net_sales*100 : 0; }), borderColor: C.purple, backgroundColor: hexToRgba(C.purple,0.1), tension: 0.35, pointRadius: 5, pointHoverRadius: 7, borderWidth: 3, fill: true }
        ]},
        options: { responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'top', labels: { usePointStyle: true, padding: 16, font: { size: 12 } } }, tooltip: { callbacks: { label: function(c) { return c.dataset.label + ': ' + c.parsed.y.toFixed(1) + '%'; } } } },
            scales: { y: { grid: { color: '#e5e7eb' }, title: { display: true, text: 'Margin %' }, ticks: { callback: function(v) { return v + '%'; } } }, x: { grid: { display: false } } }
        }
    });

    charts.netIncome = new Chart(document.getElementById('netIncomeChart'), {
        type: 'bar',
        data: { labels: years, datasets: [{ label: 'Net Income', data: ni, backgroundColor: ni.map(function(v){ return v>=0 ? C.green : C.red; }), borderRadius: 8, barPercentage: 0.6 }] },
        options: { responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: { callbacks: { label: function(c){ return '$' + c.parsed.y.toFixed(1) + 'M'; } } } },
            scales: { y: { grid: { color: '#e5e7eb' }, title: { display: true, text: '$ Millions' }, ticks: { callback: function(v){ return '$' + v + 'M'; } } }, x: { grid: { display: false } } }
        }
    });

    charts.costStruct = new Chart(document.getElementById('costStructChart'), {
        type: 'bar',
        data: { labels: years, datasets: [
            { label: 'COGS %', data: data.map(function(_,i){ return data[i].net_sales ? data[i].cogs/data[i].net_sales*100 : 0; }), backgroundColor: C.red, borderRadius: 4 },
            { label: 'OpEx %', data: data.map(function(_,i){ return data[i].net_sales ? data[i].opex/data[i].net_sales*100 : 0; }), backgroundColor: C.orange, borderRadius: 4 },
            { label: 'Tax %', data: data.map(function(_,i){ return data[i].net_sales ? data[i].corporate_tax/data[i].net_sales*100 : 0; }), backgroundColor: C.purple, borderRadius: 4 }
        ]},
        options: { responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'top', labels: { usePointStyle: true, padding: 16, font: { size: 12 } } }, tooltip: { callbacks: { label: function(c){ return c.dataset.label + ': ' + c.parsed.y.toFixed(1) + '%'; } } } },
            scales: { y: { grid: { color: '#e5e7eb' }, stacked: true, title: { display: true, text: '% of Net Sales' }, ticks: { callback: function(v){ return v + '%'; } } }, x: { stacked: true, grid: { display: false } } }
        }
    });
}

function renderPLTable(data) {
    var tb = document.getElementById('plTable');
    var h = '<thead><tr><th>Line Item</th>';
    data.forEach(function(r) { h += '<th>FY ' + r.year + '</th>'; });
    for (var i = 1; i < data.length; i++) h += '<th>' + data[i-1].year + '→' + data[i].year + '</th>';
    h += '</tr></thead><tbody>';

    var keys = [
        { label: 'Net Sales', key: 'net_sales', rowClass: '' },
        { label: 'Cost of Goods Sold', key: 'cogs', rowClass: '' },
        { label: 'Gross Margin', key: 'gross_margin', rowClass: 'subtotal' },
        { label: 'Operating Expense', key: 'opex', rowClass: '' },
        { label: 'Operating Profit', key: 'operating_profit', rowClass: 'subtotal' },
        { label: 'Profit Before Tax', key: 'profit_before_tax', rowClass: '' },
        { label: 'Corporate Tax', key: 'corporate_tax', rowClass: '' },
        { label: 'Net Income', key: 'net_income', rowClass: 'total' },
    ];

    keys.forEach(function(item) {
        h += '<tr class="' + item.rowClass + '"><td>' + item.label + '</td>';
        var vals = data.map(function(r) { return r[item.key]; });
        vals.forEach(function(v) {
            h += '<td class="' + (v < 0 ? 'neg' : '') + '">' + fmtFull(v) + '</td>';
        });
        for (var i = 1; i < vals.length; i++) {
            var c = pctChg(vals[i-1], vals[i]), cls = colorClass(item.key, vals[i-1] && vals[i] ? vals[i] - vals[i-1] : 0);
            if (c !== null) {
                var p = c * 100;
                h += '<td class="' + cls + '" style="font-weight:600;font-size:11px">' + (p >= 0 ? '▲' : '▼') + ' ' + Math.abs(p).toFixed(1) + '%</td>';
            } else {
                h += '<td>--</td>';
            }
        }
        h += '</tr>';
    });
    h += '</tbody>';
    tb.innerHTML = h;
}

// ===== QUICK INSIGHTS =====
function renderInsights(data) {
    var d = data;
    var last = d[d.length-1], prev = d[d.length-2];
    var el = document.getElementById('insightsContent');
    var lines = [];

    var nsChg = pctChg(prev.net_sales, last.net_sales);
    var cogsChg = pctChg(prev.cogs, last.cogs);
    var gmChg = pctChg(prev.gross_margin, last.gross_margin);
    var opexChg = pctChg(prev.opex, last.opex);
    var niChg = pctChg(prev.net_income, last.net_income);

    if (nsChg !== null) {
        lines.push('<div class="insight-item ' + (nsChg > 0 ? 'good' : 'bad') + '"><span class="insight-dot"></span><strong>Net Sales</strong> ' + (nsChg > 0 ? 'grew' : 'declined') + ' <b>' + Math.abs(nsChg * 100).toFixed(1) + '%</b> in ' + last.year + ' vs ' + prev.year + '</div>');
    }
    if (cogsChg !== null && nsChg !== null) {
        var worse = cogsChg > nsChg;
        lines.push('<div class="insight-item ' + (worse ? 'bad' : 'good') + '"><span class="insight-dot"></span><strong>COGS</strong> changed <b>' + (cogsChg > 0 ? '+' : '') + (cogsChg * 100).toFixed(1) + '%</b> — ' + (worse ? 'growing faster than revenue, pressuring margins' : 'well controlled vs revenue growth') + '</div>');
    }
    if (gmChg !== null) {
        lines.push('<div class="insight-item ' + (gmChg > 0 ? 'good' : 'bad') + '"><span class="insight-dot"></span><strong>Gross Margin</strong> ' + (gmChg > 0 ? 'improved' : 'dropped') + ' <b>' + Math.abs(gmChg * 100).toFixed(1) + '%</b> — GM% is <b>' + (last.net_sales ? (last.gross_margin / last.net_sales * 100).toFixed(1) : 'N/A') + '%</b> of sales</div>');
    }
    if (opexChg !== null) {
        lines.push('<div class="insight-item ' + (opexChg < 0 ? 'good' : 'bad') + '"><span class="insight-dot"></span><strong>OpEx</strong> ' + (opexChg > 0 ? 'rose' : 'fell') + ' <b>' + Math.abs(opexChg * 100).toFixed(1) + '%</b> — operating leverage is ' + (opexChg < nsChg ? 'improving' : 'worsening') + '</div>');
    }
    if (niChg !== null) {
        var niPct = last.net_sales ? last.net_income / last.net_sales * 100 : 0;
        lines.push('<div class="insight-item ' + (niChg > 0 ? 'good' : 'bad') + '"><span class="insight-dot"></span><strong>Net Income</strong> ' + (niChg > 0 ? 'grew' : 'declined') + ' <b>' + Math.abs(niChg * 100).toFixed(1) + '%</b> — net margin is <b>' + niPct.toFixed(1) + '%</b></div>');
    }
    lines.push('<div class="insight-item neutral"><span class="insight-dot"></span>CAGR (' + d[0].year + '-' + last.year + '): <b>' + (d[0].net_sales > 0 ? ((Math.pow(last.net_sales / d[0].net_sales, 1/(d.length-1)) - 1) * 100).toFixed(1) : 'N/A') + '%</b></div>');

    el.innerHTML = lines.join('');
}

// ===== REGIONAL =====
function loadRegional() {
    var metric = document.getElementById('regMetric').value;
    var promise = regionalDataCache ? Promise.resolve(regionalDataCache) : safeFetch(API + '/api/regional-pl').then(function(d) { regionalDataCache = d; return d; });

    promise.then(function(data) {
        var regions = [], seen = {};
        data.forEach(function(r) { if (r.region_desc && !seen[r.region_desc]) { seen[r.region_desc] = true; regions.push(r.region_desc); } });
        var years = [2022,2023,2024,2025,2026];

        var datasets = years.map(function(y, i) {
            return { label: String(y), data: regions.map(function(r) {
                var row = data.find(function(d) { return d.year === y && d.region_desc === r; });
                return row ? (row[metric] || 0) / 1e6 : 0;
            }), backgroundColor: yearColors[i], borderRadius: 6, barPercentage: 0.8 };
        });

        destroyChart('regionalChart');
        charts.regional = new Chart(document.getElementById('regionalChart'), {
            type: 'bar', data: { labels: regions, datasets: datasets },
            options: { responsive: true, maintainAspectRatio: false,
                plugins: { legend: { position: 'top', labels: { usePointStyle: true, padding: 12 } }, tooltip: { callbacks: { label: function(c) { return c.dataset.label + ': $' + c.parsed.y.toFixed(1) + 'M'; } } } },
                scales: { y: { grid: { color: '#e5e7eb' }, title: { display: true, text: '$ Millions' }, ticks: { callback: function(v){ return '$' + v + 'M'; } } }, x: { grid: { display: false } } }
            }
        });

        var tb = document.getElementById('regionalTable');
        var th = '<thead><tr><th>Region</th>';
        years.forEach(function(y) { th += '<th>FY ' + y + '</th>'; });
        th += '</tr></thead><tbody>';
        regions.forEach(function(r) {
            th += '<tr><td><strong>' + r + '</strong></td>';
            years.forEach(function(y) {
                var row = data.find(function(d) { return d.year === y && d.region_desc === r; });
                var v = row ? (row[metric] || 0) : 0;
                th += '<td class="' + (v < 0 ? 'neg' : '') + '">' + fmtM(v) + '</td>';
            });
            th += '</tr>';
        });
        th += '</tbody>';
        tb.innerHTML = th;
    }).catch(function(e) { showToast('Regional load failed: ' + e.message, true); });
}

document.getElementById('regMetric').addEventListener('change', function() { if (regionalDataCache) loadRegional(); });

// ===== PRODUCT =====
function loadProductAnalysis() {
    var y1 = parseInt(document.getElementById('prodYear').value);
    var y2 = parseInt(document.getElementById('prodYear2').value);
    var metric = document.getElementById('prodMetric').value;
    var promise = mgroupDataCache ? Promise.resolve(mgroupDataCache) : safeFetch(API + '/api/mgroup-pl').then(function(d) { mgroupDataCache = d; return d; });

    promise.then(function(data) {
        var y1Data = data.filter(function(d) { return d.year === y1; }).sort(function(a,b){ return (b[metric]||0)-(a[metric]||0); }).slice(0,15);
        var y2Data = data.filter(function(d) { return d.year === y2; });
        var labels = y1Data.map(function(d){ return d.m_group_desc; });
        var y2Vals = labels.map(function(l){ var r=y2Data.find(function(d){ return d.m_group_desc===l; }); return r ? (r[metric]||0)/1e6 : 0; });

        destroyChart('productChart'); destroyChart('productMarginChart');

        charts.product = new Chart(document.getElementById('productChart'), {
            type: 'bar', data: { labels: labels, datasets: [
                { label: String(y1), data: y1Data.map(function(d){ return (d[metric]||0)/1e6; }), backgroundColor: C.blue, borderRadius: 3 },
                { label: String(y2), data: y2Vals, backgroundColor: C.orange, borderRadius: 3 }
            ]},
            options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false,
                plugins: { legend: { position: 'top', labels: { usePointStyle: true } }, tooltip: { callbacks: { label: function(c){ return c.dataset.label + ': $' + c.parsed.x.toFixed(1) + 'M'; } } } },
                scales: { x: { grid: { color: '#e5e7eb' }, title: { display: true, text: '$ Millions' }, ticks: { callback: function(v){ return '$' + v + 'M'; } } }, y: { grid: { display: false } } }
            }
        });

        var marginData = y1Data.map(function(d){ return d.net_sales !== 0 ? d.gross_margin/d.net_sales*100 : 0; });
        charts.productMargin = new Chart(document.getElementById('productMarginChart'), {
            type: 'bar', data: { labels: labels, datasets: [{ label: 'GM% '+y1, data: marginData, backgroundColor: marginData.map(function(v){ return v>=0?C.green:C.red; }), borderRadius: 3 }] },
            options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { callbacks: { label: function(c){ return c.parsed.x.toFixed(1)+'%'; } } } },
                scales: { x: { grid: { color: '#e5e7eb' }, title: { display: true, text: 'Gross Margin %' }, ticks: { callback: function(v){ return v+'%'; } } }, y: { grid: { display: false } } }
            }
        });

        var tb = document.getElementById('productTable');
        var th = '<thead><tr><th>Product Group</th><th>FY '+y1+'</th><th>FY '+y2+'</th><th>Change</th><th>%</th><th>GM% '+y1+'</th></tr></thead><tbody>';
        y1Data.forEach(function(d){
            var r2 = y2Data.find(function(x){ return x.m_group_desc===d.m_group_desc; });
            var v2 = r2 ? r2[metric] : 0, chg = (d[metric]||0)-v2, chgPct = v2!==0 ? chg/Math.abs(v2)*100 : null;
            var cls = colorClass(metric, chg);
            th += '<tr><td>'+d.m_group_desc+'</td><td>'+fmtM(d[metric])+'</td><td>'+fmtM(v2)+'</td>';
            th += '<td class="'+cls+'">'+fmtM(chg)+'</td>';
            th += '<td class="'+(chgPct!==null?(chgPct>=0?'pos':'neg'):'')+'">'+(chgPct!==null?(chgPct>=0?'+':'')+chgPct.toFixed(1)+'%':'--')+'</td>';
            th += '<td>'+(d.net_sales?fmtPct(d.gross_margin/d.net_sales):'--')+'</td></tr>';
        });
        th += '</tbody>'; tb.innerHTML = th;
    }).catch(function(e){ showToast('Product load failed: '+e.message, true); });
}

// ===== DRILLDOWN =====
function loadDrilldown() {
    var y1 = parseInt(document.getElementById('ddYear1').value);
    var y2 = parseInt(document.getElementById('ddYear2').value);
    var dim = document.getElementById('ddDim').value;
    var metric = document.getElementById('ddMetric').value;
    var btn = document.getElementById('ddBtn');
    var dimLabels = { region_desc:'Region', country_name:'Country', m_group_desc:'Product Group', customer_name:'Customer', class:'Class' };
    var metricLabels = { net_sales:'Net Sales', cost_of_goods_sold:'COGS', gross_margin:'Gross Margin', operating_expense:'OpEx', operating_profit:'Operating Profit', net_income:'Net Income' };

    if (y1 === y2) { showToast('Years must be different', true); return; }
    btn.disabled = true; btn.textContent = 'Loading...';

    safeFetch(API + '/api/drilldown?dimension='+dim+'&year1='+y1+'&year2='+y2+'&metric='+metric).then(function(data){
        if (!data || !data.length) { showToast('No data found', true); return; }
        var top = data.slice(0,20);
        destroyChart('drilldownChart');
        charts.drilldown = new Chart(document.getElementById('drilldownChart'), {
            type: 'bar', data: { labels: top.map(function(d){ return d.dimension||'N/A'; }), datasets: [{ label: 'Change '+y1+'→'+y2, data: top.map(function(d){ return d.change/1e6; }), backgroundColor: top.map(function(d){ return d.change>=0?C.green:C.red; }), borderRadius: 4 }] },
            options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { callbacks: { label: function(c){ return (c.parsed.x>=0?'+':'')+'$'+c.parsed.x.toFixed(1)+'M'; } } } },
                scales: { x: { grid: { color: '#e5e7eb' }, title: { display: true, text: 'Change ($M)' }, ticks: { callback: function(v){ return '$'+v+'M'; } } }, y: { grid: { display: false } } }
            }
        });

        var tb = document.getElementById('drilldownTable'), maxChg = 0;
        data.forEach(function(d){ if(Math.abs(d.change)>maxChg) maxChg=Math.abs(d.change); });
        var th = '<thead><tr><th>'+dimLabels[dim]+'</th><th>FY '+y1+'</th><th>FY '+y2+'</th><th>Change</th><th>%</th><th>Impact</th></tr></thead><tbody>';
        data.forEach(function(d){
            var chg=d.change, pct=d.pct_change, barW=maxChg?Math.abs(chg)/maxChg*100:0, cls=colorClass(metric, chg);
            th += '<tr><td>'+(d.dimension||'N/A')+'</td><td>'+fmtM(d.val_year1)+'</td><td>'+fmtM(d.val_year2)+'</td>';
            th += '<td class="'+cls+'" style="font-weight:600">'+(chg>=0?'+':'')+fmtM(chg)+'</td>';
            th += '<td class="'+(pct>=0?'pos':'neg')+'">'+(pct!==null?(pct>=0?'+':'')+pct.toFixed(1)+'%':'--')+'</td>';
            th += '<td><div class="var-bar '+(chg>=0?'pos':'neg')+'" style="width:'+barW+'%"></div></td></tr>';
        });
        th += '</tbody>'; tb.innerHTML = th;
        showToast(data.length+' items loaded');
    }).catch(function(e){ showToast('Failed: '+e.message, true); }).then(function(){ btn.disabled=false; btn.textContent='Drill Down'; });
}

// ===== CSV EXPORT =====
function exportCSV(tableId, filename) {
    var table = document.getElementById(tableId);
    if (!table) return;
    var rows = table.querySelectorAll('tr');
    var csv = [];
    rows.forEach(function(row) {
        var cols = row.querySelectorAll('th, td');
        var line = [];
        cols.forEach(function(col) {
            var text = col.textContent.replace(/"/g, '""').replace(/\s+/g, ' ').trim();
            line.push('"' + text + '"');
        });
        csv.push(line.join(','));
    });
    var blob = new Blob([csv.join('\n')], { type: 'text/csv;charset=utf-8;' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = (filename || 'export') + '.csv';
    document.body.appendChild(a); a.click();
    document.body.removeChild(a); URL.revokeObjectURL(url);
    showToast('Exported ' + filename + '.csv');
}

// ===== HELPERS =====
function destroyChart(id) {
    var instance = Chart.getChart(document.getElementById(id));
    if (instance) instance.destroy();
}

function makeBarOptions(yLabel) {
    return { responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'top', labels: { usePointStyle: true, padding: 16, font: { size: 12 } } }, tooltip: { callbacks: { label: function(c){ return c.dataset.label + ': $' + c.parsed.y.toFixed(1) + 'M'; } } } },
        scales: { y: { beginAtZero: true, grid: { color: '#e5e7eb' }, title: { display: true, text: yLabel }, ticks: { callback: function(v){ return '$' + v + 'M'; } } }, x: { grid: { display: false } } }
    };
}

function hexToRgba(hex, alpha) {
    var r=parseInt(hex.slice(1,3),16), g=parseInt(hex.slice(3,5),16), b=parseInt(hex.slice(5,7),16);
    return 'rgba('+r+','+g+','+b+','+alpha+')';
}

// Expose for HTML onclick
window.loadProductAnalysis = loadProductAnalysis;
window.loadDrilldown = loadDrilldown;
window.exportCSV = exportCSV;

// ===== EVENT BINDINGS =====
document.getElementById('focusYear').addEventListener('change', function() {
    focusYear = parseInt(this.value);
    if (yearlyDataCache) {
        renderKPIs(yearlyDataCache, focusYear);
        renderInsights(yearlyDataCache);
    }
});

document.getElementById('productBtn').addEventListener('click', loadProductAnalysis);
document.getElementById('ddBtn').addEventListener('click', loadDrilldown);

// ===== STARTUP =====
showLoading('kpiGrid');
showLoading('plTable');
document.getElementById('insightsContent').innerHTML = '<div class="loading">Analyzing...</div>';
loadOverview();
tabLoaded.overview = true;

})();
