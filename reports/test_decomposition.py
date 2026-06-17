"""
Test for reports.decomposition — volume/price revenue decomposition.
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from reports.decomposition import decompose, auto_years


def test_decompose_group_level():
    """Decomposition at group level returns summary row."""
    # Use the synthetic database
    db_path = Path(__file__).resolve().parent.parent / "pl_detail.db"
    conn = sqlite3.connect(str(db_path))
    try:
        columns, rows, extra = decompose(conn, 2024, 2025)
        assert "dimension_label" in columns
        assert "total_change" in columns
        assert "price_effect" in columns
        assert "volume_effect" in columns
        assert extra["base_year"] == 2024
        assert extra["compare_year"] == 2025
        assert "total_change" in extra
        assert "price_pct" in extra
        assert "volume_pct" in extra
        # At group level, should have exactly 1 row
        assert len(rows) == 1
        assert rows[0]["dimension_label"] == "Group"
        # Price + volume should approximately equal total
        total = rows[0]["total_change"]
        price = rows[0]["price_effect"]
        volume = rows[0]["volume_effect"]
        assert abs(total - (price + volume)) < 1.0  # rounding tolerance
    finally:
        conn.close()


def test_decompose_by_region():
    """Decomposition by region returns per-region rows."""
    db_path = Path(__file__).resolve().parent.parent / "pl_detail.db"
    conn = sqlite3.connect(str(db_path))
    try:
        columns, rows, extra = decompose(
            conn, 2024, 2025, dimension_col="region_desc")
        assert len(rows) > 0
        for r in rows:
            assert isinstance(r["dimension_label"], str)
            assert r["dimension_label"] != ""
        # Price + volume should approximately equal total for each row
        for r in rows:
            total = r["total_change"]
            price = r["price_effect"]
            volume = r["volume_effect"]
            assert abs(total - (price + volume)) < 2.0
    finally:
        conn.close()


def test_decompose_by_product():
    """Decomposition by product group."""
    db_path = Path(__file__).resolve().parent.parent / "pl_detail.db"
    conn = sqlite3.connect(str(db_path))
    try:
        columns, rows, extra = decompose(
            conn, 2024, 2025, dimension_col="m_group_desc")
        assert len(rows) > 0
        # Verify all columns present
        for c in ["base_avg_price", "curr_avg_price", "base_volume",
                  "curr_volume", "total_change", "price_effect", "volume_effect"]:
            assert c in columns
    finally:
        conn.close()


def test_auto_years():
    """auto_years returns last two Actual years."""
    db_path = Path(__file__).resolve().parent.parent / "pl_detail.db"
    conn = sqlite3.connect(str(db_path))
    try:
        base, comp = auto_years(conn)
        assert base < comp
        assert isinstance(base, int)
        assert isinstance(comp, int)
    finally:
        conn.close()


def test_decompose_zero_volume_handled():
    """Products with zero volume don't crash the division."""
    db_path = Path(__file__).resolve().parent.parent / "pl_detail.db"
    conn = sqlite3.connect(str(db_path))
    try:
        # Should not raise even if some products have zero volume
        columns, rows, extra = decompose(conn, 2025, 2026)
        assert "price_effect" in columns
    finally:
        conn.close()


if __name__ == "__main__":
    test_decompose_group_level()
    test_decompose_by_region()
    test_decompose_by_product()
    test_auto_years()
    test_decompose_zero_volume_handled()
    print("All decomposition tests passed.")
