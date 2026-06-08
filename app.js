(function () {
'use strict';

var API = '';
var colors = {
    blue: '#3867f4',
    cyan: '#12b8d4',
    green: '#10a875',
    red: '#e34c67',
    amber: '#e89a24',
    violet: '#7857d9',
    slate: '#66758a'
};
var yearColors = ['#3867f4', '#12b8d4', '#e89a24', '#7857d9', '#e34c67'];
var charts = {};
var requestCache = new Map();
var filters = { years: [], versions: [], regions: [], countries: [], classes: [] };
var freshness = null;
var summary = null;
var activeTab = 'overview';
var standardFilterState = { year: '', version: 'Actual' };
var tabLoaded = { overview: false, regional: false, product: false, drilldown: false, scenario: false };
var yearlyData = [];
var executiveData = null;
var productData = [];
var scenarioData = [];

var pageMeta = {
    overview: ['Executive Overview', 'Live profit and loss performance from the SQLite detail ledger'],
    regional: ['Regional Performance', 'Commercial geography, profitability and market contribution'],
    product: ['Product Profitability', 'Product group economics and margin quality'],
    drilldown: ['Variance Contributors', 'The dimensions driving financial movement between periods'],
    scenario: ['2026 Operating Outlook', 'Actual P01-P05 plus T06 P06 plus T07 P07-P12']
};

var metricLabels = {
    net_sales: 'Net Sales',
    cost_of_goods_sold: 'COGS',
    cogs: 'COGS',
    gross_margin: 'Gross Margin',
    operating_expense: 'Operating Expense',
    opex: 'Operating Expense',
    operating_profit: 'Operating Profit',
    net_income: 'Net Income'
};

var metricDirection = {
    net_sales: 1,
    gross_margin: 1,
    operating_profit: 1,
    net_income: 1,
    corporate_tax: -1,
    cogs: -1,
    cost_of_goods_sold: -1,
    opex: -1,
    operating_expense: -1
};

function el(id) {
    return document.getElementById(id);
}

function escapeHtml(value) {
    return String(value == null ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function formatCompact(value) {
    if (value == null || !Number.isFinite(Number(value))) return '--';
    var number = Number(value);
    var absolute = Math.abs(number);
    if (absolute >= 1e9) return (number / 1e9).toFixed(2) + 'B';
    if (absolute >= 1e6) return (number / 1e6).toFixed(2) + 'M';
    if (absolute >= 1e3) return (number / 1e3).toFixed(1) + 'K';
    return number.toFixed(2);
}

function formatFull(value) {
    if (value == null || !Number.isFinite(Number(value))) return '--';
    return Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatPercent(value) {
    if (value == null || !Number.isFinite(Number(value))) return '--';
    return (Number(value) * 100).toFixed(1) + '%';
}

function percentChange(previous, current) {
    if (!previous || previous === 0) return null;
    return (current - previous) / Math.abs(previous);
}

function isGood(metric, change) {
    return (metricDirection[metric] || 1) * change > 0;
}

function valueClass(metric, change) {
    if (change == null || change === 0) return '';
    return isGood(metric, change) ? 'pos' : 'neg';
}

function showToast(message, isError) {
    var toast = el('toast');
    toast.textContent = message;
    toast.className = 'toast' + (isError ? ' error' : '');
    requestAnimationFrame(function () { toast.classList.add('show'); });
    window.setTimeout(function () { toast.classList.remove('show'); }, 2800);
}

function setStatus(ok, message) {
    el('statusDot').className = 'status-dot' + (ok ? '' : ' err');
    el('statusLabel').textContent = message;
}

function setLoading(id, label) {
    el(id).innerHTML = '<div class="loading"><span><span class="loading-spinner"></span>' +
        escapeHtml(label || 'Loading live data...') + '</span></div>';
}

function fetchJson(path, options) {
    options = options || {};
    var cacheKey = path;
    if (!options.force && requestCache.has(cacheKey)) {
        return Promise.resolve(requestCache.get(cacheKey));
    }
    var controller = new AbortController();
    var timer = window.setTimeout(function () { controller.abort(); }, options.timeout || 30000);
    return fetch(path, { signal: controller.signal })
        .then(function (response) {
            window.clearTimeout(timer);
            return response.json().catch(function () { return {}; }).then(function (body) {
                if (!response.ok) throw new Error(body.error || 'HTTP ' + response.status);
                requestCache.set(cacheKey, body);
                return body;
            });
        })
        .catch(function (error) {
            window.clearTimeout(timer);
            if (error.name === 'AbortError') throw new Error('Database query timed out');
            throw error;
        });
}

function queryString(extra, options) {
    extra = extra || {};
    options = options || {};
    var params = new URLSearchParams();
    var year = el('globalYear').value;
    var version = el('globalVersion').value;
    var region = el('globalRegion').value;
    var country = el('globalCountry').value;

    if (!options.ignoreYear && year) params.set('year', year);
    if (!options.ignoreVersion && version) params.set('version', version);
    if (region) params.set('region', region);
    if (country) params.set('country', country);
    Object.keys(extra).forEach(function (key) {
        var value = extra[key];
        if (value !== undefined && value !== null && value !== '') params.set(key, value);
    });
    var value = params.toString();
    return value ? '?' + value : '';
}

function getActualYearMeta(year) {
    return freshness && freshness.years && freshness.years[year]
        ? freshness.years[year].Actual
        : null;
}

function yearLabel(year) {
    var version = el('globalVersion').value || 'Actual';
    var meta = freshness && freshness.years && freshness.years[year]
        ? freshness.years[year][version]
        : null;
    if (meta && !meta.isFullYear) {
        return year + ' P' + String(meta.maxPeriodNumber || meta.periodCount).padStart(2, '0');
    }
    return String(year);
}

function fillSelect(select, values, options) {
    options = options || {};
    var current = options.selected !== undefined ? String(options.selected) : select.value;
    var html = options.emptyLabel !== undefined
        ? '<option value="">' + escapeHtml(options.emptyLabel) + '</option>'
        : '';
    values.forEach(function (value) {
        html += '<option value="' + escapeHtml(value) + '">' + escapeHtml(options.labeler ? options.labeler(value) : value) + '</option>';
    });
    select.innerHTML = html;
    if ([].some.call(select.options, function (option) { return option.value === current; })) {
        select.value = current;
    } else if (options.defaultValue !== undefined) {
        select.value = String(options.defaultValue);
    }
}

function populateControls() {
    fillSelect(el('globalYear'), filters.years, { emptyLabel: 'All years' });
    fillSelect(el('globalVersion'), filters.versions, { defaultValue: 'Actual' });
    fillSelect(el('globalRegion'), filters.regions, { emptyLabel: 'All regions' });
    fillSelect(el('globalCountry'), filters.countries, { emptyLabel: 'All countries' });

    var yearLabeler = function (year) {
        var meta = getActualYearMeta(year);
        return meta && !meta.isFullYear ? year + ' YTD P' + String(meta.maxPeriodNumber).padStart(2, '0') : year;
    };
    fillSelect(el('prodYear'), filters.years, { defaultValue: filters.years[filters.years.length - 1], labeler: yearLabeler });
    fillSelect(el('prodYear2'), filters.years, { defaultValue: filters.years[Math.max(0, filters.years.length - 2)], labeler: yearLabeler });
    fillSelect(el('ddYear1'), filters.years, { defaultValue: 2024, labeler: yearLabeler });
    fillSelect(el('ddYear2'), filters.years, { defaultValue: 2025, labeler: yearLabeler });
}

function renderSummaryMeta() {
    if (!summary) return;
    el('recordCount').textContent = Number(summary.totalRows).toLocaleString('en-US');
    el('databaseSize').textContent = (summary.databaseSizeBytes / 1024 / 1024).toFixed(0) + ' MB SQLite';
}

function renderFreshness() {
    var note = el('dataFreshnessNote');
    var actual2026 = getActualYearMeta(2026);
    if (actual2026 && !actual2026.isFullYear) {
        note.innerHTML =
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="9"/><path d="M12 10v6m0-9h.01"/></svg>' +
            '<span><strong>Data is fresh.</strong> Source: live SQLite (' +
            (summary ? Number(summary.totalRows).toLocaleString('en-US') : '--') +
            ' records) &nbsp;|&nbsp; Actual: P01-P' +
            String(actual2026.maxPeriodNumber).padStart(2, '0') +
            ' &nbsp;|&nbsp; 2026 outlook: Actual P01-P05 + T06 P06 + T07 P07-P12.</span>';
    } else {
        note.textContent = freshness ? freshness.note : 'Database coverage is unavailable.';
    }
}

function destroyChart(key) {
    if (charts[key]) {
        charts[key].destroy();
        delete charts[key];
    }
}

function baseChartOptions(axisLabel) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
            legend: {
                position: 'top',
                align: 'end',
                labels: { usePointStyle: true, pointStyle: 'circle', boxWidth: 7, boxHeight: 7, padding: 14, font: { size: 9, weight: 600 } }
            },
            tooltip: {
                padding: 10,
                titleFont: { size: 10 },
                bodyFont: { size: 10 },
                callbacks: { label: function (context) { return context.dataset.label + ': $' + Number(context.parsed.y).toFixed(1) + 'M'; } }
            }
        },
        scales: {
            x: { grid: { display: false }, ticks: { color: '#66758a', font: { size: 9 } } },
            y: {
                grid: { color: '#edf1f6' },
                border: { display: false },
                title: { display: !!axisLabel, text: axisLabel, color: '#96a2b3', font: { size: 9 } },
                ticks: { color: '#66758a', font: { size: 9 }, callback: function (value) { return '$' + value + 'M'; } }
            }
        }
    };
}

function ratio(numerator, denominator) {
    return denominator ? Number(numerator || 0) / Math.abs(Number(denominator)) : null;
}

function signedPercent(value) {
    if (value == null || !Number.isFinite(Number(value))) return '--';
    return (value >= 0 ? '+' : '') + (Number(value) * 100).toFixed(1) + '%';
}

function renderExecutiveKPIs(data) {
    var outlook = data.outlook;
    var prior = data.priorYear;
    var risk = data.productRisk;
    var actualShare = ratio(data.actualYtd.net_sales, outlook.net_sales);
    var revenueGrowth = percentChange(prior.net_sales, outlook.net_sales);
    var grossGrowth = percentChange(prior.gross_margin, outlook.gross_margin);
    var opVariance = outlook.operating_profit - prior.operating_profit;
    var netVariance = outlook.net_income - prior.net_income;
    var lossRevenueShare = ratio(risk.loss_making_revenue, risk.total_revenue);
    var cards = [
        {
            label: 'Revenue outlook',
            value: formatCompact(outlook.net_sales),
            sub: signedPercent(revenueGrowth) + ' vs FY2025 | ' + formatPercent(actualShare) + ' completed',
            tone: 'blue',
            icon: 'trending_up',
            metric: 'net_sales',
            change: revenueGrowth
        },
        {
            label: 'Gross profit',
            value: formatCompact(outlook.gross_margin),
            sub: signedPercent(grossGrowth) + ' vs FY2025 | Margin ' + formatPercent(ratio(outlook.gross_margin, outlook.net_sales)),
            tone: 'cyan',
            icon: 'paid',
            metric: 'gross_margin',
            change: grossGrowth
        },
        {
            label: 'Operating profit',
            value: formatCompact(outlook.operating_profit),
            sub: formatCompact(opVariance) + ' vs FY2025 | Margin ' + formatPercent(ratio(outlook.operating_profit, outlook.net_sales)),
            tone: 'violet',
            icon: 'monitoring',
            metric: 'operating_profit',
            change: opVariance
        },
        {
            label: 'Net profit',
            value: formatCompact(outlook.net_income),
            sub: formatCompact(netVariance) + ' vs FY2025 | Margin ' + formatPercent(ratio(outlook.net_income, outlook.net_sales)),
            tone: 'green',
            icon: 'account_balance_wallet',
            metric: 'net_income',
            change: netVariance
        },
        {
            label: 'Revenue at risk',
            value: formatPercent(lossRevenueShare),
            sub: Number(risk.loss_making_products || 0) + ' product groups forecast below operating break-even',
            tone: 'amber',
            icon: 'warning',
            metric: 'operating_profit',
            change: -Number(risk.loss_making_revenue || 0)
        }
    ];

    el('executiveKpiGrid').innerHTML = cards.map(function (card) {
        return '<article class="kpi-card">' +
            '<div class="kpi-top"><span class="kpi-icon ' + card.tone + '"><span class="material-symbols-rounded">' +
            escapeHtml(card.icon) + '</span></span><div><div class="kpi-label">' + escapeHtml(card.label) +
            '</div><div class="kpi-value">' + escapeHtml(card.value) + '</div></div></div>' +
            '<div class="kpi-sub ' + valueClass(card.metric, card.change) + '">' + escapeHtml(card.sub) + '</div>' +
            '</article>';
    }).join('');
}

function executiveLineDataset(label, values, color, dashed) {
    return {
        label: label,
        data: values,
        borderColor: color,
        backgroundColor: color,
        borderDash: dashed ? [6, 5] : [],
        pointBackgroundColor: '#fff',
        pointBorderColor: color,
        pointBorderWidth: 2,
        pointRadius: 3,
        pointHoverRadius: 5,
        borderWidth: 2.5,
        tension: 0.28,
        spanGaps: false
    };
}

function renderExecutiveCharts(data) {
    var monthly = data.monthly.slice().sort(function (a, b) { return a.period_number - b.period_number; });
    var labels = monthly.map(function (row) { return row.period_label; });
    var cumulative = 0;
    var cumulativeValues = monthly.map(function (row) {
        cumulative += Number(row.net_sales || 0);
        return cumulative / 1e6;
    });
    var actualRevenue = cumulativeValues.map(function (value, index) { return index <= 4 ? value : null; });
    var outlookRevenue = cumulativeValues.map(function (value, index) { return index >= 4 ? value : null; });
    var actualMargin = monthly.map(function (row, index) {
        return index <= 4 && row.net_sales ? Number(row.gross_margin) / Number(row.net_sales) * 100 : null;
    });
    var outlookMargin = monthly.map(function (row, index) {
        if (index === 4 && row.net_sales) return Number(row.gross_margin) / Number(row.net_sales) * 100;
        return index >= 5 && row.net_sales ? Number(row.gross_margin) / Number(row.net_sales) * 100 : null;
    });

    destroyChart('revenueOutlook');
    charts.revenueOutlook = new Chart(el('revenueOutlookChart'), {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                executiveLineDataset('Actual', actualRevenue, colors.blue, false),
                executiveLineDataset('Outlook', outlookRevenue, colors.cyan, true)
            ]
        },
        options: baseChartOptions('$ millions')
    });

    var marginOptions = baseChartOptions('gross margin %');
    marginOptions.plugins.tooltip.callbacks.label = function (context) {
        return context.dataset.label + ': ' + Number(context.parsed.y).toFixed(1) + '%';
    };
    marginOptions.scales.y.ticks.callback = function (value) { return value + '%'; };
    marginOptions.scales.y.suggestedMin = -5;
    marginOptions.scales.y.suggestedMax = 30;
    destroyChart('grossMarginOutlook');
    charts.grossMarginOutlook = new Chart(el('grossMarginOutlookChart'), {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                executiveLineDataset('Actual', actualMargin, colors.violet, false),
                executiveLineDataset('Outlook', outlookMargin, colors.violet, true)
            ]
        },
        options: marginOptions
    });
}

