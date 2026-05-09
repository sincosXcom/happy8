import streamlit as st
import os

st.set_page_config(page_title="多模型预测报告(快乐8)-SINCOSX", layout="wide")

# 确保文件存在
report_file = "index.html"
if os.path.exists(report_file):
    with open(report_file, "r", encoding="utf-8") as f:
        html_content = f.read()
    # 嵌入 HTML，设置高度和滚动
    st.components.v1.html(html_content, height=800, scrolling=True)
else:
    st.error(f"未找到报告文件：{report_file}，请先生成该文件。")
