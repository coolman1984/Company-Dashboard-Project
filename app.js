(function () {
'use strict';

// Render charts in the dashboard's Arabic-capable font, and right-to-left when
// the page is Arabic. Chart.js is already loaded (script order in index.html).
if (window.Chart) {
    Chart.defaults.font.family = "Cairo, system-ui, -apple-system, sans-serif";
    if (document.documentElement.getAttribute('dir') === 'rtl') {
        Chart.defaults.locale = 'ar';
    }
}

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
var tabLoaded = { overview: false, ask: false, briefing: false, guardian: false, regional: false, product: false, drilldown: false, scenario: false, trends: false, portfolio: false, reports: false, health: false, knowledge: false };
var yearlyData = [];
var executiveData = null;
var productData = [];
var scenarioData = [];

var pageMeta = {
    overview: ['Executive Overview', 'Live profit and loss performance from the SQLite detail ledger'],
    regional: ['Regional Performance', 'Commercial geography, profitability and market contribution'],
    product: ['Product Profitability', 'Product group economics and margin quality'],
    drilldown: ['Variance Contributors', 'The dimensions driving financial movement between periods'],
    scenario: ['2026 Operating Outlook', 'Actual P01-P05 plus T06 P06 plus T07 P07-P12'],
    trends: ['5-Year Trends', 'Structural P&L performance and efficiency ratios FY2022–FY2026'],
    portfolio: ['Strategic Portfolio Matrix', 'Product group growth vs margin positioning for capital allocation decisions'],
    reports: ['Company Reports', 'Generate and download financial reports directly from the database']
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

// Localize Western digits to Arabic-Indic when the user has chosen that mode.
function loc(text) {
    return (window.I18N && window.I18N.localizeDigits) ? window.I18N.localizeDigits(text) : text;
}

function tr(text) {
    return (window.I18N && window.I18N.translateText) ? window.I18N.translateText(text) : text;
}

function isArabicUi() {
    return window.I18N && window.I18N.lang && window.I18N.lang() === 'ar';
}

function formatCompact(value) {
    if (value == null || !Number.isFinite(Number(value))) return '--';
    var number = Number(value);
    var absolute = Math.abs(number);
    if (absolute >= 1e9) return loc((number / 1e9).toFixed(2) + 'B');
    if (absolute >= 1e6) return loc((number / 1e6).toFixed(2) + 'M');
    if (absolute >= 1e3) return loc((number / 1e3).toFixed(1) + 'K');
    return loc(number.toFixed(2));
}

function formatFull(value) {
    if (value == null || !Number.isFinite(Number(value))) return '--';
    return loc(Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
}

function formatPercent(value) {
    if (value == null || !Number.isFinite(Number(value))) return '--';
    return loc((Number(value) * 100).toFixed(1) + '%');
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

function showAlert(title, body) {
    el('appAlertTitle').textContent = title;
    el('appAlertBody').textContent = body;
    el('appAlert').classList.add('show');
}

function hideAlert() {
    el('appAlert').classList.remove('show');
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
    fillSelect(el('ovYear'), filters.years, { defaultValue: 2026 });
    fillSelect(el('portYear'), filters.years, { defaultValue: filters.years[filters.years.length - 1], labeler: yearLabeler });
    fillSelect(el('portPriorYear'), filters.years, { defaultValue: filters.years[Math.max(0, filters.years.length - 2)], labeler: yearLabeler });
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
        var period = String(actual2026.maxPeriodNumber).padStart(2, '0');
        if (isArabicUi()) {
            note.innerHTML =
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="9"/><path d="M12 10v6m0-9h.01"/></svg>' +
                '<span><strong>' + escapeHtml(tr('Data is fresh.')) + '</strong> ' +
                'المصدر: SQLite مباشر (' + (summary ? Number(summary.totalRows).toLocaleString('en-US') : '--') +
                ' سجل) &nbsp;|&nbsp; الفعلي: P01-P' + period +
                ' &nbsp;|&nbsp; توقعات 2026: فعلي P01-P05 + T06 P06 + T07 P07-P12.</span>';
        } else {
            note.innerHTML =
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="9"/><path d="M12 10v6m0-9h.01"/></svg>' +
                '<span><strong>Data is fresh.</strong> Source: live SQLite (' +
                (summary ? Number(summary.totalRows).toLocaleString('en-US') : '--') +
                ' records) &nbsp;|&nbsp; Actual: P01-P' + period +
                ' &nbsp;|&nbsp; 2026 outlook: Actual P01-P05 + T06 P06 + T07 P07-P12.</span>';
        }
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
                callbacks: { label: function (context) { return tr(context.dataset.label) + ': $' + loc(Number(context.parsed.y).toFixed(1) + 'M'); } }
            }
        },
        scales: {
            x: { grid: { display: false }, ticks: { color: '#66758a', font: { size: 9 } } },
            y: {
                grid: { color: '#edf1f6' },
                border: { display: false },
                title: { display: !!axisLabel, text: tr(axisLabel), color: '#96a2b3', font: { size: 9 } },
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
    var cov = data.coverage;
    var actualShare = ratio(data.actualYtd.net_sales, outlook.net_sales);
    var revenueGrowth = percentChange(prior.net_sales, outlook.net_sales);
    var grossGrowth = percentChange(prior.gross_margin, outlook.gross_margin);
    var opVariance = outlook.operating_profit - prior.operating_profit;
    var netVariance = outlook.net_income - prior.net_income;
    var lossRevenueShare = ratio(risk.loss_making_revenue, risk.total_revenue);
    var priorLabel = 'FY' + cov.priorYear;
    var cards = [
        {
            label: cov.isOutlookYear ? 'Revenue outlook' : 'Revenue',
            value: formatCompact(outlook.net_sales),
            sub: signedPercent(revenueGrowth) + ' ' + tr('vs') + ' ' + priorLabel + (cov.isOutlookYear ? ' | ' + formatPercent(actualShare) + ' ' + tr('completed') : ''),
            tone: 'blue',
            icon: '\u2191',
            metric: 'net_sales',
            change: revenueGrowth
        },
        {
            label: 'Gross profit',
            value: formatCompact(outlook.gross_margin),
            sub: signedPercent(grossGrowth) + ' ' + tr('vs') + ' ' + priorLabel + ' | ' + tr('Margin') + ' ' + formatPercent(ratio(outlook.gross_margin, outlook.net_sales)),
            tone: 'cyan',
            icon: '$',
            metric: 'gross_margin',
            change: grossGrowth
        },
        {
            label: 'Operating profit',
            value: formatCompact(outlook.operating_profit),
            sub: formatCompact(opVariance) + ' ' + tr('vs') + ' ' + priorLabel + ' | ' + tr('Margin') + ' ' + formatPercent(ratio(outlook.operating_profit, outlook.net_sales)),
            tone: 'violet',
            icon: '\u25C9',
            metric: 'operating_profit',
            change: opVariance
        },
        {
            label: 'Net profit',
            value: formatCompact(outlook.net_income),
            sub: formatCompact(netVariance) + ' ' + tr('vs') + ' ' + priorLabel + ' | ' + tr('Margin') + ' ' + formatPercent(ratio(outlook.net_income, outlook.net_sales)),
            tone: 'green',
            icon: '\u25C6',
            metric: 'net_income',
            change: netVariance
        },
        {
            label: 'Revenue at risk',
            value: formatPercent(lossRevenueShare),
            sub: Number(risk.loss_making_products || 0) + ' product groups forecast below operating break-even',
            tone: 'amber',
            icon: '\u26A0',
            metric: 'operating_profit',
            change: -Number(risk.loss_making_revenue || 0)
        }
    ];

    el('executiveKpiGrid').innerHTML = cards.map(function (card) {
        return '<article class="kpi-card">' +
            '<div class="kpi-top"><span class="kpi-icon ' + card.tone + '">' +
            escapeHtml(card.icon) + '</span><div><div class="kpi-label">' + escapeHtml(tr(card.label)) +
            '</div><div class="kpi-value">' + escapeHtml(card.value) + '</div></div></div>' +
            '<div class="kpi-sub ' + valueClass(card.metric, card.change) + '">' + escapeHtml(card.sub) + '</div>' +
            '</article>';
    }).join('');
}

function executiveLineDataset(label, values, color, dashed) {
    return {
        label: tr(label),
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
    var coverage = data.coverage;
    var monthly = data.monthly.slice().sort(function (a, b) { return a.period_number - b.period_number; });
    var labels = monthly.map(function (row) { return row.period_label; });
    var cumulative = 0;
    var cumulativeValues = monthly.map(function (row) {
        cumulative += Number(row.net_sales || 0);
        return cumulative / 1e6;
    });
    var actualRevenue, outlookRevenue, actualMargin, outlookMargin;
    if (coverage.isOutlookYear) {
        actualRevenue = cumulativeValues.map(function (value, index) { return index <= 4 ? value : null; });
        outlookRevenue = cumulativeValues.map(function (value, index) { return index >= 4 ? value : null; });
        actualMargin = monthly.map(function (row, index) {
            return index <= 4 && row.net_sales ? Number(row.gross_margin) / Number(row.net_sales) * 100 : null;
        });
        outlookMargin = monthly.map(function (row, index) {
            if (index === 4 && row.net_sales) return Number(row.gross_margin) / Number(row.net_sales) * 100;
            return index >= 5 && row.net_sales ? Number(row.gross_margin) / Number(row.net_sales) * 100 : null;
        });
    } else {
        actualRevenue = cumulativeValues;
        outlookRevenue = cumulativeValues.map(function () { return null; });
        actualMargin = monthly.map(function (row) {
            return row.net_sales ? Number(row.gross_margin) / Number(row.net_sales) * 100 : null;
        });
        outlookMargin = monthly.map(function () { return null; });
    }

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
    var cov = data.coverage;
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
    var html;
    if (cov.isOutlookYear) {
        html = '<thead><tr><th rowspan="2">' + tr('Account') + '</th>' +
            '<th colspan="2">' + tr('Actual ' + cov.year + ' P01-P05') + '</th><th colspan="2">' + tr(cov.year + ' Outlook P01-P12') + '</th>' +
            '<th colspan="2">' + tr(cov.priorYear + ' Full Year') + '</th><th colspan="2">' + tr('Variance vs ' + cov.priorYear) + '</th></tr>' +
            '<tr><th>' + tr('Amount') + '</th><th>' + tr('% Revenue') + '</th><th>' + tr('Amount') + '</th><th>' + tr('% Revenue') + '</th>' +
            '<th>' + tr('Amount') + '</th><th>' + tr('% Revenue') + '</th><th>' + tr('Amount') + '</th><th>%</th></tr></thead><tbody>';
    } else {
        html = '<thead><tr><th rowspan="2">' + tr('Account') + '</th>' +
            '<th colspan="2">' + tr('FY' + cov.year + ' Actual') + '</th>' +
            '<th colspan="2">' + tr('FY' + cov.priorYear + ' Full Year') + '</th><th colspan="2">' + tr('Variance vs ' + cov.priorYear) + '</th></tr>' +
            '<tr><th>' + tr('Amount') + '</th><th>' + tr('% Revenue') + '</th>' +
            '<th>' + tr('Amount') + '</th><th>' + tr('% Revenue') + '</th><th>' + tr('Amount') + '</th><th>%</th></tr></thead><tbody>';
    }

    definitions.forEach(function (definition) {
        var key = definition[1];
        var actualValue = Number(actual[key] || 0);
        var outlookValue = Number(outlook[key] || 0);
        var priorValue = Number(prior[key] || 0);
        var variance = outlookValue - priorValue;
        var variancePct = percentChange(priorValue, outlookValue);
        if (cov.isOutlookYear) {
            html += '<tr class="' + definition[2] + '"><td>' + escapeHtml(tr(definition[0])) + '</td>' +
                '<td>' + escapeHtml(formatFull(actualValue)) + '</td><td>' + formatPercent(ratio(actualValue, actual.net_sales)) + '</td>' +
                '<td>' + escapeHtml(formatFull(outlookValue)) + '</td><td>' + formatPercent(ratio(outlookValue, outlook.net_sales)) + '</td>' +
                '<td>' + escapeHtml(formatFull(priorValue)) + '</td><td>' + formatPercent(ratio(priorValue, prior.net_sales)) + '</td>' +
                '<td class="' + valueClass(key, variance) + '">' + escapeHtml(formatFull(variance)) + '</td>' +
                '<td class="' + valueClass(key, variance) + '">' + signedPercent(variancePct) + '</td></tr>';
        } else {
            html += '<tr class="' + definition[2] + '"><td>' + escapeHtml(tr(definition[0])) + '</td>' +
                '<td>' + escapeHtml(formatFull(outlookValue)) + '</td><td>' + formatPercent(ratio(outlookValue, outlook.net_sales)) + '</td>' +
                '<td>' + escapeHtml(formatFull(priorValue)) + '</td><td>' + formatPercent(ratio(priorValue, prior.net_sales)) + '</td>' +
                '<td class="' + valueClass(key, variance) + '">' + escapeHtml(formatFull(variance)) + '</td>' +
                '<td class="' + valueClass(key, variance) + '">' + signedPercent(variancePct) + '</td></tr>';
        }
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
    var cov = data.coverage;
    var salesChange = outlook.net_sales - prior.net_sales;
    var opChange = outlook.operating_profit - prior.operating_profit;
    var incrementalMargin = ratio(opChange, salesChange);
    var gmBps = (ratio(outlook.gross_margin, outlook.net_sales) - ratio(prior.gross_margin, prior.net_sales)) * 10000;
    var lossShare = ratio(data.productRisk.loss_making_revenue, data.productRisk.total_revenue);
    var topFive = topShare(data.concentration.customers, 5, outlook.net_sales);
    var periodLabel = cov.isOutlookYear ? 'FY' + cov.year + ' outlook' : 'FY' + cov.year;
    var priorLabel = 'FY' + cov.priorYear;
    var signals = [
        {
            cls: gmBps >= 0 ? 'positive' : (gmBps < -200 ? 'critical' : 'warning'),
            label: gmBps >= 0 ? tr('Gross margin improvement') : tr('Gross margin compression'),
            value: (gmBps >= 0 ? '+' : '') + gmBps.toFixed(0) + ' bps',
            copy: gmBps >= 0
                ? periodLabel + ' margin versus ' + priorLabel + '. Protect the mix and cost gains behind the improvement.'
                : periodLabel + ' margin versus ' + priorLabel + '. Prioritize pricing, mix, and direct-cost recovery.'
        },
        {
            cls: incrementalMargin < 0 ? 'critical' : 'positive',
            label: tr('Incremental operating margin'),
            value: formatPercent(incrementalMargin),
            copy: 'Operating profit change divided by revenue change versus ' + priorLabel + '. Negative conversion signals value-destructive growth.'
        },
        {
            cls: lossShare > .25 ? 'critical' : 'warning',
            label: tr('Loss-making revenue exposure'),
            value: formatPercent(lossShare),
            copy: 'Share of ' + periodLabel + ' revenue generated by product groups below operating break-even.'
        },
        {
            cls: topFive > .5 ? 'warning' : 'neutral',
            label: tr('Top 5 customer concentration'),
            value: formatPercent(topFive),
            copy: 'Revenue dependency on the five largest customers in the ' + periodLabel + '.'
        },
        (function () {
            var revGrowth = percentChange(prior.net_sales, outlook.net_sales);
            var opGrowth = percentChange(prior.operating_profit, outlook.operating_profit);
            var leverage = (revGrowth && opGrowth) ? opGrowth / revGrowth : null;
            var cls = leverage == null ? 'neutral'
                : leverage > 1.5 ? 'positive'
                : leverage < 0.5 ? 'critical'
                : 'warning';
            var leverageStr = leverage == null ? '--' : leverage.toFixed(2) + '×';
            var copy = leverage == null
                ? 'Operating leverage cannot be calculated — one or both metrics have no prior-year base.'
                : leverage > 1.5
                ? 'Operating profit is growing faster than revenue — cost structure is scaling efficiently.'
                : leverage < 0.5
                ? 'Revenue is growing faster than profit — costs are not scaling well. Review opex discipline.'
                : 'Revenue and profit growing in similar proportion — neutral operating leverage.';
            return { cls: cls, label: tr('Operating leverage'), value: leverageStr, copy: copy };
        }())
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
            labels: ['Revenue', 'Gross Profit', 'OpEx', 'Operating Profit', 'Net Profit'].map(tr),
            datasets: [{
                label: tr('Variance vs FY' + data.coverage.priorYear),
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
    var concentrationOptions = horizontalChartOptions('% of revenue');
    concentrationOptions.plugins.legend.display = false;
    concentrationOptions.plugins.tooltip.callbacks.label = function (context) {
        return loc(Number(context.parsed.x).toFixed(1) + '%') + ' ' + tr('of revenue');
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

    var allCustomers = data.concentration.customers;
    var hhi = allCustomers.reduce(function (sum, r) {
        var share = Number(r.net_sales || 0) / Math.abs(outlook.net_sales || 1) * 100;
        return sum + share * share;
    }, 0);
    var hhiRisk = hhi > 2500 ? 'High concentration risk' : hhi > 1500 ? 'Moderate concentration' : 'Diversified';
    var hhiNote = el('hhiNote');
    if (hhiNote) {
        if (window.I18N && window.I18N.lang && window.I18N.lang() === 'ar') {
            hhiNote.textContent = 'مؤشر HHI (أكبر 10 عملاء): ' + loc(Math.round(hhi).toLocaleString('en-US')) + ' — ' + tr(hhiRisk) + '. الحدود: أقل من 1,500 متنوع، 1,500–2,500 متوسط، أكثر من 2,500 خطر مرتفع.';
        } else {
            hhiNote.textContent = 'HHI (top 10 customers): ' + Math.round(hhi).toLocaleString('en-US') + ' — ' + hhiRisk + '. Thresholds: <1,500 diversified, 1,500–2,500 moderate, >2,500 high risk.';
        }
    }
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

function renderTopMovers(data) {
    var cov = data.coverage;
    var products = data.profitability.slice().map(function (r) {
        var priorSales = Number(r.prior_net_sales || 0);
        var change = Number(r.net_sales || 0) - priorSales;
        var pct = percentChange(r.prior_net_sales, r.net_sales);
        var currGm = ratio(r.gross_margin, r.net_sales);
        var priorGm = ratio(r.prior_gross_margin, r.prior_net_sales);
        var gmPpChange = (currGm != null && priorGm != null) ? (currGm - priorGm) * 100 : null;
        return { label: r.label, sales: Number(r.net_sales || 0), priorSales: priorSales, change: change, pct: pct, gmPpChange: gmPpChange };
    }).filter(function (r) { return r.priorSales !== 0 || r.change !== 0; });

    products.sort(function (a, b) { return Math.abs(b.change) - Math.abs(a.change); });
    var moversCard = el('moversCard');
    if (!products.length || !cov.priorYear) { moversCard.style.display = 'none'; return; }
    moversCard.style.display = '';

    var html = '<thead><tr><th>' + tr('Product group') + '</th><th>' + tr('FY' + cov.year + ' revenue') + '</th>' +
        '<th>' + tr('Change vs FY' + cov.priorYear) + '</th><th>' + tr('Change %') + '</th><th>' + tr('GM pp shift') + '</th><th>' + tr('Signal') + '</th></tr></thead><tbody>';
    products.slice(0, 10).forEach(function (r) {
        var revCls = valueClass('net_sales', r.change);
        var gmCls = r.gmPpChange == null ? '' : r.gmPpChange >= 0 ? 'pos' : 'neg';
        var signal = r.change > 0 ? (r.gmPpChange != null && r.gmPpChange < -1 ? 'Growing but margin eroding' : 'Strong growth') :
                                    (r.gmPpChange != null && r.gmPpChange < -2 ? 'Declining — margin also falling' : 'Revenue declining');
        html += '<tr><td>' + escapeHtml(cleanDimensionLabel(r.label)) + '</td>' +
            '<td>' + escapeHtml(formatCompact(r.sales)) + '</td>' +
            '<td class="' + revCls + '">' + (r.change >= 0 ? '+' : '') + escapeHtml(formatCompact(r.change)) + '</td>' +
            '<td class="' + revCls + '">' + (r.pct != null ? signedPercent(r.pct) : '--') + '</td>' +
            '<td class="' + gmCls + '">' + (r.gmPpChange != null ? (r.gmPpChange >= 0 ? '+' : '') + r.gmPpChange.toFixed(1) + ' pp' : '--') + '</td>' +
            '<td>' + escapeHtml(tr(signal)) + '</td></tr>';
    });
    el('moversTable').innerHTML = html + '</tbody>';
}

function renderProfitabilityTable(data) {
    var rows = data.profitability;
    var totalRevenue = rows.reduce(function (s, r) { return s + Number(r.net_sales || 0); }, 0);
    var critCount = 0, critRev = 0, erodCount = 0, watchCount = 0;

    var html = '<thead><tr>' +
        '<th>' + tr('Product group') + '</th><th>' + tr('Revenue') + '</th><th>' + tr('vs') + ' 2025</th><th>' + tr('COGS %') + '</th>' +
        '<th>' + tr('Gross margin %') + '</th><th>' + tr('GM Δ') + '</th><th>' + tr('Op margin %') + '</th>' +
        '<th>' + tr('Status') + '</th><th>' + tr('Management action') + '</th>' +
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
                '<span class="cell-sub">' + (isArabicUi() ? shareOfTotal.toFixed(1) + '% من التوقع' : shareOfTotal.toFixed(1) + '% of outlook') + '</span></td>' +
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
            '<td><span class="risk-tag ' + risk.cls + '">' + escapeHtml(tr(risk.label)) + '</span></td>' +
            '<td>' + escapeHtml(tr(risk.action)) + '</td>' +
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
    return fetchJson(API + '/api/executive-outlook' + queryString({ ovYear: el('ovYear').value }, {
        ignoreYear: true,
        ignoreVersion: true
    }), { force: force, timeout: 45000 })
        .then(function (data) {
            executiveData = data;
            var cov = data.coverage;
            var isOutlook = cov.isOutlookYear;
            el('overviewHeading').textContent = tr(cov.year + ' executive ' + (isOutlook ? 'outlook' : 'performance'));
            el('overviewSubtext').textContent = isOutlook
                ? tr(cov.definition + ', compared with FY' + cov.priorYear)
                : tr('FY' + cov.year + ' full-year Actual, compared with FY' + cov.priorYear);
            el('revScenarioBoundary').style.display = isOutlook ? '' : 'none';
            el('gmScenarioBoundary').style.display = isOutlook ? '' : 'none';
            el('plTableTitle').textContent = tr('P&L summary: ' + (isOutlook ? cov.year + ' outlook' : 'FY' + cov.year + ' Actual'));
            el('concentrationSubtitle').textContent = tr('Share of FY' + cov.year + (isOutlook ? ' outlook' : ' revenue') + ' held by the largest customers');
            el('profitBridgeTitle').textContent = tr('Profit bridge vs FY' + cov.priorYear);
            el('profitMatrixSubtitle').textContent = tr('Top product groups by ' + cov.year + ' revenue — margin quality, COGS efficiency, and YoY movement with management action tiers');
            renderExecutiveKPIs(data);
            renderExecutiveCharts(data);
            renderExecutivePL(data);
            renderCfoSignals(data);
            renderCfoCharts(data);
            renderTopMovers(data);
            renderProfitabilityTable(data);
            tabLoaded.overview = true;
        })
        .catch(handleLoadError);
}

function loadTrends(force) {
    if (yearlyData.length) { renderTrends(yearlyData); return Promise.resolve(); }
    return fetchJson(API + '/api/yearly-pl', { force: force })
        .then(function (data) {
            yearlyData = data;
            renderTrends(data);
            tabLoaded.trends = true;
        })
        .catch(handleLoadError);
}

function renderTrends(data) {
    var rows = data.filter(function (r) { return r.version === 'Actual' || !r.version; });
    if (!rows.length) { el('trendKpiGrid').innerHTML = '<div class="loading"><span>No trend data available.</span></div>'; return; }
    rows.sort(function (a, b) { return a.year - b.year; });
    var labels = rows.map(function (r) { return String(r.year); });
    var revenueM = rows.map(function (r) { return Number(r.net_sales || 0) / 1e6; });
    var gmPct = rows.map(function (r) { return r.net_sales ? Number(r.gross_margin || 0) / Number(r.net_sales) * 100 : null; });
    var opProfitM = rows.map(function (r) { return Number(r.operating_profit || 0) / 1e6; });
    var cogsPct = rows.map(function (r) { return r.net_sales ? Number(r.cogs || 0) / Number(r.net_sales) * 100 : null; });
    var opexPct = rows.map(function (r) { return r.net_sales ? Number(r.opex || 0) / Number(r.net_sales) * 100 : null; });

    function yoyGrowth(values) {
        return values.map(function (v, i) {
            if (i === 0 || !values[i - 1]) return null;
            return percentChange(values[i - 1], v);
        });
    }
    var revenueGrowth = yoyGrowth(rows.map(function (r) { return Number(r.net_sales || 0); }));
    var gpGrowth = yoyGrowth(rows.map(function (r) { return Number(r.gross_margin || 0); }));
    var opGrowth = yoyGrowth(rows.map(function (r) { return Number(r.operating_profit || 0); }));

    function cagr(first, last, years) {
        if (!first || first <= 0 || years <= 0) return null;
        return Math.pow(last / first, 1 / years) - 1;
    }
    var n = rows.length - 1;
    var kpis = [
        { label: 'Revenue', value: formatCompact(rows[n].net_sales), cagr: cagr(rows[0].net_sales, rows[n].net_sales, n), tone: 'blue' },
        { label: 'Gross Margin %', value: formatPercent(ratio(rows[n].gross_margin, rows[n].net_sales)), cagr: null, extra: (gmPct[0] != null && gmPct[n] != null ? (gmPct[n] - gmPct[0] >= 0 ? '+' : '') + (gmPct[n] - gmPct[0]).toFixed(1) + ' pp change over period' : null), tone: 'cyan' },
        { label: 'Operating Profit', value: formatCompact(rows[n].operating_profit), cagr: cagr(rows[0].operating_profit, rows[n].operating_profit, n), tone: 'violet' },
        { label: 'Net Income', value: formatCompact(rows[n].net_income), cagr: cagr(rows[0].net_income, rows[n].net_income, n), tone: 'green' }
    ];
    el('trendKpiGrid').innerHTML = kpis.map(function (k) {
        var cagrText = k.cagr != null ? formatPercent(k.cagr) + ' ' + tr('CAGR over') + ' ' + n + ' ' + tr('years') : (tr(k.extra) || tr('--'));
        return '<article class="kpi-card"><div class="kpi-top"><span class="kpi-icon ' + k.tone + '"></span><div><div class="kpi-label">' +
            escapeHtml(k.label) + '</div><div class="kpi-value">' + escapeHtml(k.value) + '</div></div></div>' +
            '<div class="kpi-sub">' + escapeHtml(cagrText) + '</div></article>';
    }).join('');

    destroyChart('revenueTrend');
    charts.revenueTrend = new Chart(el('revenueTrendChart'), {
        data: {
            labels: labels,
            datasets: [
                { type: 'bar', label: tr('Revenue'), data: revenueM, backgroundColor: colors.blue, yAxisID: 'yRev', borderRadius: 4 },
                { type: 'line', label: tr('Gross Margin %'), data: gmPct, borderColor: colors.green, backgroundColor: colors.green, yAxisID: 'yGm', tension: 0.3, pointRadius: 4, borderWidth: 2.5, spanGaps: false }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'top', align: 'end', labels: { usePointStyle: true, pointStyle: 'circle', boxWidth: 7, boxHeight: 7, padding: 14, font: { size: 9, weight: 600 } } },
                tooltip: { padding: 10, titleFont: { size: 10 }, bodyFont: { size: 10 }, callbacks: { label: function (ctx) { return ctx.dataset.yAxisID === 'yRev' ? tr('Revenue: $' + ctx.parsed.y.toFixed(1) + 'M') : tr('GM%: ' + ctx.parsed.y.toFixed(1) + '%'); } } }
            },
            scales: {
                x: { grid: { display: false }, ticks: { color: '#66758a', font: { size: 9 } } },
                yRev: { type: 'linear', position: 'left', grid: { color: '#edf1f6' }, border: { display: false }, ticks: { color: '#66758a', font: { size: 9 }, callback: function (v) { return '$' + v + 'M'; } } },
                yGm: { type: 'linear', position: 'right', grid: { display: false }, border: { display: false }, ticks: { color: '#66758a', font: { size: 9 }, callback: function (v) { return v + '%'; } } }
            }
        }
    });

    var effOptions = baseChartOptions('% of revenue');
    effOptions.plugins.tooltip.callbacks.label = function (ctx) { return tr(ctx.dataset.label) + ': ' + loc(ctx.parsed.y.toFixed(1) + '%'); };
    effOptions.scales.y.ticks.callback = function (v) { return v + '%'; };
    destroyChart('efficiencyTrend');
    charts.efficiencyTrend = new Chart(el('efficiencyTrendChart'), {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                { label: tr('COGS %'), data: cogsPct, borderColor: colors.red, backgroundColor: colors.red, tension: 0.3, pointRadius: 3, borderWidth: 2 },
                { label: tr('OpEx %'), data: opexPct, borderColor: colors.amber, backgroundColor: colors.amber, tension: 0.3, pointRadius: 3, borderWidth: 2 }
            ]
        },
        options: effOptions
    });

    var growthOptions = baseChartOptions('YoY growth %');
    growthOptions.plugins.tooltip.callbacks.label = function (ctx) { return tr(ctx.dataset.label) + ': ' + (ctx.parsed.y != null ? loc((ctx.parsed.y * 100).toFixed(1) + '%') : '--'); };
    growthOptions.scales.y.ticks.callback = function (v) { return (v * 100).toFixed(0) + '%'; };
    destroyChart('growthRate');
    charts.growthRate = new Chart(el('growthRateChart'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                { label: tr('Revenue'), data: revenueGrowth, backgroundColor: revenueGrowth.map(function (v) { return v == null ? 'transparent' : v >= 0 ? colors.blue : colors.red; }), borderRadius: 3 },
                { label: tr('Gross Profit'), data: gpGrowth, backgroundColor: gpGrowth.map(function (v) { return v == null ? 'transparent' : v >= 0 ? colors.cyan : colors.red; }), borderRadius: 3 },
                { label: tr('Operating Profit'), data: opGrowth, backgroundColor: opGrowth.map(function (v) { return v == null ? 'transparent' : v >= 0 ? colors.green : colors.red; }), borderRadius: 3 }
            ]
        },
        options: growthOptions
    });

    var plDefs = [['Revenue', 'net_sales'], ['COGS', 'cogs'], ['Gross Profit', 'gross_margin'], ['OpEx', 'opex'], ['Operating Profit', 'operating_profit'], ['Net Income', 'net_income']];
    var html = '<thead><tr><th>Metric</th>' + labels.map(function (y) { return '<th>' + y + '</th><th>% Rev</th><th>YoY</th>'; }).join('') + '</tr></thead><tbody>';
    plDefs.forEach(function (def) {
        var key = def[1];
        html += '<tr><td>' + escapeHtml(def[0]) + '</td>';
        rows.forEach(function (r, i) {
            var val = Number(r[key] || 0);
            var pctRev = ratio(val, r.net_sales);
            var prev = i > 0 ? Number(rows[i - 1][key] || 0) : null;
            var yoy = prev != null ? percentChange(prev, val) : null;
            var cls = yoy != null ? valueClass(key, yoy) : '';
            html += '<td>' + escapeHtml(formatCompact(val)) + '</td><td>' + formatPercent(pctRev) + '</td><td class="' + cls + '">' + (yoy != null ? signedPercent(yoy) : '--') + '</td>';
        });
        html += '</tr>';
    });
    el('trendTable').innerHTML = html + '</tbody>';
    tabLoaded.trends = true;
}

function loadPortfolio(force) {
    var year = el('portYear').value;
    var priorYear = el('portPriorYear').value;
    if (!year || !priorYear || year === priorYear) { showToast('Choose two different years', true); return Promise.resolve(); }
    setLoading('portfolioTable');
    return fetchJson(API + '/api/portfolio?year=' + encodeURIComponent(year) + '&priorYear=' + encodeURIComponent(priorYear), { force: force })
        .then(function (data) {
            renderPortfolioMatrix(data);
            tabLoaded.portfolio = true;
        })
        .catch(handleLoadError);
}

function renderPortfolioMatrix(data) {
    var products = data.products || [];
    if (!products.length) {
        el('portfolioTable').innerHTML = '<tbody><tr><td>No data for selected years.</td></tr></tbody>';
        destroyChart('portfolio');
        return;
    }

    var totalRevenue = products.reduce(function (s, r) { return s + Number(r.net_sales || 0); }, 0);
    var maxRevenue = products.reduce(function (max, r) { return Math.max(max, Number(r.net_sales || 0)); }, 0);
    var medianGm = (function () {
        var gms = products.map(function (r) { return r.net_sales ? Number(r.gross_margin || 0) / Number(r.net_sales) * 100 : 0; }).sort(function (a, b) { return a - b; });
        return gms[Math.floor(gms.length / 2)] || 0;
    }());

    var riskColors = { critical: colors.red, eroding: colors.amber, watch: '#e89a24', star: colors.green, healthy: colors.cyan };

    destroyChart('portfolio');
    charts.portfolio = new Chart(el('portfolioChart'), {
        type: 'bubble',
        data: {
            datasets: products.map(function (r) {
                var gmPct = r.net_sales ? Number(r.gross_margin || 0) / Number(r.net_sales) * 100 : 0;
                var growth = r.prior_net_sales ? (Number(r.net_sales || 0) - Number(r.prior_net_sales || 0)) / Math.abs(Number(r.prior_net_sales)) * 100 : 0;
                var rev = Number(r.net_sales || 0);
                var radius = Math.max(5, Math.min(35, Math.sqrt(rev / maxRevenue) * 35));
                var risk = productRisk({ gross_margin: r.gross_margin, net_sales: r.net_sales, operating_profit: r.operating_profit, prior_gross_margin: r.prior_gross_margin, prior_net_sales: r.prior_net_sales });
                return {
                    label: cleanDimensionLabel(r.label),
                    data: [{ x: growth, y: gmPct, r: radius }],
                    backgroundColor: (riskColors[risk.cls] || colors.blue) + 'cc',
                    borderColor: riskColors[risk.cls] || colors.blue,
                    borderWidth: 1.5
                };
            })
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: function (ctx) { return ctx.dataset.label + ' — ' + tr('Growth') + ': ' + loc(ctx.parsed.x.toFixed(1) + '%') + ', ' + tr('Gross Margin') + ': ' + loc(ctx.parsed.y.toFixed(1) + '%'); } } }
            },
            scales: {
                x: {
                    grid: { color: '#edf1f6' }, border: { display: false },
                    title: { display: true, text: tr('Revenue growth % vs prior year'), color: '#96a2b3', font: { size: 9 } },
                    ticks: { color: '#66758a', font: { size: 9 }, callback: function (v) { return v + '%'; } }
                },
                y: {
                    grid: { color: '#edf1f6' }, border: { display: false },
                    title: { display: true, text: tr('Gross margin %'), color: '#96a2b3', font: { size: 9 } },
                    ticks: { color: '#66758a', font: { size: 9 }, callback: function (v) { return v + '%'; } }
                }
            }
        }
    });

    var html = '<thead><tr><th>Product group</th><th>Revenue</th><th>Revenue share</th><th>Growth %</th><th>Gross margin %</th><th>Op margin %</th><th>Quadrant</th><th>Risk tier</th><th>Recommended action</th></tr></thead><tbody>';
    products.forEach(function (r) {
        var gmPct = r.net_sales ? Number(r.gross_margin || 0) / Number(r.net_sales) * 100 : 0;
        var opPct = r.net_sales ? Number(r.operating_profit || 0) / Number(r.net_sales) * 100 : 0;
        var growth = r.prior_net_sales ? (Number(r.net_sales || 0) - Number(r.prior_net_sales || 0)) / Math.abs(Number(r.prior_net_sales)) * 100 : null;
        var share = totalRevenue > 0 ? Number(r.net_sales || 0) / totalRevenue * 100 : 0;
        var highGrowth = growth != null && growth > 0;
        var highMargin = gmPct >= medianGm;
        var quadrant = highGrowth && highMargin ? 'Stars — Invest & grow'
            : !highGrowth && highMargin ? 'Cash Cows — Harvest & defend'
            : highGrowth && !highMargin ? 'Question Marks — Fix or exit'
            : 'Traps — Exit priority';
        var risk = productRisk({ gross_margin: r.gross_margin, net_sales: r.net_sales, operating_profit: r.operating_profit, prior_gross_margin: r.prior_gross_margin, prior_net_sales: r.prior_net_sales });
        html += '<tr><td>' + escapeHtml(cleanDimensionLabel(r.label)) + '</td>' +
            '<td>' + escapeHtml(formatCompact(r.net_sales)) + '</td>' +
            '<td>' + share.toFixed(1) + '%</td>' +
            '<td class="' + (growth == null ? '' : growth >= 0 ? 'pos' : 'neg') + '">' + (growth != null ? (growth >= 0 ? '+' : '') + growth.toFixed(1) + '%' : '--') + '</td>' +
            '<td>' + gmPct.toFixed(1) + '%</td>' +
            '<td class="' + (opPct >= 0 ? '' : 'neg') + '">' + opPct.toFixed(1) + '%</td>' +
            '<td>' + escapeHtml(quadrant) + '</td>' +
            '<td><span class="risk-tag ' + risk.cls + '">' + escapeHtml(risk.label) + '</span></td>' +
            '<td>' + escapeHtml(risk.action) + '</td></tr>';
    });
    el('portfolioTable').innerHTML = html + '</tbody>';
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
        return context.dataset.label ? tr(context.dataset.label) + ': ' + loc(Number(context.parsed.x).toFixed(1) + 'M') : loc(Number(context.parsed.x).toFixed(1) + 'M');
    };
    options.scales.x = {
        grid: { color: '#edf1f6' },
        border: { display: false },
        title: { display: true, text: tr(axisLabel), color: '#96a2b3', font: { size: 9 } },
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
    button.textContent = tr('Running query...');
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
                    labels: top.map(function (row) { return row.dimension || tr('Unassigned'); }),
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
            button.textContent = tr('Run analysis');
        });
}

function loadScenario(force) {
    setLoading('scenarioTable');
    initWhatif();
    loadSensitivity(force);
    return fetchJson(API + '/api/scenario-pl' + queryString({}, { ignoreYear: true, ignoreVersion: true }), { force: force })
        .then(function (data) {
            scenarioData = data;
            renderScenario();
            tabLoaded.scenario = true;
        })
        .catch(handleLoadError);
}

var whatifWired = false;
var whatifTimer = null;

function signedPct(value) {
    var n = Number(value) || 0;
    return (n > 0 ? '+' : '') + n + '%';
}

function updateLeverOutputs() {
    el('leverNsOut').textContent = signedPct(el('leverNs').value);
    el('leverCogsOut').textContent = signedPct(el('leverCogs').value);
    el('leverOpexOut').textContent = signedPct(el('leverOpex').value);
    el('leverTaxOut').textContent = (Number(el('leverTax').value) || 0) + '%';
}

function scheduleWhatif() {
    if (whatifTimer) window.clearTimeout(whatifTimer);
    whatifTimer = window.setTimeout(runWhatif, 250);
}

function initWhatif() {
    if (whatifWired) { runWhatif(); return; }
    whatifWired = true;
    ['leverNs', 'leverCogs', 'leverOpex', 'leverTax'].forEach(function (id) {
        el(id).addEventListener('input', function () { updateLeverOutputs(); scheduleWhatif(); });
    });
    el('leverScales').addEventListener('change', scheduleWhatif);
    el('whatifReset').addEventListener('click', function () {
        el('leverNs').value = 0; el('leverCogs').value = 0; el('leverOpex').value = 0;
        el('leverTax').value = 22; el('leverScales').checked = true;
        updateLeverOutputs(); runWhatif();
    });
    updateLeverOutputs();
    runWhatif();
}

function runWhatif() {
    var q = '?ns=' + encodeURIComponent(el('leverNs').value) +
        '&cogs=' + encodeURIComponent(el('leverCogs').value) +
        '&opex=' + encodeURIComponent(el('leverOpex').value) +
        '&tax=' + encodeURIComponent(el('leverTax').value) +
        '&scales=' + (el('leverScales').checked ? 'true' : 'false');
    fetchJson(API + '/api/scenario-whatif' + q, { force: true })
        .then(renderWhatif)
        .catch(function (err) {
            el('whatifTable').innerHTML = '<tbody><tr><td>' + escapeHtml(err.message) + '</td></tr></tbody>';
            el('whatifHeadline').textContent = '';
        });
}

function loadSensitivity(force) {
    var bars = el('sensitivityBars');
    if (!bars) return;
    bars.innerHTML = '<div class="loading-spinner"></div>';
    el('sensitivityTable').innerHTML = '';
    el('sensitivityHeadline').textContent = '';
    fetchJson(API + '/api/sensitivity?delta=5', { force: force })
        .then(renderSensitivity)
        .catch(function (err) { bars.innerHTML = '<div class="wiki-empty">' + escapeHtml(err.message) + '</div>'; });
}

function renderSensitivity(d) {
    var rows = d.rows || [];
    var maxSwing = rows.reduce(function (m, r) { return Math.max(m, Math.abs(r.swing)); }, 0) || 1;

    var headline = el('sensitivityHeadline');
    var top = rows[0];
    if (top) {
        headline.className = 'whatif-headline';
        headline.textContent = tr('Net income is most sensitive to') + ' ' + tr(top.label) +
            ' — ±5% ' + tr('swings it by') + ' ' + formatFull(Math.abs(top.swing)) +
            (top.swing_pct != null ? ' (' + pctVal(Math.abs(top.swing_pct)) + ')' : '');
    }

    el('sensitivityBars').innerHTML = rows.map(function (r) {
        var w = Math.round(Math.abs(r.swing) / maxSwing * 100);
        return '<div class="tornado-row"><div class="t-label">' + escapeHtml(tr(r.label)) + '</div>' +
            '<div class="tornado-track"><div class="tornado-fill" style="width:' + w + '%"></div></div>' +
            '<div class="t-val">' + formatFull(Math.abs(r.swing)) + '</div></div>';
    }).join('');

    var head = '<thead><tr><th>' + tr('Lever') + '</th><th>−5%</th><th>+5%</th><th>' + tr('Swing') + '</th><th>%</th></tr></thead>';
    var body = '<tbody>' + rows.map(function (r) {
        var pct = r.swing_pct != null ? ((r.swing_pct > 0 ? '+' : '') + r.swing_pct + '%') : '';
        return '<tr><td>' + escapeHtml(tr(r.label)) + '</td><td>' + formatFull(r.ni_low) + '</td><td>' +
            formatFull(r.ni_high) + '</td><td>' + formatFull(Math.abs(r.swing)) + '</td><td>' + escapeHtml(pct) + '</td></tr>';
    }).join('') + '</tbody>';
    el('sensitivityTable').innerHTML = head + body;
}

function renderWhatif(data) {
    var rows = (data && data.rows) || [];
    var head = '<thead><tr><th>' + tr('Line item') + '</th><th>' + tr('Baseline') + '</th><th>' +
        tr('Scenario') + '</th><th>' + tr('Change') + '</th><th>%</th></tr></thead>';
    var body = '<tbody>' + rows.map(function (r) {
        var cls = r.change > 0 ? 'delta-up' : (r.change < 0 ? 'delta-down' : '');
        var pctTxt = (r.change_pct == null) ? '' : (r.change_pct > 0 ? '+' : '') + r.change_pct + '%';
        var chTxt = (r.change > 0 ? '+' : '') + formatFull(r.change);
        return '<tr><td>' + escapeHtml(tr(String(r.line_item))) + '</td><td>' + formatFull(r.baseline) +
            '</td><td>' + formatFull(r.scenario) + '</td><td class="' + cls + '">' + chTxt +
            '</td><td class="' + cls + '">' + escapeHtml(pctTxt) + '</td></tr>';
    }).join('') + '</tbody>';
    el('whatifTable').innerHTML = head + body;

    var ni = rows.find(function (r) { return r.line_item === 'Net Income'; });
    var headline = el('whatifHeadline');
    if (ni) {
        var dir = ni.change > 0.5 ? 'up' : (ni.change < -0.5 ? 'down' : '');
        headline.className = 'whatif-headline ' + dir;
        var verb = ni.change >= 0 ? tr('increases by') : tr('decreases by');
        headline.textContent = tr('Net income') + ' ' + verb + ' ' + formatFull(Math.abs(ni.change)) +
            ' → ' + formatFull(ni.scenario) + ' (' + tr('baseline') + ' ' + formatFull(ni.baseline) + ')';
    } else {
        headline.textContent = '';
        headline.className = 'whatif-headline';
    }
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
                { label: tr('Actual / YTD'), data: actuals, backgroundColor: colors.blue, borderRadius: 5 },
                { label: tr('T06 P06'), data: scenarioData.map(function (row) { return row.year === 2026 ? t06 / 1e6 : null; }), backgroundColor: colors.amber, borderRadius: 5 },
                { label: tr('T07 P07-P12'), data: scenarioData.map(function (row) { return row.year === 2026 ? t07 / 1e6 : null; }), backgroundColor: colors.violet, borderRadius: 5 }
            ]
        },
        options: baseChartOptions('$ millions')
    });

    destroyChart('attainment');
    charts.attainment = new Chart(el('attainmentChart'), {
        type: 'bar',
        data: {
            labels: [tr('Actual P01-P05'), tr('T06 P06'), tr('T07 P07-P12'), tr('Combined 2026')],
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
    var html = '<thead><tr><th>' + tr('Metric') + '</th><th>' + tr('Actual P01-P05') + '</th><th>' + tr('T06 P06') + '</th><th>' + tr('T07 P07-P12') + '</th><th>' + tr('Combined outlook') + '</th><th>' + tr('Actual share') + '</th></tr></thead><tbody>';
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
    setStatus(false, tr('Query failed'));
    showToast(error.message, true);
    throw error;
}

function loadReports(force) {
    var listEl = el('reportList');
    var viewCard = el('reportViewCard');
    viewCard.style.display = 'none';
    listEl.innerHTML = '<div class="loading-spinner"></div>';

    return fetchJson(API + '/api/reports', { force: force })
        .then(function (data) {
            var reports = data.reports || [];
            var exportFormats = data.exportFormats || { csv: true, xlsx: true, pdf: true };
            if (!reports.length) {
                listEl.innerHTML = '<div class="report-card"><div class="report-card-body"><div class="report-card-title">No reports available</div></div></div>';
                tabLoaded.reports = true;
                return;
            }
            function downloadButton(name, format) {
                var label = format.toUpperCase();
                if (format !== 'csv' && !exportFormats[format]) {
                    // The server can't render this format (optional dependency missing).
                    // Show a disabled button with a "needs setup" hint instead of a
                    // button that would fail when clicked.
                    return '<button class="secondary-btn report-download-btn" type="button" disabled ' +
                        'title="' + escapeHtml(tr('Export needs setup')) + '">' + label + '</button>';
                }
                return '<button class="secondary-btn report-download-btn" type="button" data-report-name="' +
                    escapeHtml(name) + '" data-format="' + format + '">' + label + '</button>';
            }
            listEl.innerHTML = reports.map(function (r) {
                return '<div class="report-card">' +
                    '<div class="report-card-body">' +
                        '<div class="report-card-title">' + escapeHtml(r.title) + '</div>' +
                        '<div class="report-card-desc">' + escapeHtml(r.description) + '</div>' +
                    '</div>' +
                    '<div class="report-card-actions">' +
                        '<button class="primary-btn" type="button" data-report-name="' + escapeHtml(r.name) + '">' + tr('View') + '</button>' +
                        downloadButton(r.name, 'csv') +
                        downloadButton(r.name, 'xlsx') +
                        downloadButton(r.name, 'pdf') +
                    '</div>' +
                '</div>';
            }).join('');

            listEl.querySelectorAll('.primary-btn').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    viewReport(btn.dataset.reportName);
                });
            });
            listEl.querySelectorAll('.report-download-btn').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    downloadReportFile(btn.dataset.reportName, btn.dataset.format || 'csv');
                });
            });

            tabLoaded.reports = true;
        })
        .catch(function (err) {
            listEl.innerHTML = '<div class="report-card"><div class="report-card-body"><div class="report-card-title">Failed to load reports</div><div class="report-card-desc">' + escapeHtml(err.message) + '</div></div></div>';
            tabLoaded.reports = true;
        });
}

