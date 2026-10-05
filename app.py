import streamlit as st

from ui import show_dashboard

st.set_page_config(page_title="ExpiRex", page_icon="✦", layout="wide", initial_sidebar_state="collapsed")

if "theme" not in st.session_state:
    st.session_state.theme = "dark"

show_dashboard()
