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
    """安全验证卡密，不泄露任何数据"""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        from datetime import datetime

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(st.secrets["google"], scopes=scopes)
        client = gspread.authorize(creds)
        spreadsheet_id = "18sLFvq7qpf8_TO7SRbUQS4ynkn4gANZzuT_dI7Z6ATw"
        sh = client.open_by_key(spreadsheet_id)
        ws = sh.worksheet("Cards")   # 授权码工作表名称

        # 使用 find 方法查找卡密（假设卡密在第一列 A）
        try:
            cell = ws.find(user_code, in_column=1)
        except gspread.exceptions.CellNotFound:
            return False, "授权码不存在"

        row_num = cell.row
        row_data = ws.row_values(row_num)
        if len(row_data) < 4:
            return False, "数据格式错误"

        # 根据你的实际列索引调整（默认：A=0卡密, B=1有效天数, C=2状态, D=3激活时间）
        code = row_data[0].strip()
        days_str = row_data[1].strip()
        status = row_data[2].strip() if len(row_data) > 2 else ""
        active_time_str = row_data[3].strip() if len(row_data) > 3 else ""

        if status == "封禁":
            return False, "授权码已被封禁"

        now = datetime.now()
        if not active_time_str:
            # 未激活
            ws.update_cell(row_num, 3, "已激活")
            ws.update_cell(row_num, 4, now.strftime("%Y-%m-%d %H:%M:%S"))
            return True, int(days_str)
        else:
            start = datetime.strptime(active_time_str, "%Y-%m-%d %H:%M:%S")
            used = (now - start).days
            remaining = int(days_str) - used
            if remaining > 0:
                return True, remaining
            else:
                return False, f"授权已过期 {remaining} 天"
    except Exception as e:
        # 不要将异常详情返回给用户，只记录到日志（streamlit 会显示红色错误，但不暴露细节）
        # 这里为了调试，可以暂时 st.error 但不要包含敏感信息
        # 生产环境建议直接返回通用错误
        return False, "验证服务异常，请稍后重试"

# ================== 4. 初始化 session_state ==================
if "vip_unlocked" not in st.session_state:
    st.session_state.vip_unlocked = False
    st.session_state.vip_days_left = 0

# ================== 5. 更新在线人数并显示 ==================
update_online_status()
st.sidebar.markdown(f"👥 当前在线: **{get_online_count()}**")

# ================== 6. 授权码解锁高阶矩阵区域 ==================
st.markdown("---")
st.header("🎯 高阶矩阵预测下一期")

if not st.session_state.vip_unlocked:
    st.error("🔒 该区域需解锁高阶权限。{请输入授权码}")
    col1, col2 = st.columns([2, 1])
    with col1:
        auth_code = st.text_input("请输入授权码" type="password", key="auth_input") # "请输入授权码", 
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

            # 定位关键列
            issue_col = None
            type_col = None
            model_col = None
            temp_col = None
            num_cols = []
            for i, h in enumerate(headers):
                h_str = str(h).strip().lower()
                if "issue" in h_str or "期号" in h_str:
                    issue_col = i
                elif "类型" in h_str or "type" in h_str:
                    type_col = i
                elif "模型" in h_str or "model" in h_str:
                    model_col = i
                elif "温度" in h_str or "temp" in h_str or "wen" in h_str:
                    temp_col = i
                elif h_str.startswith("n") and h_str[1:].isdigit():
                    num_cols.append(i)

            # 如果没有找到 n1..n20，尝试取第3列到第22列
            if len(num_cols) == 0 and len(headers) >= 22:
                num_cols = list(range(2, min(22, len(headers))))
            if len(num_cols) == 0:
                st.error("无法识别号码列，请检查表头是否包含 n1~n20")
                st.stop()

            groups = []
            common_issue = None
            for row in rows:
                if len(row) < max(num_cols) + 1:
                    continue
                # 期号
                if issue_col is not None and issue_col < len(row):
                    issue_val = row[issue_col].strip()
                    if issue_val and not common_issue:
                        common_issue = issue_val
                # 提取号码（至少需要20个才能显示，否则跳过）
                numbers = [row[i].strip() for i in num_cols if i < len(row) and row[i].strip()]
                if len(numbers) < 20:
                    continue  # 跳过号码不足20的行
                # 提取类型、模型、温度
                type_val = row[type_col].strip() if type_col is not None and type_col < len(row) else "未知类型"
                model_val = row[model_col].strip() if model_col is not None and model_col < len(row) else "未知模型"
                temp_val = row[temp_col].strip() if temp_col is not None and temp_col < len(row) else ""
                title = f"{type_val} - {model_val}"
                if temp_val:
                    title += f" - 温度 {temp_val}"
                groups.append({
                    "title": title,
                    "numbers": numbers,
                    "temperature": temp_val
                })

            if not groups:
                st.info("未找到有效预测数据（至少需要20个号码）")
            else:
                # 按温度分组
                groups_by_temp = {}
                for g in groups:
                    t = g["temperature"]
                    if t not in groups_by_temp:
                        groups_by_temp[t] = []
                    groups_by_temp[t].append(g)

                # 温度顺序（匹配表格中的实际值）
                temp_order = ["2", "1", "1.5"]

                st.subheader("📊 今日高阶预测 18 组号码")
                if common_issue:
                    st.markdown(f"**📅 预测期号：{common_issue}**")
                st.markdown("---")

                # 样式
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
                .temp-section {
                    margin-bottom: 32px;
                }
                .temp-header {
                    font-size: 1.4rem;
                    font-weight: bold;
                    color: #0f172a;
                    background: #eef2ff;
                    padding: 8px 16px;
                    border-radius: 28px;
                    display: inline-block;
                    margin-bottom: 20px;
                }
                </style>
                """, unsafe_allow_html=True)

                all_lines = []
                for temp_val in temp_order:
                    if temp_val not in groups_by_temp:
                        continue
                    st.markdown(f'<div class="temp-section"><div class="temp-header">🌡️ 温度 {temp_val}</div></div>', unsafe_allow_html=True)
                    for g in groups_by_temp[temp_val]:
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
                        line = f"{g['title']}: " + " ".join(g['numbers'])
                        all_lines.append(line)

                if all_lines:
                    full_text = "\n\n".join(all_lines)
                    st.text_area("📋 全部 18 组号码（可选中复制）", full_text, height=200)

    except Exception as e:
        st.error(f"读取预测数据失败：{str(e)}")

    if st.button("退出登录", use_container_width=True):
        st.session_state.vip_unlocked = False
        st.rerun()

# ================== 7. 显示原有的静态 HTML 报告 ==================
report_file = "index.html"   # 请确认你的文件名
if os.path.exists(report_file):
    with open(report_file, "r", encoding="utf-8") as f:
        html_content = f.read()
    st.components.v1.html(html_content, height=800, scrolling=True)
else:
    st.error(f"未找到报告文件：{report_file}，请先生成该文件。")