function viewReport(name) {
    var viewCard = el('reportViewCard');
    var viewTitle = el('reportViewTitle');
    var viewSubtitle = el('reportViewSubtitle');
    var viewTable = el('reportViewTable');
    var exportBtn = el('reportExportBtn');
    var listEl = el('reportList');

    viewTitle.textContent = 'Loading...';
    viewSubtitle.textContent = '';
    viewTable.innerHTML = '<tr><td colspan="20"><div class="loading-spinner"></div></td></tr>';
    viewCard.style.display = '';
    listEl.style.display = 'none';
    exportBtn.style.display = 'none';

    fetchJson(API + '/api/reports/generate?name=' + encodeURIComponent(name))
        .then(function (data) {
            viewTitle.textContent = data.title || name;
            viewSubtitle.textContent = data.description || '';
            if (data.row_count != null) {
                viewSubtitle.textContent += ' — ' + data.row_count + ' rows';
            }

            if (!data.columns || !data.rows || !data.rows.length) {
                viewTable.innerHTML = '<tr><td colspan="20">No data returned for this report.</td></tr>';
                return;
            }

            var headerHtml = '<thead><tr>' + data.columns.map(function (c) {
                return '<th>' + escapeHtml(c) + '</th>';
            }).join('') + '</tr></thead>';

            var bodyHtml = '<tbody>' + data.rows.map(function (row) {
                return '<tr>' + data.columns.map(function (c) {
                    var val = row[c];
                    if (val == null) return '<td></td>';
                    if (typeof val === 'number') {
                        if (Number.isInteger(val)) return '<td>' + val.toLocaleString() + '</td>';
                        return '<td>' + val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + '</td>';
                    }
                    return '<td>' + escapeHtml(String(val)) + '</td>';
                }).join('') + '</tr>';
            }).join('') + '</tbody>';

            viewTable.innerHTML = headerHtml + bodyHtml;
            exportBtn.style.display = '';
            exportBtn.dataset.exportTable = 'reportViewTable';
            exportBtn.dataset.exportName = name;
        })
        .catch(function (err) {
            viewTitle.textContent = 'Error';
            viewSubtitle.textContent = err.message;
            viewTable.innerHTML = '<tr><td colspan="20">Failed to generate report: ' + escapeHtml(err.message) + '</td></tr>';
        });
}

