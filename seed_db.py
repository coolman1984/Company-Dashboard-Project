"""
seed_db.py - build a realistic *synthetic* pl_detail.db for development, tests and CI.

The production database is built from a proprietary Excel workbook on Windows
(see ingest_sheet1.py), which is not available in most environments. This script
generates a deterministic, self-contained SQLite database with the exact schema
the server expects, so the dashboard and smoke tests run anywhere with nothing
but Python's standard library.

Usage:
    python3 seed_db.py            # writes pl_detail.db next to this script
    python3 seed_db.py --force    # overwrite an existing database without asking

The generated data honours the conventions the app depends on:
  * Versions: Actual (realised), T06 (bridge P06), T07 (outlook P07-P12)
  * FY2022-FY2025 are full-year Actual (P01-P12)
  * FY2026 = Actual P01-P05 + T06 P06 + T07 P07-P12
  * period REAL = year + period_number / 1000
  * Every region/period combination carries positive net sales
"""
import argparse
import os
import random
import sqlite3
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "pl_detail.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

# Deterministic output so tests and CI are reproducible.
RNG = random.Random(20260614)

YEARS = [2022, 2023, 2024, 2025, 2026]
CURRENT_YEAR = 2026

# Column order must match schema.sql / pl_detail exactly.
COLUMNS = [
    "class", "region_desc", "country_name", "customer_name", "m_group_desc",
    "year", "class_code", "version", "product_number", "sender_ba",
    "customer_code", "country_code", "profit_center", "valuation_class", "period",
    "currency", "qty_gross", "qty_return", "qty_net", "s_rrp",
    "reference_price", "dealer_discount", "s_base_margin", "s_contract_margin",
    "s_additional_margin", "s_special_margin", "s_gross_sales", "s_gross_sales_amt",
    "s_other_sales", "s_oth_sales_tax_inc", "s_internal_sales_amt", "s_return_amt",
    "s_return_amt_alt", "ref_sales", "s_ifc", "s_fob_sales_amt", "sales_deduction",
    "s_sales_allowance", "s_rebate", "s_cash_discount", "s_price_protection",
    "s_coop", "s_sale_deduction_tax", "net_sales", "cost_of_goods_sold",
    "material_cost", "gross_margin", "operating_expense", "sales_expense",
    "operating_profit", "profit_before_tax", "corporate_tax", "corp_tax",
    "net_income", "sa_hq_sales_comm", "sa_corp_promotion", "royalty",
    "sa_royalty_3rd_party", "sa_royalty_hq",
]

# region -> (relative scale, [(country_name, country_code), ...])
REGIONS = {
    "Africa":        (0.12, [("South Africa", "ZA"), ("Nigeria", "NG"), ("Kenya", "KE")]),
    "Americas":      (0.30, [("United States", "US"), ("Brazil", "BR"), ("Canada", "CA")]),
    "Asia Pacific":  (0.34, [("China", "CN"), ("Japan", "JP"), ("Australia", "AU")]),
    "Europe":        (0.18, [("Germany", "DE"), ("France", "FR"), ("United Kingdom", "GB")]),
    "Middle East":   (0.06, [("UAE", "AE"), ("Saudi Arabia", "SA")]),
}

_AR_REGIONS = {
    "أفريقيا":             (0.12, [("جنوب أفريقيا", "ZA"), ("نيجيريا", "NG"), ("كينيا", "KE")]),
    "الأمريكتان":          (0.30, [("الولايات المتحدة", "US"), ("البرازيل", "BR"), ("كندا", "CA")]),
    "آسيا والمحيط الهادئ": (0.34, [("الصين", "CN"), ("اليابان", "JP"), ("أستراليا", "AU")]),
    "أوروبا":              (0.18, [("ألمانيا", "DE"), ("فرنسا", "FR"), ("المملكة المتحدة", "GB")]),
    "الشرق الأوسط":        (0.06, [("الإمارات", "AE"), ("السعودية", "SA")]),
}

