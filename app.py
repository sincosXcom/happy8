import streamlit as st
import os
import requests
import time
import uuid
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from streamlit.runtime.scriptrunner import get_script_run_ctx

# ================== 1. 页面配置（必须放在最前面） ==================
st.set_page_config(page_title="多模型预测报告(快乐8)", layout="wide")

# ================== 2. Redis 在线人数功能 ==================
class RedisClient:
    def __init__(self, url, token):
        self.url = url.rstrip('/')
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "text/plain"
        })

    def setex(self, key, ttl, value):
        url = f"{self.url}/set/{key}?EX={ttl}"
        resp = self.session.post(url, data=str(value))
        return resp.ok

    def sadd(self, set_name, member):
        url = f"{self.url}/sadd/{set_name}"
        resp = self.session.post(url, data=member)
        return resp.ok

    def scard(self, set_name):
        url = f"{self.url}/scard/{set_name}"
        resp = self.session.get(url)
        if resp.ok:
            return resp.json().get("result", 0)
        return 0

@st.cache_resource
def get_redis():
    return RedisClient(st.secrets["redis"]["url"], st.secrets["redis"]["token"])

def get_user_id():
    ctx = get_script_run_ctx()
    if ctx and ctx.session_id:
        return ctx.session_id
    if "user_id" not in st.session_state:
        st.session_state.user_id = str(uuid.uuid4())
    return st.session_state.user_id

def update_online_status():
    try:
        r = get_redis()
        uid = get_user_id()
        r.setex(f"user:{uid}", 300, time.time())
        r.sadd("online_users_set", uid)
    except Exception as e:
        st.sidebar.error(f"在线人数异常: {e}")

def get_online_count():
    try:
        r = get_redis()
        return r.scard("online_users_set")
    except:
        return 0

# ================== 3. Google Sheets 授权码验证 ==================
def verify_card_from_sheets(user_code):
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(st.secrets["google"], scopes=scopes)
        client = gspread.authorize(creds)
        
        spreadsheet_id = "18sLFvq7qpf8_TO7SRbUQS4ynkn4gANZzuT_dI7Z6ATw"  # 你的表格ID
        sh = client.open_by_key(spreadsheet_id)
        worksheet = sh.worksheet("Cards")
        
        # 打印所有数据，确认能读取
        all_data = worksheet.get_all_values()
        st.write("表格内容：", all_data)   # 临时查看
        
        records = worksheet.get_all_records()
        now = datetime.now()
        
        for idx, row in enumerate(records):
            if str(row["卡密"]).strip() == user_code.strip():
                if not row.get("激活时间"):
                    row_num = idx + 2
                    worksheet.update_cell(row_num, 3, "已激活")
                    worksheet.update_cell(row_num, 4, now.strftime("%Y-%m-%d %H:%M:%S"))
                    return True, int(row["有效天数"])
                else:
                    start = datetime.strptime(row["激活时间"], "%Y-%m-%d %H:%M:%S")
                    used = (now - start).days
                    remaining = int(row["有效天数"]) - used
                    if remaining > 0:
                        return True, remaining
                    else:
                        return False, f"授权已过期 {remaining} 天"
        return False, "授权码不存在"
    except Exception as e:
        st.exception(e)   # 打印完整堆栈
        return False, f"验证服务异常: {str(e)}"

# ================== 4. 初始化 session_state ==================
if "vip_unlocked" not in st.session_state:
    st.session_state.vip_unlocked = False
    st.session_state.vip_days_left = 0

# ================== 5. 更新在线人数并显示 ==================
update_online_status()
st.sidebar.markdown(f"👥 当前在线: **{get_online_count()}**")

# ================== 6. 显示原有的静态 HTML 报告 ==================
report_file = "index.html"   # 请确认你的文件名
if os.path.exists(report_file):
    with open(report_file, "r", encoding="utf-8") as f:
        html_content = f.read()
    st.components.v1.html(html_content, height=800, scrolling=True)
else:
    st.error(f"未找到报告文件：{report_file}，请先生成该文件。")

# ================== 7. 授权码解锁高阶矩阵区域 ==================
st.markdown("---")
st.header("🎯 高阶矩阵预测 (马尔科夫链 12阶)")