function renderExecutivePL(data) {
    var actual = data.actualYtd;
    var outlook = data.outlook;
    var prior = data.priorYear;
    var definitions = [
        ['Revenue', 'net_sales', ''],
        ['Cost of Sales', 'cogs', ''],
        ['Gross Profit', 'gross_margin', 'subtotal'],
        ['Operating Expenses', 'opex', ''],
        ['Operating Profit', 'operating_profit', 'subtotal'],
        ['Profit Before Tax', 'profit_before_tax', ''],
        ['Corporate Tax', 'corporate_tax', ''],
        ['Net Profit', 'net_income', 'total']
    ];
    var html = '<thead><tr><th rowspan="2">Account</th>' +
        '<th colspan="2">Actual 2026 P01-P05</th><th colspan="2">2026 Outlook P01-P12</th>' +
        '<th colspan="2">2025 Full Year</th><th colspan="2">Variance vs 2025</th></tr>' +
        '<tr><th>Amount</th><th>% Revenue</th><th>Amount</th><th>% Revenue</th>' +
        '<th>Amount</th><th>% Revenue</th><th>Amount</th><th>%</th></tr></thead><tbody>';

    definitions.forEach(function (definition) {
        var key = definition[1];
        var actualValue = Number(actual[key] || 0);
        var outlookValue = Number(outlook[key] || 0);
        var priorValue = Number(prior[key] || 0);
        var variance = outlookValue - priorValue;
        var variancePct = percentChange(priorValue, outlookValue);
        html += '<tr class="' + definition[2] + '"><td>' + escapeHtml(definition[0]) + '</td>' +
            '<td>' + escapeHtml(formatFull(actualValue)) + '</td><td>' + formatPercent(ratio(actualValue, actual.net_sales)) + '</td>' +
            '<td>' + escapeHtml(formatFull(outlookValue)) + '</td><td>' + formatPercent(ratio(outlookValue, outlook.net_sales)) + '</td>' +
            '<td>' + escapeHtml(formatFull(priorValue)) + '</td><td>' + formatPercent(ratio(priorValue, prior.net_sales)) + '</td>' +
            '<td class="' + valueClass(key, variance) + '">' + escapeHtml(formatFull(variance)) + '</td>' +
            '<td class="' + valueClass(key, variance) + '">' + signedPercent(variancePct) + '</td></tr>';
    });
    el('executivePlTable').innerHTML = html + '</tbody>';
}

