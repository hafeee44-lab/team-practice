import pandas as pd
import streamlit as st

from pipeline import get_items


def show_dashboard():
    items = get_items()
    metrics = st.columns(2)
    metrics[0].metric("Items tracked", len(items))
    metrics[1].metric("Total packs", sum(item["qty"] for item in items))
    st.table(pd.DataFrame(items))