function closeReportView() {
    el('reportViewCard').style.display = 'none';
    el('reportList').style.display = '';
}

function downloadReportFile(name, format) {
    format = (format || 'csv').toLowerCase();
    var url = API + '/api/reports/download?name=' + encodeURIComponent(name) + '&format=' + encodeURIComponent(format);
    fetch(url)
        .then(function (response) {
            if (!response.ok) {
                return response.json().catch(function () { return {}; }).then(function (body) {
                    if (body.code === 'export_unavailable') {
                        var err = new Error(tr('Export needs setup'));
                        err.handled = true;
                        throw err;
                    }
                    throw new Error(body.error || 'HTTP ' + response.status);
                });
            }
            return response.blob();
        })
        .then(function (blob) {
            var objectUrl = URL.createObjectURL(blob);
            var anchor = document.createElement('a');
            anchor.href = objectUrl;
            anchor.download = (name || 'report') + '.' + format;
            document.body.appendChild(anchor);
            anchor.click();
            anchor.remove();
            URL.revokeObjectURL(objectUrl);
            showToast(tr('Report downloaded'));
        })
        .catch(function (err) {
            showToast(tr('Download failed') + ': ' + err.message, true);
        });
}

function loadHealth(force) {
    var summaryEl = el('healthSummary');
    var checksTable = el('healthChecksTable');
    var historyTable = el('healthHistoryTable');
    summaryEl.innerHTML = '<div class="loading-spinner"></div>';
    checksTable.innerHTML = '';
    historyTable.innerHTML = '';

    return fetchJson(API + '/api/import-health', { force: force })
        .then(function (data) {
            var s = data.summary || { ok: 0, warn: 0, total: 0, overall: 'OK' };
            var overallOk = s.overall !== 'WARN';
            summaryEl.innerHTML =
                '<div class="health-card ' + (overallOk ? 'is-ok' : 'is-warn') + '">' +
                    '<div class="health-num">' + (overallOk ? tr('Healthy') : tr('Review')) + '</div>' +
                    '<div class="health-lbl">' + tr('Overall status') + '</div>' +
                '</div>' +
                '<div class="health-card is-ok"><div class="health-num">' + s.ok + '</div><div class="health-lbl">' + tr('Checks passed') + '</div></div>' +
                '<div class="health-card ' + (s.warn ? 'is-warn' : 'is-ok') + '"><div class="health-num">' + s.warn + '</div><div class="health-lbl">' + tr('Warnings') + '</div></div>';

            var checks = data.checks || [];
            if (!checks.length) {
                checksTable.innerHTML = '<tbody><tr><td>' + tr('No checks available') + '</td></tr></tbody>';
            } else {
                var head = '<thead><tr><th>' + tr('Category') + '</th><th>' + tr('Check') + '</th><th>' + tr('Value') + '</th><th>' + tr('Status') + '</th></tr></thead>';
                var body = '<tbody>' + checks.map(function (c) {
                    var st = String(c.status || '').toUpperCase();
                    var cls = st === 'WARN' ? 'warn' : 'ok';
                    var label = st === 'WARN' ? tr('Warning') : tr('OK');
                    return '<tr><td>' + escapeHtml(String(c.category || '')) + '</td><td>' + escapeHtml(String(c.item || '')) +
                        '</td><td>' + escapeHtml(String(c.value)) + '</td><td><span class="status-badge ' + cls + '">' + label + '</span></td></tr>';
                }).join('') + '</tbody>';
                checksTable.innerHTML = head + body;
            }

            var history = data.history || [];
            if (!history.length) {
                historyTable.innerHTML = '<tbody><tr><td>' + tr('No client import runs yet. Runs appear here after importing a client file.') + '</td></tr></tbody>';
            } else {
                var hhead = '<thead><tr><th>' + tr('Client') + '</th><th>' + tr('When') + '</th><th>' + tr('Status') + '</th><th>' + tr('Rows') + '</th><th>' + tr('Warnings') + '</th></tr></thead>';
                var hbody = '<tbody>' + history.map(function (r) {
                    var st = String(r.status || '').toLowerCase();
                    var cls = st === 'success' ? 'ok' : 'warn';
                    return '<tr><td>' + escapeHtml(String(r.client_id || '')) + '</td><td>' + escapeHtml(String(r.timestamp || '')) +
                        '</td><td><span class="status-badge ' + cls + '">' + escapeHtml(String(r.status || '')) + '</span></td><td>' +
                        (r.row_count != null ? r.row_count.toLocaleString() : '') + '</td><td>' + (r.warnings || 0) + '</td></tr>';
                }).join('') + '</tbody>';
                historyTable.innerHTML = hhead + hbody;
            }
            tabLoaded.health = true;
        })
        .catch(function (err) {
            summaryEl.innerHTML = '<div class="health-card is-warn"><div class="health-num">!</div><div class="health-lbl">' + escapeHtml(err.message) + '</div></div>';
            tabLoaded.health = true;
        });
}

