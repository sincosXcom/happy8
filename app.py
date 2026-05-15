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
    
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(st.secrets["google"], scopes=scopes)
        client = gspread.authorize(creds)
        spreadsheet_id = "18sLFvq7qpf8_TO7SRbUQS4ynkn4gANZzuT_dI7Z6ATw"
        sh = client.open_by_key(spreadsheet_id)
        ws = sh.worksheet("tomorrow")

        all_data = ws.get_all_values()
        if len(all_data) < 2:
            st.warning("tomorrow 工作表无数据")
        else:
            headers = all_data[0]
            rows = all_data[1:]

            # 定位期号列（必须包含“期号”或数字格式）
            issue_col = 0
            for i, h in enumerate(headers):
                if "期号" in str(h):
                    issue_col = i
                    break
            # 如果没找到，默认第0列，但通常第1列是序号，第2列是期号，我们尝试找包含2026的单元格
            if issue_col == 0 and len(rows) > 0:
                # 检查第一行哪一列看起来像期号（4-8位数字）
                for i in range(min(len(headers), 10)):
                    val = rows[0][i] if i < len(rows[0]) else ""
                    if str(val).isdigit() and len(str(val)) >= 6:
                        issue_col = i
                        break

            # 号码列：从期号列之后连续取20列
            num_start = issue_col + 1
            num_end = min(num_start + 20, len(headers))
            num_cols = list(range(num_start, num_end))

            # 查找类型、模型、温度列（可选）
            type_col = None
            model_col = None
            temp_col = None
            for i, h in enumerate(headers):
                h_str = str(h)
                if "类型" in h_str or "type" in h_str.lower():
                    type_col = i
                if "模型" in h_str or "model" in h_str.lower():
                    model_col = i
                if "温度" in h_str or "temp" in h_str.lower():
                    temp_col = i

            # 解析每一行数据
            groups = []
            common_issue = None   # 所有组共同的期号
            for row in rows:
                if len(row) <= issue_col:
                    continue
                issue_val = row[issue_col].strip() if issue_col < len(row) else ""
                if not common_issue and issue_val:
                    common_issue = issue_val   # 取第一个非空期号作为统一期号
                numbers = []
                for i in num_cols:
                    if i < len(row) and row[i].strip():
                        numbers.append(row[i].strip())
                if len(numbers) == 0:
                    continue
                # 标题
                model_type = row[type_col].strip() if type_col is not None and type_col < len(row) else "LSTM"
                model_name = row[model_col].strip() if model_col is not None and model_col < len(row) else "原始号码"
                temperature = row[temp_col].strip() if temp_col is not None and temp_col < len(row) else ""
                title = f"{model_type} - {model_name}"
                if temperature:
                    title += f" - 温度 {temperature}"
                groups.append({
                    "title": title,
                    "numbers": numbers
                })

            if not groups:
                st.info("tomorrow 工作表无有效预测数据")
            else:
                st.subheader("📊 今日高阶预测 18 组号码")
                if common_issue:
                    st.markdown(f"**📅 预测期号：{common_issue}**")
                st.markdown("---")

                # 自定义样式：横排号码球
                st.markdown("""
                <style>
                .number-block {
                    display: inline-block;
                    background: linear-gradient(135deg, #4b6cb7, #182848);
                    color: white;
                    border-radius: 12px;
                    width: 40px;
                    height: 40px;
                    line-height: 40px;
                    text-align: center;
                    margin: 4px;
                    font-weight: bold;
                    font-size: 15px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                }
                .group-card {
                    background: #f8fafc;
                    border-radius: 16px;
                    padding: 12px 16px;
                    margin-bottom: 24px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
                    border-left: 6px solid #4b6cb7;
                }
                .group-title {
                    font-size: 1.2rem;
                    font-weight: bold;
                    color: #1e293b;
                    margin-bottom: 12px;
                    border-bottom: 1px solid #e2e8f0;
                    padding-bottom: 6px;
                }
                .numbers-container {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 4px;
                    margin-top: 8px;
                }
                </style>
                """, unsafe_allow_html=True)

                # 逐个显示每组预测（横排号码）
                for g in groups:
                    # 构建号码球的HTML字符串（一次性拼接）
                    numbers_html = "".join([f'<div class="number-block">{num}</div>' for num in g['numbers']])
                    card_html = f"""
                    <div class="group-card">
                        <div class="group-title">🎯 {g['title']}</div>
                        <div class="numbers-container">
                            {numbers_html}
                        </div>
                    </div>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"读取预测数据失败: {e}")
        st.exception(e)

    if st.button("退出登录", use_container_width=True):
        st.session_state.vip_unlocked = False
        st.rerun()