function topShare(rows, count, total) {
    return ratio(rows.slice(0, count).reduce(function (sum, row) {
        return sum + Number(row.net_sales || 0);
    }, 0), total);
}

function renderCfoSignals(data) {
    var outlook = data.outlook;
    var prior = data.priorYear;
    var salesChange = outlook.net_sales - prior.net_sales;
    var opChange = outlook.operating_profit - prior.operating_profit;
    var incrementalMargin = ratio(opChange, salesChange);
    var gmBps = (ratio(outlook.gross_margin, outlook.net_sales) - ratio(prior.gross_margin, prior.net_sales)) * 10000;
    var lossShare = ratio(data.productRisk.loss_making_revenue, data.productRisk.total_revenue);
    var topFive = topShare(data.concentration.customers, 5, outlook.net_sales);
    var signals = [
        {
            cls: gmBps >= 0 ? 'positive' : (gmBps < -200 ? 'critical' : 'warning'),
            label: gmBps >= 0 ? 'Gross margin improvement' : 'Gross margin compression',
            value: (gmBps >= 0 ? '+' : '') + gmBps.toFixed(0) + ' bps',
            copy: gmBps >= 0
                ? 'Outlook margin versus FY2025. Protect the mix and cost gains behind the improvement.'
                : 'Outlook margin versus FY2025. Prioritize pricing, mix, and direct-cost recovery.'
        },
        {
            cls: incrementalMargin < 0 ? 'critical' : 'positive',
            label: 'Incremental operating margin',
            value: formatPercent(incrementalMargin),
            copy: 'Operating profit change divided by revenue change. Negative conversion signals value-destructive growth.'
        },
        {
            cls: lossShare > .25 ? 'critical' : 'warning',
            label: 'Loss-making revenue exposure',
            value: formatPercent(lossShare),
            copy: 'Share of outlook revenue generated by product groups below operating break-even.'
        },
        {
            cls: topFive > .5 ? 'warning' : 'neutral',
            label: 'Top 5 customer concentration',
            value: formatPercent(topFive),
            copy: 'Revenue dependency on the five largest customers in the 2026 operating outlook.'
        }
    ];
    el('cfoSignalGrid').innerHTML = signals.map(function (signal) {
        return '<article class="signal-card ' + signal.cls + '"><div class="signal-label">' +
            escapeHtml(signal.label) + '</div><div class="signal-value">' + escapeHtml(signal.value) +
            '</div><div class="signal-copy">' + escapeHtml(signal.copy) + '</div></article>';
    }).join('');
}

