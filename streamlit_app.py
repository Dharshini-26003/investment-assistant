import streamlit as st

try:
    from app.main import *
except Exception as e:
    st.title("❌ App failed to start")
    st.exception(e)
