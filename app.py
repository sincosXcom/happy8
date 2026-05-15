import streamlit as st
import os
import requests
import json
import time
import uuid
from streamlit.runtime.scriptrunner import get_script_run_ctx

# ========== 1. 在线人数功能（Redis） ==========
@st.cache_resource
def get_redis_client():
    url = st.secrets["redis"]["url"]
    token = st.secrets["redis"]["token"]
    class Redis:
        def __init__(self, url, token):
            self.url = url.rstrip('/')
            self.token = token
        def setex(self, key, ttl, value):
            data = {"key": key, "value": str(value), "ex": ttl}
            r = requests.post(f"{self.url}/set", json=data, headers={"Authorization": f"Bearer {self.token}"})
            return r.ok
        def sadd(self, set_name, member):
            data = {"set": set_name, "member": member}
            r = requests.post(f"{self.url}/sadd", json=data, headers={"Authorization": f"Bearer {self.token}"})
            return r.ok
        def scard(self, set_name):
            r = requests.get(f"{self.url}/scard/{set_name}", headers={"Authorization": f"Bearer {self.token}"})
            if r.ok:
                return r.json()["result"]
            return 0
    return Redis(url, token)

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
        key = f"user:{uid}"
        redis.setex(key, 300, time.time())
        redis.sadd("online_users_set", uid)
        # 调试：打印当前集合大小
        st.write(f"DEBUG: set size = {redis.scard('online_users_set')}")
    except Exception as e:
        st.error(f"Redis 错误: {e}")

def get_online_count():
    redis = get_redis_client()
    return redis.scard("online_users_set")

# ========== 2. 页面配置 ==========
st.set_page_config(page_title="多模型预测报告(快乐8)-SINCOSX", layout="wide")

# 更新在线状态 + 侧边栏显示人数
update_online()
st.sidebar.metric("👥 当前在线", get_online_count())

# ========== 3. 显示原来的 HTML 报告 ==========
report_file = "index.html"
if os.path.exists(report_file):
    with open(report_file, "r", encoding="utf-8") as f:
        html_content = f.read()
    st.components.v1.html(html_content, height=800, scrolling=True)
else:
    st.error(f"未找到报告文件：{report_file}，请先生成该文件。")