var briefingWired = false;

function briefArrow(dir) { return dir === 'up' ? '▲' : (dir === 'down' ? '▼' : '■'); }
function pctVal(n) { return loc(Number(n || 0).toFixed(1)) + '%'; }

function briefRiskText(r) {
    if (r.type === 'loss_making') return r.count + ' ' + tr('loss-making product groups') + ' — ' + formatFull(r.amount) + ' ' + tr('revenue at risk');
    if (r.type === 'negative_gm') return r.count + ' ' + tr('product groups with negative gross margin') + ' — ' + formatFull(r.amount) + ' ' + tr('revenue exposed');
    if (r.type === 'concentration') return tr('Top 5 customers concentrate') + ' ' + pctVal(r.pct) + ' ' + tr('of revenue') + (r.top1_label ? ' (' + tr('largest') + ': ' + escapeHtml(String(r.top1_label)) + ' ' + pctVal(r.top1_pct) + ')' : '');
    if (r.type === 'margin') return tr('Gross margin compressed') + ' ' + pctVal(r.drop) + ' pp ' + tr('vs prior year');
    return '';
}
function briefActionText(r) {
    if (r.type === 'loss_making') return tr('Review pricing and direct cost for loss-making groups before committing further volume.');
    if (r.type === 'negative_gm') return tr('Re-price or exit negative-margin product groups.');
    if (r.type === 'concentration') return tr('Diversify the customer base to reduce dependence on the largest accounts.');
    if (r.type === 'margin') return tr('Protect margin: audit discounts, channel mix, and COGS drivers.');
    return '';
}