function renderCfoCharts(data) {
    var outlook = data.outlook;
    var prior = data.priorYear;
    var bridge = [
        outlook.net_sales - prior.net_sales,
        outlook.gross_margin - prior.gross_margin,
        outlook.opex - prior.opex,
        outlook.operating_profit - prior.operating_profit,
        outlook.net_income - prior.net_income
    ];
    destroyChart('profitBridge');
    charts.profitBridge = new Chart(el('profitBridgeChart'), {
        type: 'bar',
        data: {
            labels: ['Revenue', 'Gross Profit', 'OpEx', 'Operating Profit', 'Net Profit'],
            datasets: [{
                label: 'Variance vs FY2025',
                data: bridge.map(function (value) { return value / 1e6; }),
                backgroundColor: bridge.map(function (value, index) {
                    if (index === 2) return value <= 0 ? colors.green : colors.red;
                    return value >= 0 ? colors.green : colors.red;
                }),
                borderRadius: 5,
                maxBarThickness: 42
            }]
        },
        options: baseChartOptions('$ millions')
    });

    var customers = data.concentration.customers.slice(0, 8);
    var concentrationOptions = horizontalChartOptions('% of outlook revenue');
    concentrationOptions.plugins.legend.display = false;
    concentrationOptions.plugins.tooltip.callbacks.label = function (context) {
        return Number(context.parsed.x).toFixed(1) + '% of outlook revenue';
    };
    concentrationOptions.scales.x.ticks.callback = function (value) { return value + '%'; };
    destroyChart('concentration');
    charts.concentration = new Chart(el('concentrationChart'), {
        type: 'bar',
        data: {
            labels: customers.map(function (row) { return row.label; }),
            datasets: [{
                data: customers.map(function (row) { return ratio(row.net_sales, outlook.net_sales) * 100; }),
                backgroundColor: customers.map(function (_, index) { return index < 3 ? colors.violet : '#9b8de2'; }),
                borderRadius: 4
            }]
        },
        options: concentrationOptions
    });
}

function cleanDimensionLabel(value) {
    var label = String(value == null ? '' : value).trim();
    if (!label || /^-?\d{6,}$/.test(label)) return 'Unmapped product';
    return label;
}

function productRisk(row) {
    var gmRate      = ratio(row.gross_margin, row.net_sales);
    var opRate      = ratio(row.operating_profit, row.net_sales);
    var priorGmRate = ratio(row.prior_gross_margin, row.prior_net_sales);
    var gmDrop      = priorGmRate != null ? (gmRate - priorGmRate) * 100 : 0;
    var gmPct       = (gmRate || 0) * 100;

    if (gmRate < 0) {
        return { cls: 'critical', label: 'Intervene',
            action: 'Negative gross margin — losing money on every unit sold. Reprice, renegotiate COGS, or exit this volume.' };
    }
    if (opRate < 0) {
        return { cls: 'critical', label: 'Intervene',
            action: 'Operating loss despite positive gross margin. OpEx exceeds the margin contribution — review fixed cost allocation.' };
    }
    if (priorGmRate != null && gmDrop < -3) {
        return { cls: 'eroding', label: 'Recover',
            action: 'Gross margin fell ' + Math.abs(gmDrop).toFixed(1) + ' pp YoY. Review discount policy, channel mix, and COGS drivers urgently.' };
    }
    if (gmPct < 10) {
        return { cls: 'watch', label: 'Watch',
            action: 'Gross margin below 10% — insufficient buffer to absorb operating expense. Target repricing or direct cost reduction.' };
    }
    if (priorGmRate != null && gmDrop < -1) {
        return { cls: 'watch', label: 'Watch',
            action: 'Margin slipping ' + Math.abs(gmDrop).toFixed(1) + ' pp — monitor channel mix and discount exposure before it accelerates.' };
    }
    if (gmPct >= 25 && (priorGmRate == null || gmDrop >= -0.5)) {
        return { cls: 'star', label: 'Star',
            action: 'High-margin product with stable or improving economics. Prioritise volume growth and defend price positioning.' };
    }
    return { cls: 'healthy', label: 'Scale',
        action: 'Margins healthy and stable. Defend pricing discipline and look for selective volume growth opportunities.' };
}

