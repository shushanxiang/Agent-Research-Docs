# -*- coding: utf-8 -*-
"""utils/plot_helper.py 测试：绘图返回 base64 data URI"""
import pandas as pd
from utils.plot_helper import plot_from_df


def test_plot_two_columns_returns_base64():
    df = pd.DataFrame({"date": ["2026-07-01", "2026-07-02"], "value": [1, 2]})
    out = plot_from_df(df, title="趋势图")
    assert out.startswith("data:image/png;base64,")
    assert len(out) > len("data:image/png;base64,")


def test_plot_multi_columns():
    df = pd.DataFrame(
        {"date": ["a", "b", "c"], "v1": [1, 2, 3], "v2": [4, 5, 6]}
    )
    out = plot_from_df(df)
    assert out.startswith("data:image/png;base64,")


def test_plot_chinese_title_no_crash():
    """中文标题不应导致绘图失败（仅可能产生字体警告）"""
    df = pd.DataFrame({"date": ["a", "b"], "value": [10, 20]})
    out = plot_from_df(df, title="每日销售额趋势")
    assert out.startswith("data:image/png;base64,")


def test_plot_bar_chart():
    """柱状图（对比/分布场景）"""
    df = pd.DataFrame({"category": ["家居", "电子", "美妆"], "sales": [100, 200, 150]})
    out = plot_from_df(df, title="类目销售额对比", chart_type="bar")
    assert out.startswith("data:image/png;base64,")


def test_plot_bar_multi_columns():
    """柱状图多序列"""
    df = pd.DataFrame({"region": ["US", "EU", "JP"], "v1": [1, 2, 3], "v2": [4, 5, 6]})
    out = plot_from_df(df, chart_type="bar")
    assert out.startswith("data:image/png;base64,")