function loadBriefing(force) {
    if (!briefingWired) {
        briefingWired = true;
        el('briefingPrint').addEventListener('click', function () { window.print(); });
    }
    var body = el('briefingBody');
    body.innerHTML = '<div class="loading-spinner"></div>';
    return Promise.all([
        fetchJson(API + '/api/executive-narrative', { force: force }),
        // The guardian's findings make the briefing smarter — but the briefing
        // must still render if anomaly detection is unavailable.
        fetchJson(API + '/api/anomalies', { force: force }).catch(function () { return { anomalies: [], count: 0 }; })
    ])
        .then(function (results) { renderBriefing(results[0], results[1]); tabLoaded.briefing = true; })
        .catch(function (err) {
            body.innerHTML = '<div class="report-card"><div class="report-card-body"><div class="report-card-title">' + escapeHtml(err.message) + '</div></div></div>';
            tabLoaded.briefing = true;
        });
}

function renderBriefing(d, guardian) {
    var h = d.headline || {};
    function kpi(label, value, delta, dir, isPct) {
        var dtxt = (delta >= 0 ? '+' : '') + (isPct ? pctVal(delta) + ' pp' : formatFull(delta));
        return '<div class="brief-kpi"><div class="k-label">' + label + '</div>' +
            '<div class="k-value">' + (isPct ? pctVal(value) : formatFull(value)) + '</div>' +
            '<div class="k-delta ' + dir + '">' + briefArrow(dir) + ' ' + dtxt + ' ' + tr('vs prior year') + '</div></div>';
    }
    var gmDir = h.gm_pct_delta > 0.05 ? 'up' : (h.gm_pct_delta < -0.05 ? 'down' : 'flat');
    var kpis = '<div class="brief-kpis">' +
        kpi(tr('Net income'), h.net_income, h.net_income_delta, h.net_income_dir, false) +
        kpi(tr('Net sales'), h.net_sales, h.net_sales_delta, h.net_sales_dir, false) +
        kpi(tr('Operating profit'), h.operating_profit, h.operating_profit_delta, h.operating_profit_dir, false) +
        kpi(tr('Gross margin %'), h.gm_pct, h.gm_pct_delta, gmDir, true) +
        '</div>';

    var changes = (d.topChanges || []).map(function (c) {
        var verb = c.direction === 'up' ? tr('improved by') : tr('declined by');
        var cls = c.direction === 'up' ? 'delta-up' : 'delta-down';
        return '<li><span class="sev ' + (c.direction === 'up' ? 'medium' : 'high') + '">' + briefArrow(c.direction) +
            '</span><span class="' + cls + '">' + escapeHtml(tr(String(c.label))) + ' — ' + verb + ' ' +
            formatFull(Math.abs(c.delta_operating_profit)) + ' ' + tr('operating profit') + '</span></li>';
    }).join('');
    if (!changes) changes = '<li>' + tr('No material changes versus prior year.') + '</li>';

    var risks = (d.risks || []).map(function (r) {
        var sevLabel = tr(r.severity === 'high' ? 'High' : 'Medium');
        return '<li><span class="sev ' + r.severity + '">' + sevLabel + '</span>' + briefRiskText(r) + '</li>';
    }).join('');
    if (!risks) risks = '<li>' + tr('No material risks flagged.') + '</li>';

    var actions = (d.risks || []).map(function (r) { return '<li>' + briefActionText(r) + '</li>'; }).join('');
    if (!actions) actions = '<li>' + tr('Maintain the current plan; monitor monthly.') + '</li>';

    // What the guardian flagged — top alerts from the anomaly engine.
    var alerts = (guardian && guardian.anomalies) || [];
    var guardianSection = '';
    if (alerts.length) {
        var topAlerts = alerts.slice(0, 4).map(function (a) {
            return '<li><span class="sev ' + a.severity + '">' + tr(a.severity === 'high' ? 'High' : 'Medium') +
                '</span>' + guardianText(a) + '</li>';
        }).join('');
        guardianSection = '<div class="brief-section"><h3>' + tr('What the guardian flagged') +
            ' (' + alerts.length + ')</h3><ul class="brief-list">' + topAlerts + '</ul></div>';
    }

    var sc = d.sourceConfidence || {};
    var scBadge = '<span class="status-badge ' + (sc.overall === 'WARN' ? 'warn' : 'ok') + '">' +
        (sc.overall === 'WARN' ? tr('Review') : tr('Healthy')) + '</span>';
    var conf = '<div class="brief-confidence">' + scBadge + ' ' + tr('Lineage coverage') + ': ' + pctVal(sc.lineage_coverage_pct) +
        ' · ' + (sc.warnings || 0) + ' ' + tr('Warnings') + ' · ' + loc(Number(sc.total_rows || 0).toLocaleString('en-US')) + ' ' + tr('rows') + '</div>';

    el('briefingBody').innerHTML = kpis +
        '<div class="brief-section"><h3>' + tr('What changed') + '</h3><ul class="brief-list">' + changes + '</ul></div>' +
        guardianSection +
        '<div class="brief-section"><h3>' + tr('Top risks') + '</h3><ul class="brief-list">' + risks + '</ul></div>' +
        '<div class="brief-section"><h3>' + tr('Recommended actions') + '</h3><ul class="brief-list">' + actions + '</ul></div>' +
        '<div class="brief-section"><h3>' + tr('Source confidence') + '</h3>' + conf + '</div>';
}