function renderProfitabilityTable(data) {
    var rows = data.profitability;
    var totalRevenue = rows.reduce(function (s, r) { return s + Number(r.net_sales || 0); }, 0);
    var critCount = 0, critRev = 0, erodCount = 0, watchCount = 0;

    var html = '<thead><tr>' +
        '<th>Product group</th><th>Revenue</th><th>vs 2025</th><th>COGS %</th>' +
        '<th>Gross margin %</th><th>GM Δ</th><th>Op margin %</th>' +
        '<th>Status</th><th>Management action</th>' +
        '</tr></thead><tbody>';

    rows.forEach(function (row) {
        var revenueChange = percentChange(row.prior_net_sales, row.net_sales);
        var gmRate      = ratio(row.gross_margin, row.net_sales);
        var opRate      = ratio(row.operating_profit, row.net_sales);
        var cogsRate    = ratio(row.cogs, row.net_sales);
        var priorGmRate = ratio(row.prior_gross_margin, row.prior_net_sales);
        var gmChange    = priorGmRate == null ? null : (gmRate - priorGmRate) * 100;
        var shareOfTotal = totalRevenue > 0 ? Number(row.net_sales || 0) / totalRevenue * 100 : 0;
        var risk = productRisk(row);

        if (risk.cls === 'critical') { critCount++; critRev += Number(row.net_sales || 0); }
        else if (risk.cls === 'eroding') erodCount++;
        else if (risk.cls === 'watch') watchCount++;

        // GM bar: 40% gross margin = full bar width; capped at 100%
        var gmBarPct = Math.min(Math.max((gmRate || 0) * 250, 0), 100);
        var gmBarCls = (gmRate || 0) < 0 ? 'red' : (gmRate || 0) * 100 < 10 ? 'amber' : '';
        var gmChangeCls = gmChange == null ? '' : gmChange < 0 ? 'neg' : 'pos';
        var rowCls = risk.cls === 'critical' ? ' class="row-critical"'
                   : risk.cls === 'eroding'  ? ' class="row-eroding"' : '';

        html +=
            '<tr' + rowCls + '>' +
            '<td>' + escapeHtml(cleanDimensionLabel(row.label)) + '</td>' +
            '<td>' + escapeHtml(formatCompact(row.net_sales)) +
                '<span class="cell-sub">' + shareOfTotal.toFixed(1) + '% of outlook</span></td>' +
            '<td class="' + valueClass('net_sales', Number(row.net_sales) - Number(row.prior_net_sales)) + '">' +
                signedPercent(revenueChange) + '</td>' +
            '<td>' + formatPercent(cogsRate) + '</td>' +
            '<td><div class="gm-bar-wrap">' +
                '<span>' + formatPercent(gmRate) + '</span>' +
                '<div class="gm-bar-track"><span class="gm-bar-fill' + (gmBarCls ? ' ' + gmBarCls : '') +
                '" style="width:' + gmBarPct.toFixed(0) + '%"></span></div>' +
            '</div></td>' +
            '<td class="' + gmChangeCls + '">' +
                (gmChange == null ? '--' : (gmChange >= 0 ? '+' : '') + gmChange.toFixed(1) + ' pp') + '</td>' +
            '<td class="' + (opRate < 0 ? 'neg' : '') + '">' + formatPercent(opRate) + '</td>' +
            '<td><span class="risk-tag ' + risk.cls + '">' + escapeHtml(risk.label) + '</span></td>' +
            '<td>' + escapeHtml(risk.action) + '</td>' +
            '</tr>';
    });

    html += '</tbody>';

    if (rows.length > 0) {
        var parts = [];
        if (critCount > 0) parts.push(critCount + ' loss-making (' + formatCompact(critRev) + ' revenue at risk)');
        if (erodCount > 0) parts.push(erodCount + ' margin eroding');
        if (watchCount > 0) parts.push(watchCount + ' below safe threshold');
        if (parts.length === 0) parts.push('All ' + rows.length + ' product groups profitable and stable');
        html += '<tfoot><tr><td colspan="9" class="table-note">Top ' + rows.length +
            ' groups by 2026 outlook revenue · ' + parts.join(' · ') + '</td></tr></tfoot>';
    }

    el('profitabilityTable').innerHTML = html;
}

function loadOverview(force) {
    setLoading('executiveKpiGrid');
    setLoading('executivePlTable');
    setLoading('cfoSignalGrid');
    setLoading('profitabilityTable');
    return fetchJson(API + '/api/executive-outlook' + queryString({}, {
        ignoreYear: true,
        ignoreVersion: true
    }), { force: force, timeout: 45000 })
        .then(function (data) {
            executiveData = data;
            renderExecutiveKPIs(data);
            renderExecutiveCharts(data);
            renderExecutivePL(data);
            renderCfoSignals(data);
            renderCfoCharts(data);
            renderProfitabilityTable(data);
            tabLoaded.overview = true;
        })
        .catch(handleLoadError);
}

function loadRegional(force) {
    setLoading('regionalTable');
    var metric = el('regMetric').value;
    return fetchJson(API + '/api/regional-pl' + queryString(), { force: force })
        .then(function (data) {
            var regions = unique(data.map(function (row) { return row.region_desc; }).filter(Boolean));
            var years = unique(data.map(function (row) { return row.year; })).sort();
            destroyChart('regional');
            charts.regional = new Chart(el('regionalChart'), {
                type: 'bar',
                data: {
                    labels: regions,
                    datasets: years.map(function (year, index) {
                        return {
                            label: yearLabel(year),
                            data: regions.map(function (region) {
                                var row = data.find(function (item) { return item.year === year && item.region_desc === region; });
                                return row ? Number(row[metric] || 0) / 1e6 : 0;
                            }),
                            backgroundColor: yearColors[index % yearColors.length],
                            borderRadius: 4,
                            maxBarThickness: 22
                        };
                    })
                },
                options: baseChartOptions('$ millions')
            });

            var html = '<thead><tr><th>Region</th>';
            years.forEach(function (year) { html += '<th>' + escapeHtml(yearLabel(year)) + '</th>'; });
            html += '</tr></thead><tbody>';
            regions.forEach(function (region) {
                html += '<tr><td>' + escapeHtml(region) + '</td>';
                years.forEach(function (year) {
                    var row = data.find(function (item) { return item.year === year && item.region_desc === region; });
                    var value = row ? Number(row[metric] || 0) : 0;
                    html += '<td class="' + (value < 0 ? 'neg' : '') + '">' + escapeHtml(formatCompact(value)) + '</td>';
                });
                html += '</tr>';
            });
            el('regionalTable').innerHTML = html + '</tbody>';
            tabLoaded.regional = true;
        })
        .catch(handleLoadError);
}

