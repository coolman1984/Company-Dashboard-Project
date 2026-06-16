/*
 * test_i18n_coverage.js — verifies the Arabic deep-content translation (Stage 6.5b).
 *
 * The dashboard renders many strings dynamically in app.js; i18n.js translates
 * them (exact dictionary + regex rules + a " · " compositional split) and a
 * MutationObserver applies it live. We can't run a browser in CI, but
 * window.I18N.translateText is pure and exported — so we stub a minimal DOM,
 * load i18n.js, and assert that the EXACT strings app.js produces get
 * translated out of English when the UI is Arabic (and left untouched in
 * English mode). This makes 5b coverage measurable and guards against regressions.
 *
 * Run: node test_i18n_coverage.js
 */
'use strict';

// --- minimal browser stubs so the i18n.js IIFE can load under Node ----------
const store = { dashboardLang: 'ar', dashboardDigits: 'western' };
global.localStorage = {
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
};
const noopEl = { setAttribute() {}, getAttribute: () => 'rtl', textContent: '', addEventListener() {} };
global.document = {
    documentElement: noopEl,
    body: null,
    addEventListener() {},
    getElementById: () => null,
    createTreeWalker: () => ({ nextNode: () => null }),
};
global.window = {};

require('./i18n.js');
const I18N = global.window.I18N;

let failures = 0;
function check(name, cond) {
    if (cond) { console.log('  ok   ' + name); }
    else { console.log('  FAIL ' + name); failures++; }
}

// Exact strings app.js renders (constructed the way app.js builds them).
const GM_DROP = (3.2).toFixed(1);
const footerMulti = 'Top 8 groups by 2026 outlook revenue · 2 loss-making (1.2M revenue at risk) · '
    + '3 margin eroding · 1 below safe threshold';
const footerStable = 'Top 8 groups by 2026 outlook revenue · All 8 product groups profitable and stable';

const mustTranslate = [
    'Strong growth',
    'Growing but margin eroding',
    'Database query timed out',
    'Chart.js did not load',
    'Gross margin fell ' + GM_DROP + ' pp YoY. Review discount policy, channel mix, and COGS drivers urgently.',
    'Margin slipping 1.5 pp — monitor channel mix and discount exposure before it accelerates.',
    'Top 8 groups by 2026 outlook revenue',
    '2 loss-making (1.2M revenue at risk)',
    '3 margin eroding',
    '1 below safe threshold',
    'All 8 product groups profitable and stable',
    footerMulti,
    footerStable,
    'Year',                       // existing chrome coverage (regression)
];

console.log('Arabic mode — strings must change:');
for (const s of mustTranslate) {
    const out = I18N.translateText(s);
    check(JSON.stringify(s.slice(0, 48)), out !== s && /[؀-ۿ]/.test(out));
}

// The compositional footer must be FULLY translated (no English leakage).
console.log('Compositional footer — no English leakage:');
const leaks = ['groups by', 'loss-making', 'revenue at risk', 'margin eroding',
    'below safe threshold', 'profitable and stable'];
for (const f of [footerMulti, footerStable]) {
    const out = I18N.translateText(f);
    check('no-leak: ' + f.slice(0, 36), !leaks.some((w) => out.includes(w)));
}

// English mode — translateText must be a no-op.
console.log('English mode — strings unchanged:');
store.dashboardLang = 'en';
for (const s of ['Strong growth', footerMulti]) {
    check('passthrough: ' + s.slice(0, 36), I18N.translateText(s) === s);
}
store.dashboardLang = 'ar';

if (failures) { console.log('\n' + failures + ' i18n coverage check(s) FAILED.'); process.exit(1); }
console.log('\nAll i18n coverage checks passed.');
