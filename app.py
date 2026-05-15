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
    # 这里可以替换成你真正的高阶预测代码
    st.markdown("**基于最近 50 期历史数据 + 马尔科夫链 12 阶转移概率：**")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**红球推荐**")
        st.code("08 12 15 22 28 33")
    with col2:
        st.markdown("**蓝球推荐**")
        st.code("05 09")
    st.metric("AC值", "8")
    st.metric("和值", "118")
    if st.button("退出登录", use_container_width=True):
        st.session_state.vip_unlocked = False
        st.rerun()