var knowledgeWired = false;
var wikiTimer = null;

function renderMarkdown(md) {
    function inline(s) {
        s = escapeHtml(s);   // escape first; the replacements below run on safe text
        s = s.replace(/\[\[([^\]]+)\]\]/g, function (_, t) {
            var parts = t.split('|');
            var id = parts[0].trim();
            var label = (parts[1] || parts[0]).trim();
            return '<a class="wikilink" data-note="' + id + '">' + label + '</a>';
        });
        s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
        return s;
    }
    var html = '';
    var inList = false;
    String(md || '').split('\n').forEach(function (raw) {
        var line = raw.replace(/\s+$/, '');
        var h = line.match(/^(#{1,3})\s+(.*)$/);
        var li = line.match(/^\s*[-*]\s+(.*)$/);
        if (h) {
            if (inList) { html += '</ul>'; inList = false; }
            html += '<h' + h[1].length + '>' + inline(h[2]) + '</h' + h[1].length + '>';
        } else if (li) {
            if (!inList) { html += '<ul>'; inList = true; }
            html += '<li>' + inline(li[1]) + '</li>';
        } else if (line.trim() === '') {
            if (inList) { html += '</ul>'; inList = false; }
        } else {
            if (inList) { html += '</ul>'; inList = false; }
            html += '<p>' + inline(line) + '</p>';
        }
    });
    if (inList) html += '</ul>';
    return html;
}

function loadKnowledge() {
    if (!knowledgeWired) {
        knowledgeWired = true;
        el('wikiSearch').addEventListener('input', function () {
            if (wikiTimer) window.clearTimeout(wikiTimer);
            wikiTimer = window.setTimeout(runWikiSearch, 250);
        });
        el('wikiResults').innerHTML = '<div class="wiki-empty">' + tr('Type to search the knowledge base.') + '</div>';
        el('wikiNote').innerHTML = '<div class="wiki-empty">' + tr('Select a note to read it here.') + '</div>';
    }
    tabLoaded.knowledge = true;
    return Promise.resolve();
}

function runWikiSearch() {
    var q = el('wikiSearch').value.trim();
    var resultsEl = el('wikiResults');
    if (!q) { resultsEl.innerHTML = '<div class="wiki-empty">' + tr('Type to search the knowledge base.') + '</div>'; return; }
    resultsEl.innerHTML = '<div class="loading-spinner"></div>';
    fetchJson(API + '/api/wiki/search?q=' + encodeURIComponent(q) + '&limit=15', { force: true })
        .then(function (d) {
            var hits = d.matches || [];
            if (!hits.length) { resultsEl.innerHTML = '<div class="wiki-empty">' + tr('No notes match.') + '</div>'; return; }
            resultsEl.innerHTML = hits.map(function (h) {
                var tags = (h.tags || []).map(function (t) { return '<span class="wiki-tag">' + escapeHtml(t) + '</span>'; }).join('');
                return '<button class="wiki-hit" type="button" data-note="' + escapeHtml(h.note) + '">' +
                    '<div class="h-title">' + escapeHtml(h.title) + '</div>' +
                    '<div class="h-snip">' + escapeHtml(h.snippet || '') + '</div>' +
                    '<div class="h-tags">' + tags + '</div></button>';
            }).join('');
            resultsEl.querySelectorAll('.wiki-hit').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    resultsEl.querySelectorAll('.wiki-hit').forEach(function (b) { b.classList.remove('active'); });
                    btn.classList.add('active');
                    viewNote(btn.dataset.note);
                });
            });
            viewNote(hits[0].note);
            var first = resultsEl.querySelector('.wiki-hit');
            if (first) first.classList.add('active');
        })
        .catch(function (err) { resultsEl.innerHTML = '<div class="wiki-empty">' + escapeHtml(err.message) + '</div>'; });
}