# product group -> (relative scale, gross-margin rate, opex rate of sales)
# A couple of groups are deliberately thin / loss-making for portfolio realism.
PRODUCT_GROUPS = {
    "Industrial Drives":   (0.22, 0.34, 0.18),
    "Smart Sensors":       (0.16, 0.41, 0.20),
    "Power Systems":       (0.18, 0.29, 0.17),
    "Connectivity":        (0.12, 0.46, 0.22),
    "Automation Software": (0.10, 0.58, 0.30),
    "Robotics":            (0.09, 0.25, 0.24),
    "Legacy Controllers":  (0.05, 0.12, 0.16),   # thin margin
    "Field Services":      (0.04, 0.08, 0.14),   # loss-making
    "Spare Parts":         (0.04, 0.38, 0.12),
}

CLASSES = ["Premium", "Standard", "Value"]

_AR_PRODUCT_GROUPS = {
    "محركات صناعية":       (0.22, 0.34, 0.18),
    "مستشعرات ذكية":       (0.16, 0.41, 0.20),
    "أنظمة الطاقة":        (0.18, 0.29, 0.17),
    "الاتصالات":           (0.12, 0.46, 0.22),
    "برمجيات الأتمتة":     (0.10, 0.58, 0.30),
    "الروبوتات":           (0.09, 0.25, 0.24),
    "متحكمات قديمة":       (0.05, 0.12, 0.16),
    "الخدمات الميدانية":   (0.04, 0.08, 0.14),
    "قطع الغيار":          (0.04, 0.38, 0.12),
}

_AR_CLASSES = ["ممتاز", "قياسي", "اقتصادي"]


def coverage_for_year(year):
    """Return [(version, period_number), ...] for a given fiscal year."""
    if year < CURRENT_YEAR:
        return [("Actual", p) for p in range(1, 13)]
    # Current year: realised P01-P05, bridge P06, outlook P07-P12.
    points = [("Actual", p) for p in range(1, 6)]
    points.append(("T06", 6))
    points.extend([("T07", p) for p in range(7, 13)])
    return points


def growth_factor(year):
    """Mild compound growth across the horizon, anchored at FY2024 = 1.0."""
    return 1.0 + 0.06 * (year - 2024)


def seasonality(period_number):
    """Monthly seasonality multiplier (stronger H2, softer summer)."""
    curve = [0.92, 0.90, 0.98, 1.00, 1.02, 0.95,
             0.88, 0.90, 1.05, 1.08, 1.10, 1.22]
    return curve[period_number - 1]


