# -*- coding: utf-8 -*-
"""db/duckdb_manager.py 测试：上传 CSV/XLSX、查询、聚合、会话隔离与只读限制"""
import pytest
from db.duckdb_manager import SessionDB


def test_upload_csv_and_query(sample_csv, tmp_path):
    db = SessionDB(str(tmp_path / "test.db"))
    table = db.upload_file("s1", sample_csv, "sales.csv")
    assert table.startswith("file_")
    assert table in db.get_session_tables("s1")

    df = db.execute_sql("s1", f"SELECT * FROM {table}")
    assert len(df) == 4
    assert list(df.columns) == ["date", "sales", "orders"]


def test_upload_xlsx(sample_xlsx, tmp_path):
    db = SessionDB(str(tmp_path / "test.db"))
    table = db.upload_file("s2", sample_xlsx, "products.xlsx")
    df = db.execute_sql("s2", f"SELECT * FROM {table}")
    assert len(df) == 3


def test_aggregation_query(sample_csv, tmp_path):
    db = SessionDB(str(tmp_path / "test.db"))
    table = db.upload_file("s1", sample_csv, "sales.csv")
    df = db.execute_sql("s1", f"SELECT SUM(sales) AS total, AVG(orders) AS avg_orders FROM {table}")
    assert df["total"].iloc[0] == 570
    assert abs(df["avg_orders"].iloc[0] - 14.25) < 1e-6


def test_session_isolation(sample_csv, tmp_path):
    db = SessionDB(str(tmp_path / "test.db"))
    db.upload_file("s1", sample_csv, "sales.csv")
    assert db.get_session_tables("other_session") == []


def test_reject_non_select(sample_csv, tmp_path):
    db = SessionDB(str(tmp_path / "test.db"))
    table = db.upload_file("s1", sample_csv, "sales.csv")
    with pytest.raises(ValueError, match="仅支持 SELECT / WITH"):
        db.execute_sql("s1", f"DROP TABLE {table}")


def test_with_cte_query_allowed(sample_csv, tmp_path):
    """CTE(WITH) 开头的只读查询应被允许（回归：修复误拒绝合法查询）"""
    db = SessionDB(str(tmp_path / "test.db"))
    table = db.upload_file("s1", sample_csv, "sales.csv")
    df = db.execute_sql(
        "s1",
        f"WITH agg AS (SELECT SUM(sales) AS total FROM {table}) SELECT * FROM agg",
    )
    assert df["total"].iloc[0] == 570


def test_get_table_schema(sample_csv, tmp_path):
    """get_table_schema 返回列名+类型+示例行"""
    db = SessionDB(str(tmp_path / "test.db"))
    table = db.upload_file("s1", sample_csv, "sales.csv")
    info = db.get_table_schema(table)
    assert info["table"] == table
    col_names = [c["name"] for c in info["columns"]]
    assert col_names == ["date", "sales", "orders"]
    assert all(c["type"] for c in info["columns"])
    assert len(info["sample_rows"]) == 4  # 前5行，数据不足则全量
    assert "date" in info["sample_rows"][0]


def test_multiple_uploads_same_session(sample_csv, sample_xlsx, tmp_path):
    db = SessionDB(str(tmp_path / "test.db"))
    t1 = db.upload_file("s1", sample_csv, "sales.csv")
    t2 = db.upload_file("s1", sample_xlsx, "products.xlsx")
    tables = db.get_session_tables("s1")
    assert t1 in tables and t2 in tables