function viewNote(id) {
    var noteEl = el('wikiNote');
    noteEl.innerHTML = '<div class="loading-spinner"></div>';
    fetchJson(API + '/api/wiki/note?id=' + encodeURIComponent(id), { force: true })
        .then(function (d) {
            noteEl.innerHTML = renderMarkdown(d.body);
            noteEl.querySelectorAll('a.wikilink').forEach(function (a) {
                a.addEventListener('click', function () { viewNote(a.dataset.note); });
            });
        })
        .catch(function (err) { noteEl.innerHTML = '<div class="wiki-empty">' + escapeHtml(err.message) + '</div>'; });
}

function updateGuardianBadge(count) {
    var badge = el('guardianBadge');
    if (!badge) return;
    if (count > 0) { badge.textContent = count; badge.hidden = false; }
    else { badge.hidden = true; }
}

function primeGuardianBadge() {
    // Passive guardian: surface the alert count on the nav without opening the tab.
    fetchJson(API + '/api/anomalies', { force: true })
        .then(function (d) { updateGuardianBadge(d.count || 0); })
        .catch(function () { /* badge stays hidden if detection is unavailable */ });
}

function guardianMetricLabel(metric) {
    var map = {
        operating_expense: tr('Operating expense'), net_sales: tr('Net sales'),
        operating_profit: tr('Operating profit'), gross_margin_pct: tr('Gross margin %')
    };
    return map[metric] || metric;
}

