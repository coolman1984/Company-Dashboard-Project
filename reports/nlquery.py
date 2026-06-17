"""
nlquery.py - deterministic, offline natural-language querying over the ledger.

No LLM, no network: a transparent rule-based parser maps an Arabic or English
question to the project's existing query vocabulary (a metric, an optional
group-by dimension, entity filters, a year, and a quarter) and runs a
parameterised SQL query. It always echoes back *what it understood* so the user
can trust the answer — and because it's deterministic it is fully unit-tested.

It handles the core intents a finance manager actually asks:
  * "net sales by region"                         -> metric + group-by
  * "show me Africa sales in 2025"                -> metric + filter + year
  * "compare Africa vs Asia Pacific revenue"       -> two-entity comparison
  * "gross margin first quarter"                  -> metric + quarter
  * Arabic equivalents (مبيعات أفريقيا، قارن ... ، الربع الأول، السنة الماضية)

Entity names (regions, customers, …) are matched against the database's own
values, so it works in whichever language the data is in.

Usage:
    echo "net sales by region" | python3 -m reports.nlquery --eval-stdin
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys

from .outlook import PNUM, detect_years

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(BASE_DIR, "pl_detail.db")

# Fixed vocabulary (language-independent of the data): metric + dimension words.
METRIC_SYNONYMS = {
    "net_sales": ["net sales", "sales", "revenue", "turnover",
                  "صافي المبيعات", "المبيعات", "مبيعات", "الإيراد", "الايراد", "إيرادات"],
    "cost_of_goods_sold": ["cogs", "cost of goods", "cost of sales",
                           "تكلفة المبيعات", "تكلفة البضاعة", "التكلفة"],
    "gross_margin": ["gross margin", "gross profit", "margin",
                     "هامش الربح", "إجمالي الربح", "الهامش", "هامش"],
    "operating_expense": ["operating expense", "opex", "expenses",
                          "المصروفات التشغيلية", "المصروفات", "مصروفات"],
    "operating_profit": ["operating profit", "الربح التشغيلي"],
    "net_income": ["net income", "net profit", "earnings", "profit",
                   "صافي الدخل", "صافي الربح", "الأرباح", "ارباح", "الربح"],
}
# Order matters: check longer/more specific metrics before "profit"/"sales".
METRIC_ORDER = ["net_sales", "cost_of_goods_sold", "gross_margin",
                "operating_expense", "operating_profit", "net_income"]

DIM_SYNONYMS = {
    "region_desc": ["regions", "region", "منطقة", "المناطق", "مناطق", "إقليم"],
    "country_name": ["countries", "country", "دولة", "الدول", "دول", "بلد"],
    "m_group_desc": ["product group", "products", "product", "منتج", "المنتجات", "منتجات", "مجموعة"],
    "customer_name": ["customers", "customer", "client", "عميل", "العملاء", "عملاء", "زبون"],
}

QUARTERS = {
    (1, 2, 3): ["q1", "first quarter", "1st quarter", "الربع الأول", "الربع الاول"],
    (4, 5, 6): ["q2", "second quarter", "2nd quarter", "الربع الثاني"],
    (7, 8, 9): ["q3", "third quarter", "3rd quarter", "الربع الثالث"],
    (10, 11, 12): ["q4", "fourth quarter", "4th quarter", "last quarter",
                   "الربع الرابع", "الربع الأخير", "الربع الاخير"],
}

COMPARE_WORDS = ["compare", "vs", "versus", "against", "مقارنة", "قارن", "مقابل", "ضد"]


def build_vocab(conn):
    """Distinct entity values per dimension + the years present in the ledger."""
    vocab = {}
    for dim in DIM_SYNONYMS:
        rows = conn.execute(
            f"SELECT DISTINCT {dim} FROM pl_detail WHERE {dim} IS NOT NULL")
        vocab[dim] = [r[0] for r in rows]
    vocab["years"] = [r[0] for r in conn.execute(
        "SELECT DISTINCT year FROM pl_detail WHERE year IS NOT NULL ORDER BY year")]
    return vocab


def _find_metric(text):
    for metric in METRIC_ORDER:
        for syn in METRIC_SYNONYMS[metric]:
            if syn in text:
                return metric
    return "net_sales"


def _find_dimension(text):
    for dim, syns in DIM_SYNONYMS.items():
        for syn in syns:
            if syn in text:
                return dim
    return None


def _find_entities(text, vocab):
    """{dimension: [matched values]} for entity names present in the question."""
    found = {}
    for dim in DIM_SYNONYMS:
        matches = []
        for value in vocab.get(dim, []):
            if value and str(value).lower() in text:
                matches.append(value)
        if matches:
            found[dim] = matches
    return found


def _find_year(text, vocab, current):
    explicit = re.findall(r"\b(20\d{2})\b", text)
    if explicit:
        year = int(explicit[0])
        return year if not vocab or year in vocab.get("years", [year]) else year
    if any(w in text for w in ["last year", "prior year", "السنة الماضية", "العام الماضي", "السنة السابقة"]):
        return (current - 1) if current else None
    if any(w in text for w in ["this year", "current year", "السنة الحالية", "هذا العام", "العام الحالي"]):
        return current
    return None


def _find_quarter(text):
    for periods, syns in QUARTERS.items():
        if any(s in text for s in syns):
            return list(periods)
    return None


def parse(question, vocab, current):
    """Pure parser: question + vocab -> structured query dict (no DB access)."""
    text = " " + (question or "").lower().strip() + " "
    metric = _find_metric(text)
    dimension = _find_dimension(text)
    entities = _find_entities(text, vocab)
    year = _find_year(text, vocab, current)
    periods = _find_quarter(text)
    is_compare = any(w in text for w in COMPARE_WORDS)

    group_by = dimension
    filters = {}
    # A comparison (or several entities of one dimension) groups by that dimension
    # and restricts to the named values.
    for dim, values in entities.items():
        if (is_compare or len(values) >= 2) and group_by is None:
            group_by = dim
        if group_by == dim:
            filters[dim] = values
        else:
            filters[dim] = values
    # If grouping by a dimension we also filtered to specific values, keep the
    # filter; otherwise a lone entity is just a filter (no grouping).
    return {
        "metric": metric,
        "group_by": group_by,
        "filters": filters,
        "year": year if year is not None else current,
        "periods": periods,
        "compare": is_compare,
    }


_METRIC_LABEL = {
    "net_sales": ("Net sales", "صافي المبيعات"),
    "cost_of_goods_sold": ("COGS", "تكلفة المبيعات"),
    "gross_margin": ("Gross margin", "هامش الربح"),
    "operating_expense": ("Operating expense", "المصروفات التشغيلية"),
    "operating_profit": ("Operating profit", "الربح التشغيلي"),
    "net_income": ("Net income", "صافي الدخل"),
}
_DIM_LABEL = {
    "region_desc": ("region", "المنطقة"),
    "country_name": ("country", "الدولة"),
    "m_group_desc": ("product group", "مجموعة المنتج"),
    "customer_name": ("customer", "العميل"),
}
_QUARTER_LABEL = {1: "Q1", 4: "Q2", 7: "Q3", 10: "Q4"}


def _interpretation(q):
    m_en, m_ar = _METRIC_LABEL.get(q["metric"], (q["metric"], q["metric"]))
    en = m_en
    ar = m_ar
    if q["group_by"]:
        d_en, d_ar = _DIM_LABEL.get(q["group_by"], (q["group_by"], q["group_by"]))
        en += f" by {d_en}"
        ar += f" حسب {d_ar}"
    flat = [v for vals in q["filters"].values() for v in vals]
    if flat and q["group_by"] is None:
        en += " for " + ", ".join(map(str, flat))
        ar += " لـ " + "، ".join(map(str, flat))
    elif flat and q["group_by"]:
        en += " (" + ", ".join(map(str, flat)) + ")"
        ar += " (" + "، ".join(map(str, flat)) + ")"
    if q["periods"]:
        en += f" {_QUARTER_LABEL.get(q['periods'][0], '')}"
        ar += f" {_QUARTER_LABEL.get(q['periods'][0], '')}"
    if q["year"]:
        en += f" FY{q['year']}"
        ar += f" السنة المالية {q['year']}"
    return en.strip(), ar.strip()


def run(conn, question):
    current, _prior = detect_years(conn)
    vocab = build_vocab(conn)
    q = parse(question, vocab, current)

    where = ["year = ?"]
    params = [q["year"]]
    if q["periods"]:
        where.append(f"{PNUM} IN ({', '.join('?' for _ in q['periods'])})")
        params += q["periods"]
    for dim, values in q["filters"].items():
        where.append(f"{dim} IN ({', '.join('?' for _ in values)})")
        params += values

    metric = q["metric"]
    where_sql = " AND ".join(where)
    if q["group_by"]:
        sql = (f"SELECT COALESCE({q['group_by']}, 'Unassigned') AS label, "
               f"COALESCE(SUM({metric}), 0) AS value FROM pl_detail "
               f"WHERE {where_sql} GROUP BY {q['group_by']} "
               f"ORDER BY value DESC LIMIT 50")
        rows = [{"label": r[0], "value": r[1]} for r in conn.execute(sql, params)]
        columns = ["label", "value"]
    else:
        sql = f"SELECT COALESCE(SUM({metric}), 0) FROM pl_detail WHERE {where_sql}"
        total = conn.execute(sql, params).fetchone()[0]
        rows = [{"label": "Total", "value": total}]
        columns = ["label", "value"]

    en, ar = _interpretation(q)
    return {
        "question": question,
        "query": q,
        "columns": columns,
        "rows": rows,
        "metric": metric,
        "interpretation": en,
        "interpretation_ar": ar,
        "row_count": len(rows),
    }


def evaluate(db_path, question):
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"Database not found: {db_path}. Seed it or load client data first.")
    conn = sqlite3.connect(db_path)
    try:
        return run(conn, question)
    finally:
        conn.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline natural-language ledger query.")
    parser.add_argument("--db", default=DEFAULT_DB, help="Source database.")
    parser.add_argument("--query", default=None, help="The question (or use --eval-stdin).")
    parser.add_argument("--eval-stdin", action="store_true",
                        help="Read the question from stdin and print JSON.")
    args = parser.parse_args(argv)
    question = sys.stdin.read().strip() if args.eval_stdin else (args.query or "")
    try:
        print(json.dumps(evaluate(args.db, question), ensure_ascii=False))
    except FileNotFoundError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
