# -*- coding: utf-8 -*-
"""pytest 公共配置：路径、matplotlib 中文字体、共享数据 fixtures"""
import os
import sys
import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# matplotlib 无界面后端 + 中文字体（避免图表测试产生字体告警）
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = [
    "Microsoft YaHei",
    "SimHei",
    "Noto Sans CJK SC",
    "WenQuanYi Micro Hei",
]
plt.rcParams["axes.unicode_minus"] = False


@pytest.fixture
def sample_csv(tmp_path):
    """示例 CSV 销售数据（4 行，3 列）"""
    csv_path = tmp_path / "sales.csv"
    df = pd.DataFrame(
        {
            "date": ["2026-07-01", "2026-07-02", "2026-07-03", "2026-07-04"],
            "sales": [100, 150, 120, 200],
            "orders": [10, 15, 12, 20],
        }
    )
    df.to_csv(csv_path, index=False)
    return str(csv_path)


@pytest.fixture
def sample_xlsx(tmp_path):
    """示例 Excel 产品数据（3 行，3 列）"""
    xlsx_path = tmp_path / "products.xlsx"
    df = pd.DataFrame(
        {
            "sku": ["A1", "A2", "B1"],
            "name": ["eco bottle", "natural soap", "LED lamp"],
            "price": [9.9, 12.5, 19.0],
        }
    )
    df.to_excel(xlsx_path, index=False)
    return str(xlsx_path)


def make_state(messages, session_id="s1", **extra):
    """构造一个符合 AgentState 结构的普通 dict（供节点级单测使用）"""
    state = {
        "messages": messages,
        "session_id": session_id,
        "intent": None,
        "uploaded_files": [],
        "execution_result": None,
        "error": None,
    }
    state.update(extra)
    return state
