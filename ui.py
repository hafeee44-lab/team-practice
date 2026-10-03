import pandas as pd
import streamlit as st

from pipeline import get_items


def show_dashboard():
    st.table(pd.DataFrame(get_items()))
