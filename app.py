import streamlit as st
import os
import requests
import time
import uuid
from streamlit.runtime.scriptrunner import get_script_run_ctx

# ========== Redis 客户端（完整方法） ==========
class Redis:
    def __init__(self, url, token):
        self.url = url.rstrip('/')
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "text/plain"
        })

    def setex(self, key, ttl, value):
        """设置带过期时间的键值（秒）"""
        url = f"{self.url}/set/{key}?EX={ttl}"
        resp = self.session.post(url, data=str(value))
        return resp.ok

    def sadd(self, set_name, member):
        """向集合添加成员"""
        url = f"{self.url}/sadd/{set_name}"
        resp = self.session.post(url, data=member)
        return resp.ok

    def scard(self, set_name):
        """获取集合成员数"""
        url = f"{self.url}/scard/{set_name}"
        resp = self.session.get(url)
        if resp.ok:
            return resp.json().get("result", 0)
        return 0

@st.cache_resource
def get_redis_client():
    return Redis(st.secrets["redis"]["url"], st.secrets["redis"]["token"])

def get_user_id():
    ctx = get_script_run_ctx()
    if ctx and ctx.session_id:
        return ctx.session_id
    if "user_id" not in st.session_state:
        st.session_state.user_id = str(uuid.uuid4())
    return st.session_state.user_id

def update_online():
    try:
        redis = get_redis_client()
        uid = get_user_id()
        redis.setex(f"user:{uid}", 300, time.time())
        redis.sadd("online_users_set", uid)
    except Exception as e:
        st.error(f"Redis 错误: {e}")

def get_online_count():
    redis = get_redis_client()
    return redis.scard("online_users_set")

# ========== 页面配置 ==========
st.set_page_config(page_title="多模型预测报告(快乐8)-SINCOSX", layout="wide")

update_online()
# 修改这一行即可：
st.sidebar.markdown(f"👥 当前在线: **{get_online_count()}**")

# ========== 显示 HTML 报告 ==========
report_file = "index.html"
if os.path.exists(report_file):
    with open(report_file, "r", encoding="utf-8") as f:
        html_content = f.read()
    st.components.v1.html(html_content, height=800, scrolling=True)
else:
    st.error(f"未找到报告文件：{report_file}，请先生成该文件。")
