import streamlit as st
import os
import requests
import json
import time
import uuid
from streamlit.runtime.scriptrunner import get_script_run_ctx

# ========== 1. 带调试功能的 Redis 类 ==========
class Redis:
    def __init__(self, url, token):
        self.url = url.rstrip('/')
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})

    def _request(self, method, endpoint, params=None, data=None):
        url = f"{self.url}/{endpoint}"
        resp = self.session.request(method, url, params=params, data=data)
        st.write(f"DEBUG {endpoint}: status={resp.status_code}, text={resp.text[:200]}")
        return resp

    def setex(self, key, ttl, value):
        # 使用路径参数：POST /set/<key>?ex=<ttl>  body = value 字符串
        endpoint = f"set/{key}"
        resp = self._request("POST", endpoint, params={"ex": ttl}, data=str(value))
        return resp.ok

    def sadd(self, set_name, member):
        # 使用路径参数：POST /sadd/<set_name>  body = member 字符串
        endpoint = f"sadd/{set_name}"
        resp = self._request("POST", endpoint, data=member)
        return resp.ok

    def scard(self, set_name):
        endpoint = f"scard/{set_name}"
        resp = self._request("GET", endpoint)
        if resp.ok:
            result = resp.json().get("result")
            return int(result) if result is not None else 0
        return 0

# ========== 2. 获取 Redis 客户端（单例） ==========
@st.cache_resource
def get_redis_client():
    url = st.secrets["redis"]["url"]
    token = st.secrets["redis"]["token"]
    return Redis(url, token)   # 注意：使用上面定义的带调试的类

# ========== 3. 用户标识 ==========
def get_user_id():
    ctx = get_script_run_ctx()
    if ctx and ctx.session_id:
        return ctx.session_id
    if "user_id" not in st.session_state:
        st.session_state.user_id = str(uuid.uuid4())
    return st.session_state.user_id

# ========== 4. 更新在线状态 ==========
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

# ========== 5. 页面配置 ==========
st.set_page_config(page_title="多模型预测报告(快乐8)-SINCOSX", layout="wide")

update_online()
st.sidebar.metric("👥 当前在线", get_online_count())

# ========== 6. 显示 HTML 报告 ==========
report_file = "index.html"
if os.path.exists(report_file):
    with open(report_file, "r", encoding="utf-8") as f:
        html_content = f.read()
    st.components.v1.html(html_content, height=800, scrolling=True)
else:
    st.error(f"未找到报告文件：{report_file}，请先生成该文件。")
