import sqlite3
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Better Stock Scanner", layout="wide")

VALID_TYPES = [
    "PREMARKET_MOVER",
    "REGULAR_MOVER",
    "AFTERHOURS_MOVER",
    "NEWS",
    "SEC",
]

st.title("Better Stock Scanner Dashboard")

conn = sqlite3.connect("scanner_results.db")

df = pd.read_sql_query(
    "SELECT * FROM alerts ORDER BY id DESC LIMIT 1000",
    conn
)

conn.close()

if df.empty:
    st.warning("No alerts yet. Start scanner3.py first.")
    st.stop()

df = df[df["alert_type"].isin(VALID_TYPES)]

if df.empty:
    st.warning("No valid alerts yet. CLOSED_MOVER alerts are now hidden.")
    st.stop()

st.subheader("Latest Valid Alerts")
st.dataframe(df, width="stretch")

st.subheader("Highest Scores")
st.dataframe(
    df.sort_values("score", ascending=False).head(50),
    width="stretch"
)

st.subheader("Premarket Movers")
st.dataframe(
    df[df["alert_type"] == "PREMARKET_MOVER"].head(50),
    width="stretch"
)

st.subheader("Regular Market Movers")
st.dataframe(
    df[df["alert_type"] == "REGULAR_MOVER"].head(50),
    width="stretch"
)

st.subheader("After-Hours Movers")
st.dataframe(
    df[df["alert_type"] == "AFTERHOURS_MOVER"].head(50),
    width="stretch"
)

st.subheader("News Alerts")
st.dataframe(
    df[df["alert_type"] == "NEWS"].head(50),
    width="stretch"
)

st.subheader("SEC Alerts")
st.dataframe(
    df[df["alert_type"] == "SEC"].head(50),
    width="stretch"
)

st.subheader("Bearish / Dilution Risk")
st.dataframe(
    df[df["score"] < 0].head(50),
    width="stretch"
)