if not st.session_state.vip_unlocked:
    st.error("🔒 该区域需解锁高阶权限。")
    col1, col2 = st.columns([2, 1])
    with col1:
        auth_code = st.text_input("请输入授权码", type="password", key="auth_input")
    with col2:
        if st.button("激活高级权限", use_container_width=True):
            ok, msg = verify_card_from_sheets(auth_code)
            if ok:
                st.session_state.vip_unlocked = True
                st.session_state.vip_days_left = msg
                st.success(f"✅ 解锁成功！剩余 {msg} 天")
                st.rerun()
            else:
                st.error(msg)
else:
    st.success(f"🌟 VIP 已激活 | 剩余 {st.session_state.vip_days_left} 天")
    
    # ---------- 读取今日预测数据 ----------
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(st.secrets["google"], scopes=scopes)
        client = gspread.authorize(creds)
        spreadsheet_id = "18sLFvq7qpf8_TO7SRbUQS4ynkn4gANZzuT_dI7Z6ATw"
        sh = client.open_by_key(spreadsheet_id)
        ws = sh.worksheet("今日预测")   # 工作表名称请确认
        
        # 获取所有数据（包括表头）
        all_data = ws.get_all_values()
        if len(all_data) < 2:
            st.warning("今日预测工作表无数据")
        else:
            headers = all_data[0]       # 第一行作为列名
            rows = all_data[1:]         # 数据行
            
            # 自动识别期号列（通常第一列或包含“期号”/“No.”）
            issue_col_idx = 0
            for i, h in enumerate(headers):
                if "期号" in h or "No" in h or "期" in h:
                    issue_col_idx = i
                    break
            
            # 号码列：期号之后的连续20列（或者从第2列到第21列）
            # 根据你的截图，号码从第2列到第21列（共20个）
            number_start_idx = 1
            number_end_idx = min(number_start_idx + 20, len(headers))
            number_cols = list(range(number_start_idx, number_end_idx))
            
            # 命中数、温度列（可能位于最后）
            hit_col = None
            temp_col = None
            for i, h in enumerate(headers):
                if "命中" in h:
                    hit_col = i
                if "温度" in h:
                    temp_col = i
            
            # 构建展示数据
            display_rows = []
            for row in rows:
                if len(row) < number_end_idx:
                    continue
                issue = row[issue_col_idx] if issue_col_idx < len(row) else ""
                numbers = [row[i] for i in number_cols if i < len(row) and row[i].strip()]
                hit = row[hit_col] if hit_col is not None and hit_col < len(row) else ""
                temp = row[temp_col] if temp_col is not None and temp_col < len(row) else ""
                display_rows.append({
                    "期号": issue,
                    "号码": numbers,
                    "命中数": hit,
                    "温度": temp
                })
            
            # ---------- 展示为漂亮的号码球表格 ----------
            st.subheader("📊 今日高阶预测 18 组号码")
            
            # 自定义CSS样式（号码球）
            st.markdown("""
            <style>
            .pred-ball {
                display: inline-block;
                width: 36px;
                height: 36px;
                line-height: 36px;
                border-radius: 50%;
                text-align: center;
                margin: 2px;
                font-size: 14px;
                font-weight: bold;
                color: white;
                background-color: #f14545;
                box-shadow: 0 1px 3px rgba(0,0,0,0.2);
            }
            .pred-table td {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            </style>
            """, unsafe_allow_html=True)
            
            # 使用 HTML 表格展示（可滚动）
            html_table = "<table class='pred-table' style='width:100%; border-collapse:collapse;'>"
            html_table += "<tr><th>期号</th><th>20码推荐</th><th>命中数</th><th>温度</th></tr>"
            for row in display_rows:
                balls = "".join([f'<span class="pred-ball">{n}</span>' for n in row["号码"]])
                html_table += f"<tr><td style='vertical-align:top;'><b>{row['期号']}</b></td><td>{balls}</td><td>{row['命中数']}</td><td>{row['温度']}</td></tr>"
            html_table += "</table>"
            st.markdown(html_table, unsafe_allow_html=True)
            
    except Exception as e:
        st.error(f"读取预测数据失败: {e}")
        st.exception(e)  # 调试时可显示详细错误
    
    if st.button("退出登录", use_container_width=True):
        st.session_state.vip_unlocked = False
        st.rerun()
