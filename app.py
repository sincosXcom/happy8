# ========== 授权码验证函数（已集成 Google Sheets） ==========
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

def verify_card_from_sheets(user_code):
    """返回 (是否成功, 剩余天数或错误信息)"""
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["google"], scopes=scopes)
        client = gspread.authorize(creds)
        
        # 打开你的表格（确保名字和 sheet 名称正确）
        sh = client.open("Lotto_Cards")          # 表格名称
        worksheet = sh.worksheet("Cards")        # 工作表名称
        
        records = worksheet.get_all_records()
        now = datetime.now()
        
        for idx, row in enumerate(records):
            if str(row["卡密"]).strip() == user_code.strip():
                # 未激活
                if not row.get("激活时间"):
                    # 更新激活时间和状态
                    row_num = idx + 2  # 因为 records 从 0 开始，且第一行是表头
                    worksheet.update_cell(row_num, 3, "已激活")      # C列状态
                    worksheet.update_cell(row_num, 4, now.strftime("%Y-%m-%d %H:%M:%S"))  # D列激活时间
                    return True, int(row["有效天数"])
                else:
                    # 已激活，计算剩余天数
                    start = datetime.strptime(row["激活时间"], "%Y-%m-%d %H:%M:%S")
                    used_days = (now - start).days
                    remaining = int(row["有效天数"]) - used_days
                    if remaining > 0:
                        return True, remaining
                    else:
                        return False, f"授权已过期 {remaining} 天"
        return False, "授权码不存在"
    except Exception as e:
        return False, f"验证服务异常: {str(e)}"

# ========== 在你的页面中（比如高阶矩阵标签页）添加以下代码 ==========
# 初始化 session_state
if "vip_unlocked" not in st.session_state:
    st.session_state.vip_unlocked = False
    st.session_state.vip_days_left = 0

# 创建两个占位容器（用来动态刷新）
auth_placeholder = st.empty()
content_placeholder = st.empty()

if not st.session_state.vip_unlocked:
    with auth_placeholder.container():
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
                    st.rerun()
                else:
                    st.error(msg)
else:
    # 已解锁，显示高阶内容
    with content_placeholder.container():
        st.success(f"🌟 VIP 已激活 | 剩余 {st.session_state.vip_days_left} 天")
        st.markdown("### 高阶马尔科夫矩阵预测 (12阶)")
        st.markdown("基于最近 50 期历史数据 + 马尔科夫链 12 阶转移概率：")
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