def build_rows(locale="en"):
    regions = _AR_REGIONS if locale == "ar" else REGIONS
    product_groups = _AR_PRODUCT_GROUPS if locale == "ar" else PRODUCT_GROUPS
    classes = _AR_CLASSES if locale == "ar" else CLASSES
    customer_prefixes = {
        "أفريقيا": "عميل أفريقيا",
        "الأمريكتان": "عميل الأمريكتين",
        "آسيا والمحيط الهادئ": "عميل آسيا",
        "أوروبا": "عميل أوروبا",
        "الشرق الأوسط": "عميل الشرق الأوسط",
    } if locale == "ar" else {}
    rows = []
    for year in YEARS:
        gf = growth_factor(year)
        for version, period_number in coverage_for_year(year):
            period = round(year + period_number / 1000.0, 3)
            season = seasonality(period_number)
            for region, (region_scale, countries) in regions.items():
                for country_name, country_code in countries:
                    # Spread a region's weight across its countries.
                    country_scale = region_scale / len(countries)
                    for pg_idx, (pgroup, (pg_scale, gm_rate, opex_rate)) in enumerate(product_groups.items()):
                        # Base monthly net sales for this cell, with noise.
                        base = 9_500_000 * gf * season * country_scale * pg_scale
                        noise = RNG.uniform(0.82, 1.18)
                        net_sales = round(base * noise, 2)
                        if net_sales <= 0:
                            net_sales = round(abs(base) * 0.5 + 1000, 2)

                        gm = round(net_sales * (gm_rate + RNG.uniform(-0.04, 0.04)), 2)
                        cogs = round(net_sales - gm, 2)
                        material_cost = round(cogs * 0.72, 2)
                        opex = round(net_sales * (opex_rate + RNG.uniform(-0.03, 0.03)), 2)
                        sales_expense = round(opex * 0.45, 2)
                        operating_profit = round(gm - opex, 2)
                        royalty = round(net_sales * 0.015, 2)
                        pbt = round(operating_profit - royalty, 2)
                        corporate_tax = round(max(pbt, 0) * 0.22, 2)
                        net_income = round(pbt - corporate_tax, 2)

                        gross_sales = round(net_sales * 1.18, 2)
                        returns = round(net_sales * 0.04, 2)
                        sales_deduction = round(net_sales * 0.09, 2)

                        # Cycle customers, classes and products for variety.
                        customer_idx = (pg_idx + period_number) % 3 + 1
                        if locale == "ar":
                            prefix = customer_prefixes.get(region, "عميل")
                            customer_name = f"{prefix} {customer_idx}"
                        else:
                            customer_name = f"{region.split()[0]} Customer {customer_idx}"
                        customer_code = f"{country_code}{customer_idx:03d}"
                        cls = classes[pg_idx % len(classes)]
                        class_code = f"C{pg_idx % len(classes) + 1}"
                        product_number = f"{country_code}-{pg_idx + 1:02d}-{customer_idx}"
                        qty_net = round(net_sales / 1250.0, 1)

                        record = {
                            "class": cls,
                            "region_desc": region,
                            "country_name": country_name,
                            "customer_name": customer_name,
                            "m_group_desc": pgroup,
                            "year": year,
                            "class_code": class_code,
                            "version": version,
                            "product_number": product_number,
                            "sender_ba": "BA10",
                            "customer_code": customer_code,
                            "country_code": country_code,
                            "profit_center": f"PC{pg_idx + 1:02d}",
                            "valuation_class": 7920,
                            "period": period,
                            "currency": "USD",
                            "qty_gross": round(qty_net * 1.05, 1),
                            "qty_return": round(qty_net * 0.05, 1),
                            "qty_net": qty_net,
                            "s_rrp": round(net_sales * 1.30, 2),
                            "reference_price": round(net_sales * 1.25, 2),
                            "dealer_discount": round(net_sales * 0.10, 2),
                            "s_base_margin": gm,
                            "s_contract_margin": round(gm * 0.6, 2),
                            "s_additional_margin": round(gm * 0.2, 2),
                            "s_special_margin": round(gm * 0.1, 2),
                            "s_gross_sales": gross_sales,
                            "s_gross_sales_amt": gross_sales,
                            "s_other_sales": round(net_sales * 0.02, 2),
                            "s_oth_sales_tax_inc": round(net_sales * 0.01, 2),
                            "s_internal_sales_amt": round(net_sales * 0.03, 2),
                            "s_return_amt": returns,
                            "s_return_amt_alt": returns,
                            "ref_sales": round(net_sales * 1.02, 2),
                            "s_ifc": round(net_sales * 0.005, 2),
                            "s_fob_sales_amt": round(net_sales * 0.98, 2),
                            "sales_deduction": sales_deduction,
                            "s_sales_allowance": round(sales_deduction * 0.3, 2),
                            "s_rebate": round(sales_deduction * 0.4, 2),
                            "s_cash_discount": round(sales_deduction * 0.1, 2),
                            "s_price_protection": round(sales_deduction * 0.1, 2),
                            "s_coop": round(sales_deduction * 0.1, 2),
                            "s_sale_deduction_tax": round(sales_deduction * 0.05, 2),
                            "net_sales": net_sales,
                            "cost_of_goods_sold": cogs,
                            "material_cost": material_cost,
                            "gross_margin": gm,
                            "operating_expense": opex,
                            "sales_expense": sales_expense,
                            "operating_profit": operating_profit,
                            "profit_before_tax": pbt,
                            "corporate_tax": corporate_tax,
                            "corp_tax": corporate_tax,
                            "net_income": net_income,
                            "sa_hq_sales_comm": round(net_sales * 0.012, 2),
                            "sa_corp_promotion": round(net_sales * 0.008, 2),
                            "royalty": royalty,
                            "sa_royalty_3rd_party": round(royalty * 0.5, 2),
                            "sa_royalty_hq": round(royalty * 0.5, 2),
                        }
                        rows.append(tuple(record[col] for col in COLUMNS))
    return rows