function loadProduct(force) {
    setLoading('productTable');
    return fetchJson(API + '/api/mgroup-pl' + queryString({}, { ignoreYear: true }), { force: force })
        .then(function (data) {
            productData = data;
            renderProduct();
            tabLoaded.product = true;
        })
        .catch(handleLoadError);
}

function renderProduct() {
    var year1 = Number(el('prodYear').value);
    var year2 = Number(el('prodYear2').value);
    var metric = el('prodMetric').value;
    if (year1 === year2) {
        showToast('Choose two different years', true);
        return;
    }
    var primary = productData
        .filter(function (row) { return row.year === year1; })
        .sort(function (a, b) { return Number(b[metric] || 0) - Number(a[metric] || 0); })
        .slice(0, 15);
    var comparison = productData.filter(function (row) { return row.year === year2; });
    var labels = primary.map(function (row) { return row.m_group_desc; });

    destroyChart('product');
    charts.product = new Chart(el('productChart'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                { label: yearLabel(year1), data: primary.map(function (row) { return Number(row[metric] || 0) / 1e6; }), backgroundColor: colors.blue, borderRadius: 4 },
                { label: yearLabel(year2), data: labels.map(function (label) { var row = comparison.find(function (item) { return item.m_group_desc === label; }); return row ? Number(row[metric] || 0) / 1e6 : 0; }), backgroundColor: colors.cyan, borderRadius: 4 }
            ]
        },
        options: horizontalChartOptions('$ millions')
    });

    var margins = primary.map(function (row) { return row.net_sales ? row.gross_margin / row.net_sales * 100 : 0; });
    destroyChart('productMargin');
    var marginOptions = horizontalChartOptions('gross margin %');
    marginOptions.plugins.tooltip.callbacks.label = function (context) { return Number(context.parsed.x).toFixed(1) + '%'; };
    marginOptions.scales.x.ticks.callback = function (value) { return value + '%'; };
    charts.productMargin = new Chart(el('productMarginChart'), {
        type: 'bar',
        data: { labels: labels, datasets: [{ data: margins, backgroundColor: margins.map(function (value) { return value >= 0 ? colors.green : colors.red; }), borderRadius: 4 }] },
        options: marginOptions
    });

    var html = '<thead><tr><th>Product group</th><th>' + escapeHtml(yearLabel(year1)) + '</th><th>' +
        escapeHtml(yearLabel(year2)) + '</th><th>Change</th><th>Change %</th><th>GM %</th></tr></thead><tbody>';
    primary.forEach(function (row) {
        var other = comparison.find(function (item) { return item.m_group_desc === row.m_group_desc; });
        var value1 = Number(row[metric] || 0);
        var value2 = other ? Number(other[metric] || 0) : 0;
        var change = value1 - value2;
        var pct = value2 ? change / Math.abs(value2) * 100 : null;
        html += '<tr><td>' + escapeHtml(row.m_group_desc) + '</td><td>' + escapeHtml(formatCompact(value1)) +
            '</td><td>' + escapeHtml(formatCompact(value2)) + '</td><td class="' + valueClass(metric, change) + '">' +
            escapeHtml(formatCompact(change)) + '</td><td class="' + valueClass(metric, change) + '">' +
            (pct == null ? '--' : (pct >= 0 ? '+' : '') + pct.toFixed(1) + '%') + '</td><td>' +
            (row.net_sales ? formatPercent(row.gross_margin / row.net_sales) : '--') + '</td></tr>';
    });
    el('productTable').innerHTML = html + '</tbody>';
}

function horizontalChartOptions(axisLabel) {
    var options = baseChartOptions(axisLabel);
    options.indexAxis = 'y';
    options.plugins.legend.align = 'end';
    options.plugins.tooltip.callbacks.label = function (context) {
        return context.dataset.label ? context.dataset.label + ': $' + Number(context.parsed.x).toFixed(1) + 'M' : '$' + Number(context.parsed.x).toFixed(1) + 'M';
    };
    options.scales.x = {
        grid: { color: '#edf1f6' },
        border: { display: false },
        title: { display: true, text: axisLabel, color: '#96a2b3', font: { size: 9 } },
        ticks: { color: '#66758a', font: { size: 9 }, callback: function (value) { return '$' + value + 'M'; } }
    };
    options.scales.y = { grid: { display: false }, ticks: { color: '#66758a', font: { size: 8 } } };
    return options;
}

