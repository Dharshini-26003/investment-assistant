import streamlit as st

try:
    from app.main import run_app

    run_app()
except Exception as e:
    st.title("App failed to start")
    st.exception(e)