def apply_schema(conn):
    with open(SCHEMA_PATH, "r", encoding="utf-8") as handle:
        conn.executescript(handle.read())


def write_synthetic_lineage(conn, row_count, locale="en"):
    """Attach synthetic-source lineage to every seeded ledger row.

    The seed database is not real client data, but treating it like an imported
    source proves the audit/provenance tables work end-to-end in demos and tests.
    """
    run_id = "seed-synthetic-ar" if locale == "ar" else "seed-synthetic-en"
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    filename = f"synthetic-pl-detail-{locale}.generated"
    conn.execute(
        """
        INSERT INTO import_run (
            import_run_id, client_id, started_at, source, mapping_name,
            mapping_path, mapping_sha256, row_count, status, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, "synthetic-demo", now, "seed_db.py", "synthetic-seed", "seed_db.py", None,
         row_count, "success", "Deterministic synthetic development/demo data."),
    )
    cur = conn.execute(
        """
        INSERT INTO source_file (import_run_id, filename, relpath, sha256, extractor, document_type)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (run_id, filename, filename, None, "seed_db", "synthetic-ledger"),
    )
    source_file_id = cur.lastrowid
    conn.executemany(
        """
        INSERT INTO row_lineage (
            ledger_rowid, import_run_id, source_file_id, sheet_name,
            source_row, raw_file, source_reference
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (rowid, run_id, source_file_id, "pl_detail", rowid, filename, f"{filename}:row:{rowid}")
            for (rowid,) in conn.execute("SELECT rowid FROM pl_detail ORDER BY rowid")
        ],
    )


def main():
    parser = argparse.ArgumentParser(description="Generate a synthetic pl_detail.db.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing database.")
    parser.add_argument("--locale", choices=["en", "ar"], default="en",
                        help="Dimension language: en (English) or ar (Arabic). Default: en.")
    args = parser.parse_args()

    if os.path.exists(DB_PATH) and not args.force:
        reply = input(f"{DB_PATH} exists. Overwrite? [y/N] ").strip().lower()
        if reply not in ("y", "yes"):
            print("Aborted.")
            sys.exit(0)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    if not os.path.exists(SCHEMA_PATH):
        print(f"ERROR: schema.sql not found at {SCHEMA_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    try:
        apply_schema(conn)
        rows = build_rows(locale=args.locale)
        placeholders = ", ".join("?" for _ in COLUMNS)
        col_names = ", ".join(f'"{c}"' for c in COLUMNS)
        conn.executemany(
            f"INSERT INTO pl_detail ({col_names}) VALUES ({placeholders})", rows
        )
        write_synthetic_lineage(conn, len(rows), locale=args.locale)
        conn.commit()

        total = conn.execute("SELECT COUNT(*) FROM pl_detail").fetchone()[0]
        years = [r[0] for r in conn.execute("SELECT DISTINCT year FROM pl_detail ORDER BY year")]
        regions = [r[0] for r in conn.execute("SELECT DISTINCT region_desc FROM pl_detail ORDER BY region_desc")]
        print(f"Seeded {total:,} rows into {DB_PATH}")
        print(f"  Years   : {years}")
        print(f"  Regions : {regions}")
        for year in years:
            cov = conn.execute(
                "SELECT version, COUNT(DISTINCT period) FROM pl_detail WHERE year = ? GROUP BY version ORDER BY version",
                (year,),
            ).fetchall()
            print(f"  FY{year}  : " + ", ".join(f"{v} x{c}" for v, c in cov))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
