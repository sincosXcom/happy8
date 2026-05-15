import streamlit as st
import requests
import json
import time
import uuid
from streamlit.runtime.scriptrunner import get_script_run_ctx

@st.cache_resource
def get_redis_client():
    url = st.secrets["redis"]["url"]
    token = st.secrets["redis"]["token"]
    # Upstash Redis 的 REST 客户端
    class Redis:
        def __init__(self, url, token):
            self.url = url.rstrip('/')
            self.token = token
        def setex(self, key, ttl, value):
            data = {"key": key, "value": str(value), "ex": ttl}
            r = requests.post(f"{self.url}/set", json=data, headers={"Authorization": f"Bearer {self.token}"})
            return r.ok
        def get(self, key):
            r = requests.get(f"{self.url}/get/{key}", headers={"Authorization": f"Bearer {self.token}"})
            if r.ok and r.json()["result"]:
                return r.json()["result"]
            return None
        def sadd(self, set_name, member):
            data = {"set": set_name, "member": member}
            r = requests.post(f"{self.url}/sadd", json=data, headers={"Authorization": f"Bearer {self.token}"})
            return r.ok
        def srem(self, set_name, member):
            data = {"set": set_name, "member": member}
            r = requests.post(f"{self.url}/srem", json=data, headers={"Authorization": f"Bearer {self.token}"})
            return r.ok
        def scard(self, set_name):
            r = requests.get(f"{self.url}/scard/{set_name}", headers={"Authorization": f"Bearer {self.token}"})
            if r.ok:
                return r.json()["result"]
            return 0
        def smembers(self, set_name):
            r = requests.get(f"{self.url}/smembers/{set_name}", headers={"Authorization": f"Bearer {self.token}"})
            if r.ok:
                return r.json()["result"]
            return []
    return Redis(url, token)

def get_user_id():
    ctx = get_script_run_ctx()
    if ctx and ctx.session_id:
        return ctx.session_id
    if "user_id" not in st.session_state:
        st.session_state.user_id = str(uuid.uuid4())
    return st.session_state.user_id

def update_online():
    redis = get_redis_client()
    uid = get_user_id()
    key = f"user:{uid}"
    redis.setex(key, 300, time.time())  # 5分钟过期
    redis.sadd("online_users_set", uid)

def get_online_count():
    redis = get_redis_client()
    return redis.scard("online_users_set")

# 在页面中调用
update_online()
st.sidebar.metric("👥 当前在线", get_online_count())