function loadDrilldown(force) {
    var year1 = Number(el('ddYear1').value);
    var year2 = Number(el('ddYear2').value);
    var dimension = el('ddDim').value;
    var metric = el('ddMetric').value;
    var button = el('ddBtn');
    if (year1 === year2) {
        showToast('Choose two different years', true);
        return Promise.resolve();
    }
    button.disabled = true;
    button.textContent = 'Running query...';
    setLoading('drilldownTable');

    return fetchJson(API + '/api/drilldown' + queryString({
        year1: year1,
        year2: year2,
        dimension: dimension,
        metric: metric,
        limit: 50
    }, { ignoreYear: true }), { force: force })
        .then(function (data) {
            var top = data.slice(0, 20);
            destroyChart('drilldown');
            charts.drilldown = new Chart(el('drilldownChart'), {
                type: 'bar',
                data: {
                    labels: top.map(function (row) { return row.dimension || 'Unassigned'; }),
                    datasets: [{
                        data: top.map(function (row) { return row.change / 1e6; }),
                        backgroundColor: top.map(function (row) { return isGood(metric, row.change) ? colors.green : colors.red; }),
                        borderRadius: 4
                    }]
                },
                options: horizontalChartOptions('change in $ millions')
            });

            var maxChange = data.reduce(function (max, row) { return Math.max(max, Math.abs(row.change)); }, 0);
            var html = '<thead><tr><th>Dimension</th><th>' + escapeHtml(yearLabel(year1)) + '</th><th>' +
                escapeHtml(yearLabel(year2)) + '</th><th>Change</th><th>Change %</th><th>Impact</th></tr></thead><tbody>';
            data.forEach(function (row) {
                var width = maxChange ? Math.abs(row.change) / maxChange * 100 : 0;
                html += '<tr><td>' + escapeHtml(row.dimension || 'Unassigned') + '</td><td>' +
                    escapeHtml(formatCompact(row.val_year1)) + '</td><td>' + escapeHtml(formatCompact(row.val_year2)) +
                    '</td><td class="' + valueClass(metric, row.change) + '">' + escapeHtml(formatCompact(row.change)) +
                    '</td><td class="' + valueClass(metric, row.change) + '">' +
                    (row.pct_change == null ? '--' : (row.pct_change >= 0 ? '+' : '') + Number(row.pct_change).toFixed(1) + '%') +
                    '</td><td><span class="var-bar ' + (row.change < 0 ? 'neg' : '') + '" style="width:' + width.toFixed(1) + '%"></span></td></tr>';
            });
            el('drilldownTable').innerHTML = html + '</tbody>';
            tabLoaded.drilldown = true;
            showToast(data.length + ' contributors loaded from SQLite');
        })
        .catch(handleLoadError)
        .finally(function () {
            button.disabled = false;
            button.textContent = 'Run analysis';
        });
}

function loadScenario(force) {
    setLoading('scenarioTable');
    return fetchJson(API + '/api/scenario-pl' + queryString({}, { ignoreYear: true, ignoreVersion: true }), { force: force })
        .then(function (data) {
            scenarioData = data;
            renderScenario();
            tabLoaded.scenario = true;
        })
        .catch(handleLoadError);
}

function renderScenario() {
    var metric = el('scenMetric').value;
    var labels = scenarioData.map(function (row) { return String(row.year); });
    var actuals = scenarioData.map(function (row) { return Number(row['actual_' + metric] || 0) / 1e6; });
    var row2026 = scenarioData.find(function (row) { return row.year === 2026; });
    if (!row2026) {
        el('scenarioTable').innerHTML = '<tbody><tr><td>No 2026 scenario records match the filters.</td></tr></tbody>';
        return;
    }
    var actual = Number(row2026['actual_' + metric] || 0);
    var t06 = Number(row2026['t06_' + metric] || 0);
    var t07 = Number(row2026['t07_' + metric] || 0);
    var combined = actual + t06 + t07;

    destroyChart('scenario');
    charts.scenario = new Chart(el('scenarioChart'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                { label: 'Actual / YTD', data: actuals, backgroundColor: colors.blue, borderRadius: 5 },
                { label: 'T06 P06', data: scenarioData.map(function (row) { return row.year === 2026 ? t06 / 1e6 : null; }), backgroundColor: colors.amber, borderRadius: 5 },
                { label: 'T07 P07-P12', data: scenarioData.map(function (row) { return row.year === 2026 ? t07 / 1e6 : null; }), backgroundColor: colors.violet, borderRadius: 5 }
            ]
        },
        options: baseChartOptions('$ millions')
    });

    destroyChart('attainment');
    charts.attainment = new Chart(el('attainmentChart'), {
        type: 'bar',
        data: {
            labels: ['Actual P01-P05', 'T06 P06', 'T07 P07-P12', 'Combined 2026'],
            datasets: [{
                data: [actual / 1e6, t06 / 1e6, t07 / 1e6, combined / 1e6],
                backgroundColor: [colors.blue, colors.amber, colors.violet, colors.green],
                borderRadius: 5
            }]
        },
        options: horizontalChartOptions('$ millions')
    });

    var definitions = [
        ['Net Sales', 'net_sales'],
        ['COGS', 'cogs'],
        ['Gross Margin', 'gross_margin'],
        ['Operating Expense', 'opex'],
        ['Operating Profit', 'operating_profit'],
        ['Net Income', 'net_income']
    ];
    var html = '<thead><tr><th>Metric</th><th>Actual P01-P05</th><th>T06 P06</th><th>T07 P07-P12</th><th>Combined outlook</th><th>Actual share</th></tr></thead><tbody>';
    definitions.forEach(function (definition) {
        var key = definition[1];
        var actualValue = Number(row2026['actual_' + key] || 0);
        var t06Value = Number(row2026['t06_' + key] || 0);
        var t07Value = Number(row2026['t07_' + key] || 0);
        var total = actualValue + t06Value + t07Value;
        var share = total > 0 && actualValue >= 0 ? actualValue / total * 100 : null;
        html += '<tr><td>' + escapeHtml(definition[0]) + '</td><td>' + escapeHtml(formatCompact(actualValue)) +
            '</td><td>' + escapeHtml(formatCompact(t06Value)) + '</td><td>' + escapeHtml(formatCompact(t07Value)) +
            '</td><td class="' + (total < 0 ? 'neg' : '') + '">' + escapeHtml(formatCompact(total)) +
            '</td><td>' + (share == null ? '--' : share.toFixed(1) + '%') + '</td></tr>';
    });
    el('scenarioTable').innerHTML = html + '</tbody>';
}

function unique(values) {
    return Array.from(new Set(values));
}

function handleLoadError(error) {
    setStatus(false, 'Query failed');
    showToast(error.message, true);
    throw error;
}

function loadActiveTab(force) {
    setStatus(true, 'Querying SQLite');
    var loader = {
        overview: loadOverview,
        regional: loadRegional,
        product: loadProduct,
        drilldown: loadDrilldown,
        scenario: loadScenario
    }[activeTab];
    return Promise.resolve(loader(force)).then(function () {
        setStatus(true, 'Live SQLite');
    }).catch(function () {
        // The loader already surfaced the error.
    });
}

