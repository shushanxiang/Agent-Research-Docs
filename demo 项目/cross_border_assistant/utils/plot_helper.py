# -*- coding: utf-8 -*-
import matplotlib.pyplot as plt
import pandas as pd
import io
import base64

def plot_from_df(df: pd.DataFrame, title: str = "趋势图", chart_type: str = "line") -> str:
    """绘制折线图(line)或柱状图(bar)，返回base64 data URI

    约定：第一列为 X 轴，其余列为数值序列；仅有一列数值时直接绘制该列。
    """
    plt.figure(figsize=(8, 4))
    x_col = df.columns[0]
    y_cols = df.columns[1:] if len(df.columns) > 2 else df.columns[1]

    x = df[x_col].astype(str)  # 统一转字符串，避免日期/数字刻度问题

    if chart_type == "bar":
        if len(df.columns) == 2:
            plt.bar(x, df[y_cols], alpha=0.8)
        else:
            width = 0.8 / len(y_cols)
            for i, col in enumerate(y_cols):
                plt.bar([j + i * width for j in range(len(df))], df[col], width=width, label=col)
            plt.xticks(range(len(df)), x, rotation=45)
            plt.legend()
    else:  # line（默认）
        if len(df.columns) == 2:
            plt.plot(x, df[y_cols], marker='o')
        else:
            for col in y_cols:
                plt.plot(x, df[col], marker='o', label=col)
            plt.legend()

    plt.title(title)
    plt.xticks(rotation=45)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    base64_img = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()
    return f"data:image/png;base64,{base64_img}"
