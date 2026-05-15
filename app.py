import streamlit as st
import os
import time
import uuid
import gspread
from google.oauth2.service_account import Credentials
from streamlit.runtime.scriptrunner import get_script_run_ctx

# ------------------ 1. Google Sheets 在线人数统计核心 ------------------
@st.cache_resource
def get_sheet_client():
    """复用你已有的 Google Sheets 授权（与卡密验证相同）"""
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["google"], scopes=scopes)
    client = gspread.authorize(creds)
    # 打开或新建一个工作表用于在线人数（建议新建一个 sheet，避免与卡密表冲突）
    try:
        sh = client.open("Lotto_Cards")  # 沿用你的已有表格
        # 尝试获取名为 "OnlineUsers" 的工作表，如果没有就创建
        try:
            worksheet = sh.worksheet("OnlineUsers")
        except gspread.WorksheetNotFound:
            worksheet = sh.add_worksheet(title="OnlineUsers", rows=1, cols=3)
            # 写入表头
            worksheet.update('A1:C1', [['session_id', 'last_active', 'user_agent']])
        return worksheet
    except Exception as e:
        st.error(f"连接 Google Sheets 失败: {e}")
        return None

def get_session_id():
    """获取当前用户的唯一会话ID（同一标签页刷新不变，新开标签页不同）"""
    ctx = get_script_run_ctx()
    if ctx and ctx.session_id:
        return f"session_{ctx.session_id}"
    # 后备方案：使用 session_state 中存储的 UUID
    if "fallback_session_id" not in st.session_state:
        st.session_state.fallback_session_id = str(uuid.uuid4())
    return st.session_state.fallback_session_id

def update_online_status(worksheet, session_id, ttl_seconds=300):
    """
    在 Google Sheets 中更新当前会话的活动时间，并删除过期会话
    ttl_seconds: 超时时间（秒），默认5分钟
    """
    if worksheet is None:
        return 0
    
    current_time = time.time()
    # 1. 获取所有记录
    all_records = worksheet.get_all_values()
    if len(all_records) <= 1:
        # 只有表头，直接添加当前会话
        worksheet.append_row([session_id, current_time, "streamlit"])
        return 1
    
    # 2. 查找当前会话所在行
    session_col = 0  # A列是 session_id
    time_col = 1     # B列是 last_active
    row_to_update = None
    rows_to_keep = [all_records[0]]  # 保留表头
    
    for i, row in enumerate(all_records[1:], start=2):
        if len(row) < 2:
            continue
        sid = row[session_col].strip()
        try:
            last_active = float(row[time_col])
        except (ValueError, IndexError):
            last_active = 0
        
        # 如果会话过期，跳过（不加入保留列表）
        if current_time - last_active > ttl_seconds:
            continue
        
        # 未过期的记录保留
        rows_to_keep.append(row)
        if sid == session_id:
            row_to_update = i  # 记录行号以便更新
    
    # 3. 如果当前会话已存在且未过期，更新它的活动时间
    if row_to_update:
        worksheet.update_cell(row_to_update, time_col + 1, current_time)
    else:
        # 否则新增一行
        rows_to_keep.append([session_id, current_time, "streamlit"])
    
    # 4. 清空工作表并重写所有活跃记录（避免删除操作复杂）
    worksheet.clear()
    if rows_to_keep:
        worksheet.update('A1:C{}'.format(len(rows_to_keep)), rows_to_keep)
    
    # 5. 返回在线人数（去掉表头）
    return len(rows_to_keep) - 1

def get_online_count(worksheet):
    """仅获取当前在线人数（不更新状态）"""
    if worksheet is None:
        return 0
    all_records = worksheet.get_all_values()
    if len(all_records) <= 1:
        return 0
    current_time = time.time()
    ttl_seconds = 300
    count = 0
    for row in all_records[1:]:
        if len(row) >= 2:
            try:
                last_active = float(row[1])
                if current_time - last_active <= ttl_seconds:
                    count += 1
            except:
                pass
    return count

# ------------------ 2. 页面配置与主逻辑 ------------------
st.set_page_config(page_title="多模型预测报告(快乐8)-SINCOSX", layout="wide")

# ---- 初始化在线人数组件 ----
worksheet = get_sheet_client()
if worksheet is not None:
    session_id = get_session_id()
    online_num = update_online_status(worksheet, session_id)
else:
    online_num = 0

# 在侧边栏显示在线人数（你也可以放在顶部）
st.sidebar.metric("👥 当前在线人数", online_num)

# ---- 显示原有的静态 HTML 报告 ----
report_file = "index.html"
if os.path.exists(report_file):
    with open(report_file, "r", encoding="utf-8") as f:
        html_content = f.read()
    st.components.v1.html(html_content, height=800, scrolling=True)
else:
    st.error(f"未找到报告文件：{report_file}，请先生成该文件。")

# （可选）在页面底部实时刷新在线人数，可以通过定时自动刷新页面实现
# 但 Streamlit 没有内置定时器，用户刷新页面时人数会自动更新