function activateTab(tabName) {
    activeTab = tabName;
    document.querySelectorAll('.tab').forEach(function (tab) {
        var selected = tab.dataset.tab === tabName;
        tab.classList.toggle('active', selected);
        tab.setAttribute('aria-selected', selected ? 'true' : 'false');
    });
    document.querySelectorAll('.panel').forEach(function (panel) {
        var selected = panel.id === 'panel-' + tabName;
        panel.classList.toggle('active', selected);
        panel.hidden = !selected;
    });
    el('pageTitle').textContent = pageMeta[tabName][0];
    el('pageSubtitle').textContent = pageMeta[tabName][1];
    configureGlobalFiltersForTab(tabName);
    if (!tabLoaded[tabName]) loadActiveTab(false);
}

function configureGlobalFiltersForTab(tabName) {
    var yearSelect = el('globalYear');
    var versionSelect = el('globalVersion');
    var versionLabel = el('globalVersionLabel');
    var executiveOption = versionSelect.querySelector('option[value="executive"]');

    if (tabName === 'overview') {
        if (!yearSelect.disabled) {
            standardFilterState.year = yearSelect.value;
            standardFilterState.version = versionSelect.value || 'Actual';
        }
        yearSelect.value = '2026';
        yearSelect.disabled = true;
        if (!executiveOption) {
            executiveOption = document.createElement('option');
            executiveOption.value = 'executive';
            executiveOption.textContent = 'Actual + Outlook';
            versionSelect.appendChild(executiveOption);
        }
        versionSelect.value = 'executive';
        versionSelect.disabled = true;
        versionLabel.textContent = 'Reporting view';
        return;
    }

    var returningFromExecutive = yearSelect.disabled;
    yearSelect.disabled = false;
    versionSelect.disabled = false;
    if (executiveOption) executiveOption.remove();
    if (returningFromExecutive) {
        yearSelect.value = standardFilterState.year;
        versionSelect.value = standardFilterState.version;
    }
    if (!versionSelect.value || versionSelect.value === 'executive') versionSelect.value = 'Actual';
    versionLabel.textContent = 'Version';
}

function refreshCountryOptions() {
    var region = el('globalRegion').value;
    return fetchJson(API + '/api/filters' + (region ? '?region=' + encodeURIComponent(region) : ''), { force: true })
        .then(function (data) {
            filters.countries = data.countries || [];
            fillSelect(el('globalCountry'), filters.countries, { emptyLabel: 'All countries' });
        });
}

function applyFilters() {
    if (activeTab !== 'overview') {
        standardFilterState.year = el('globalYear').value;
        standardFilterState.version = el('globalVersion').value;
    }
    requestCache.clear();
    Object.keys(tabLoaded).forEach(function (key) { tabLoaded[key] = false; });
    yearlyData = [];
    executiveData = null;
    productData = [];
    scenarioData = [];
    loadActiveTab(true);
}

function resetFilters() {
    el('globalYear').value = activeTab === 'overview' ? '2026' : '';
    el('globalVersion').value = activeTab === 'overview' ? 'executive' : 'Actual';
    el('globalRegion').value = '';
    el('globalCountry').value = '';
    if (activeTab !== 'overview') {
        standardFilterState.year = '';
        standardFilterState.version = 'Actual';
    }
    applyFilters();
}

function exportCSV(tableId, filename) {
    var table = el(tableId);
    if (!table) return;
    var lines = [];
    table.querySelectorAll('tr').forEach(function (row) {
        var columns = [];
        row.querySelectorAll('th,td').forEach(function (cell) {
            var text = cell.textContent.replace(/\s+/g, ' ').trim();
            if (/^[=+\-@]/.test(text)) text = "'" + text;
            columns.push('"' + text.replace(/"/g, '""') + '"');
        });
        lines.push(columns.join(','));
    });
    var blob = new Blob(['\ufeff' + lines.join('\n')], { type: 'text/csv;charset=utf-8' });
    var objectUrl = URL.createObjectURL(blob);
    var anchor = document.createElement('a');
    anchor.href = objectUrl;
    anchor.download = (filename || 'dashboard-export') + '.csv';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(objectUrl);
    showToast('CSV exported');
}

function bindEvents() {
    document.querySelectorAll('.tab').forEach(function (tab) {
        tab.addEventListener('click', function () { activateTab(tab.dataset.tab); });
    });
    el('applyFiltersBtn').addEventListener('click', applyFilters);
    el('resetFiltersBtn').addEventListener('click', resetFilters);
    el('refreshBtn').addEventListener('click', function () {
        requestCache.clear();
        loadActiveTab(true);
    });
    el('globalRegion').addEventListener('change', refreshCountryOptions);
    el('regMetric').addEventListener('change', function () { loadRegional(false); });
    el('productBtn').addEventListener('click', renderProduct);
    el('prodMetric').addEventListener('change', renderProduct);
    el('ddBtn').addEventListener('click', function () { loadDrilldown(true); });
    el('scenMetric').addEventListener('change', renderScenario);
    document.querySelectorAll('[data-export-table]').forEach(function (button) {
        button.addEventListener('click', function () {
            exportCSV(button.dataset.exportTable, button.dataset.exportName);
        });
    });
}

function configureCharts() {
    if (!window.Chart) throw new Error('Chart.js did not load');
    Chart.defaults.color = '#66758a';
    Chart.defaults.borderColor = '#edf1f6';
    Chart.defaults.font.family = 'Inter, system-ui, sans-serif';
    Chart.defaults.animation.duration = 420;
}

function bootstrap() {
    setStatus(true, 'Connecting');
    configureCharts();
    bindEvents();
    Promise.all([
        fetchJson(API + '/api/status', { force: true }),
        fetchJson(API + '/api/summary', { force: true }),
        fetchJson(API + '/api/filters', { force: true }),
        fetchJson(API + '/api/data-freshness', { force: true })
    ]).then(function (results) {
        var status = results[0];
        summary = results[1];
        filters = results[2];
        freshness = results[3];
        populateControls();
        configureGlobalFiltersForTab(activeTab);
        renderSummaryMeta();
        renderFreshness();
        setStatus(status.database === 'connected', status.backend === 'sqlite-live' ? 'Live SQLite' : 'Fallback cache');
        return loadOverview(false);
    }).catch(function (error) {
        setStatus(false, 'Connection failed');
        showToast(error.message, true);
    });
}

bootstrap();
})();