function guardianText(a) {
    var label = escapeHtml(tr(String(a.label || '')));
    var d = a.detail || {};
    if (a.type === 'first_negative_margin') {
        return label + ' — ' + tr('operating profit turned negative for the first time after') + ' ' +
            (d.positive_years || 0) + ' ' + tr('profitable years') + ' (' + formatFull(a.value) + ')';
    }
    if (a.type === 'margin_erosion') {
        return label + ' — ' + tr('gross margin fell') + ' ' + pctVal(d.drop_pp) + ' pp (' +
            pctVal(a.baseline) + ' → ' + pctVal(a.value) + ')';
    }
    if (a.type === 'customer_churn') {
        return label + ' — ' + tr('purchases collapsed') + ' (' + tr('avg') + ' ' +
            formatFull(a.baseline) + ' → ' + formatFull(a.value) + ')';
    }
    if (a.type === 'expense_spike') {
        return label + ' — ' + tr('operating expense surged') + ' ' + pctVal(a.delta_pct) +
            ' (' + tr('revenue grew') + ' ' + pctVal(d.revenue_growth_pct) + ')';
    }
    if (a.type === 'period_spike') {
        var pp = ('0' + a.period).slice(-2);
        return 'P' + pp + ' — ' + guardianMetricLabel(a.metric) + ' ' + tr('spiked vs the year average') +
            ' (' + pctVal(a.delta_pct) + ', z=' + loc(String(d.z_score)) + ')';
    }
    return label;
}

function guardianTrace(a) {
    var where = a.dimension ? (a.dimension + '=' + a.label) : (a.period ? ('P' + ('0' + a.period).slice(-2)) : '');
    return 'FY' + a.year + (where ? ' · ' + where : '') + ' · ' + a.metric;
}

function loadGuardian(force) {
    var list = el('guardianList');
    el('guardianSummary').innerHTML = '';
    list.innerHTML = '<div class="loading-spinner"></div>';
    return fetchJson(API + '/api/anomalies', { force: force })
        .then(function (d) { renderGuardian(d); tabLoaded.guardian = true; })
        .catch(function (err) {
            list.innerHTML = '<div class="wiki-empty">' + escapeHtml(err.message) + '</div>';
            tabLoaded.guardian = true;
        });
}

function renderGuardian(d) {
    var anomalies = d.anomalies || [];
    var high = (d.by_severity && d.by_severity.high) || 0;
    var medium = (d.by_severity && d.by_severity.medium) || 0;
    updateGuardianBadge(d.count || 0);
    el('guardianSummary').innerHTML =
        '<div class="health-card ' + (d.count ? 'is-warn' : 'is-ok') + '"><div class="health-num">' + (d.count || 0) + '</div><div class="health-lbl">' + tr('Alerts') + '</div></div>' +
        '<div class="health-card ' + (high ? 'is-warn' : 'is-ok') + '"><div class="health-num">' + high + '</div><div class="health-lbl">' + tr('High') + '</div></div>' +
        '<div class="health-card"><div class="health-num">' + medium + '</div><div class="health-lbl">' + tr('Medium') + '</div></div>';
    if (!anomalies.length) {
        el('guardianList').innerHTML = '<div class="guardian-clear">✓ ' + tr('All clear — no anomalies detected.') + '</div>';
        return;
    }
    el('guardianList').innerHTML = '<div class="guardian-list">' + anomalies.map(function (a) {
        return '<div class="alert-card sev-' + a.severity + '">' +
            '<span class="a-sev ' + a.severity + '">' + tr(a.severity === 'high' ? 'High' : 'Medium') + '</span>' +
            '<div class="a-body"><div class="a-text">' + guardianText(a) + '</div>' +
            '<div class="a-trace">' + escapeHtml(guardianTrace(a)) + '</div></div></div>';
    }).join('') + '</div>';
}

var askWired = false;
var ASK_EXAMPLES = [
    'net sales by region',
    'compare Africa vs Asia Pacific net sales',
    'gross margin first quarter',
    'operating expense last year',
    'net income by product'
];

function loadAsk() {
    if (!askWired) {
        askWired = true;
        el('askBtn').addEventListener('click', runAsk);
        el('askInput').addEventListener('keydown', function (e) { if (e.key === 'Enter') runAsk(); });
        el('askExamples').innerHTML = ASK_EXAMPLES.map(function (q) {
            return '<button class="ask-chip" type="button" data-q="' + escapeHtml(q) + '">' + escapeHtml(q) + '</button>';
        }).join('');
        el('askExamples').querySelectorAll('.ask-chip').forEach(function (chip) {
            chip.addEventListener('click', function () { el('askInput').value = chip.dataset.q; runAsk(); });
        });
    }
    tabLoaded.ask = true;
    return Promise.resolve();
}

function runAsk() {
    var q = el('askInput').value.trim();
    if (!q) return;
    var interp = el('askInterpretation');
    var card = el('askResultCard');
    interp.hidden = false;
    interp.innerHTML = '<div class="loading-spinner"></div>';
    card.style.display = 'none';
    fetchJson(API + '/api/nl-query?q=' + encodeURIComponent(q), { force: true })
        .then(function (d) { renderAsk(d); })
        .catch(function (err) {
            interp.hidden = false;
            interp.innerHTML = '<span class="ai-label">' + tr('Could not answer') + '</span>' + escapeHtml(err.message);
        });
}

function renderAsk(d) {
    var isAr = window.I18N && window.I18N.lang && window.I18N.lang() === 'ar';
    var interpretation = isAr ? (d.interpretation_ar || d.interpretation) : d.interpretation;
    el('askInterpretation').hidden = false;
    el('askInterpretation').innerHTML = '<span class="ai-label">' + tr('Understood as') + ':</span>' + escapeHtml(interpretation || '');

    var rows = d.rows || [];
    var card = el('askResultCard');
    el('askResultSub').textContent = (d.row_count || rows.length) + ' ' + tr('rows');
    var metricLabel = guardianMetricLabel(d.metric) || d.metric;
    var head = '<thead><tr><th>' + tr('Item') + '</th><th>' + escapeHtml(metricLabel) + '</th></tr></thead>';
    var body = '<tbody>' + rows.map(function (r) {
        var label = r.label === 'Total' ? tr('Total') : escapeHtml(tr(String(r.label)));
        return '<tr><td>' + label + '</td><td>' + formatFull(r.value) + '</td></tr>';
    }).join('') + '</tbody>';
    el('askTable').innerHTML = head + body;
    card.style.display = '';
}

function loadActiveTab(force) {
    setStatus(true, tr('Querying SQLite'));
    var loader = {
        overview: loadOverview,
        regional: loadRegional,
        product: loadProduct,
        drilldown: loadDrilldown,
        scenario: loadScenario,
        trends: loadTrends,
        portfolio: loadPortfolio,
        reports: loadReports,
        health: loadHealth,
        briefing: loadBriefing,
        knowledge: loadKnowledge,
        guardian: loadGuardian,
        ask: loadAsk
    }[activeTab];
    return Promise.resolve(loader(force)).then(function () {
        setStatus(true, tr('Live SQLite'));
    }).catch(function () {
        // The loader already surfaced the error.
    });
}

function updatePageHeading(tabName) {
    el('pageTitle').textContent = (window.I18N && window.I18N.t('page.' + tabName + '.title')) || tr(pageMeta[tabName][0]);
    el('pageSubtitle').textContent = (window.I18N && window.I18N.t('page.' + tabName + '.sub')) || tr(pageMeta[tabName][1]);
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
    updatePageHeading(tabName);
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

    if (tabName === 'reports') {
        yearSelect.disabled = true;
        versionSelect.disabled = true;
        el('globalRegion').disabled = true;
        el('globalCountry').disabled = true;
        el('applyFiltersBtn').style.display = 'none';
        el('resetFiltersBtn').style.display = 'none';
        return;
    }

    var returningFromExecutive = yearSelect.disabled;
    yearSelect.disabled = false;
    versionSelect.disabled = false;
    el('globalRegion').disabled = false;
    el('globalCountry').disabled = false;
    el('applyFiltersBtn').style.display = '';
    el('resetFiltersBtn').style.display = '';
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
    el('appAlertRetry').addEventListener('click', function () { window.location.reload(); });
    el('globalRegion').addEventListener('change', refreshCountryOptions);
    el('regMetric').addEventListener('change', function () { loadRegional(false); });
    el('productBtn').addEventListener('click', renderProduct);
    el('prodMetric').addEventListener('change', renderProduct);
    el('ddBtn').addEventListener('click', function () { loadDrilldown(true); });
    el('scenMetric').addEventListener('change', renderScenario);
    el('ovYear').addEventListener('change', function () { loadOverview(true); });
    document.querySelectorAll('[data-export-table]').forEach(function (button) {
        button.addEventListener('click', function () {
            exportCSV(button.dataset.exportTable, button.dataset.exportName);
        });
    });
    el('reportCloseBtn').addEventListener('click', closeReportView);
}

function configureCharts() {
    if (!window.Chart) throw new Error('Chart.js did not load');
    Chart.defaults.color = '#66758a';
    Chart.defaults.borderColor = '#edf1f6';
    Chart.defaults.font.family = 'Cairo, system-ui, -apple-system, sans-serif';
    Chart.defaults.animation.duration = 420;
}

function bootstrap() {
    setStatus(true, tr('Connecting'));
    configureCharts();
    bindEvents();
    updatePageHeading(activeTab);
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
        if (status.backend === 'sqlite-live') {
            hideAlert();
        } else {
            showAlert(tr('Running in limited mode'),
                tr('The live database is not connected, so the dashboard is showing only saved summary data. Some sections may be empty until the database is set up.'));
        }
        setStatus(status.database === 'connected', status.backend === 'sqlite-live' ? tr('Live SQLite') : tr('Fallback cache'));
        primeGuardianBadge();
        return loadOverview(false);
    }).catch(function () {
        setStatus(false, tr('Connection failed'));
        showAlert(tr('We couldn’t load the dashboard data'),
            tr('The data service may still be starting up, or it has not been set up yet. Wait a moment and click Try again. If this is a fresh setup, the database needs to be created first — see the Getting Started guide.'));
    });
}

bootstrap();
})();
