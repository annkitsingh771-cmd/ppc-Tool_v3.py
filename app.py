import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("🚀 Amazon PPC Smart Tool")

# -----------------------------
# SETTINGS
# -----------------------------

target_acos = st.sidebar.slider("Target ACOS (%)", 10, 60, 35) / 100
breakeven_roas = 1 / target_acos

spend_threshold = st.sidebar.number_input("Hard Waste Spend Threshold", value=200)

# -----------------------------
# FILE UPLOAD
# -----------------------------

uploaded_file = st.file_uploader("Upload Search Term Report", type=["csv","xlsx"])

if not uploaded_file:
    st.stop()

if uploaded_file.name.endswith("xlsx"):
    df = pd.read_excel(uploaded_file)
else:
    df = pd.read_csv(uploaded_file)

df.columns = df.columns.str.lower()

required = ["spend","sales","clicks","impressions"]

for col in required:
    if col not in df.columns:
        st.error(f"Missing column: {col}")
        st.stop()

for col in required:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

# -----------------------------
# METRICS
# -----------------------------

df["ROAS"] = np.where(df["spend"]>0, df["sales"]/df["spend"],0)
df["ACOS"] = np.where(df["sales"]>0, df["spend"]/df["sales"],1)
df["CPC"] = np.where(df["clicks"]>0, df["spend"]/df["clicks"],0)
df["CTR"] = np.where(df["impressions"]>0, df["clicks"]/df["impressions"],0)

# -----------------------------
# WASTE
# -----------------------------

df["Hard_Waste"] = np.where(
    (df["sales"]==0) & (df["spend"]>spend_threshold),
    df["spend"],0
)

df["Soft_Waste"] = np.where(
    (df["ROAS"] < breakeven_roas) & (df["sales"]>0),
    df["spend"],0
)

# -----------------------------
# CLASSIFICATION
# -----------------------------

df["Category"] = "Neutral"

df.loc[
    (df["ROAS"] >= breakeven_roas) & (df["sales"]>0),
    "Category"
] = "High Potential"

df.loc[
    (df["sales"]==0) & (df["spend"]>spend_threshold),
    "Category"
] = "Negative"

df.loc[
    (df["ROAS"] < breakeven_roas) & (df["sales"]>0),
    "Category"
] = "Low Potential"

# -----------------------------
# DASHBOARD
# -----------------------------

total_spend = df["spend"].sum()
total_sales = df["sales"].sum()
total_waste = df["Hard_Waste"].sum() + df["Soft_Waste"].sum()

col1,col2,col3,col4 = st.columns(4)

col1.metric("Spend", f"₹{total_spend:,.0f}")
col2.metric("Sales", f"₹{total_sales:,.0f}")
col3.metric("ROAS", round(total_sales/total_spend,2) if total_spend>0 else 0)
col4.metric("Waste", f"₹{total_waste:,.0f}")

st.divider()

st.subheader("Keyword Intelligence")

show_cols = [
    "spend","sales","ROAS","ACOS",
    "CPC","CTR","Category"
]

st.dataframe(df[show_cols], use_container_width=True)

# -----------------------------
# AMAZON BULK FILES
# -----------------------------

st.divider()
st.subheader("Download Amazon Bulk Files")

# NEGATIVE BULK
neg_df = df[df["Category"]=="Negative"]

bulk_neg = pd.DataFrame({
    "Record Type": "Negative Keyword",
    "Campaign": neg_df.get("campaign",""),
    "Ad Group": neg_df.get("ad group",""),
    "Keyword Text": neg_df.get("search term",""),
    "Match Type": "exact",
    "State": "enabled"
})

st.download_button(
    "Download Negative Bulk",
    bulk_neg.to_csv(index=False),
    "amazon_negative_bulk.csv"
)

# SCALE BULK
scale_df = df[df["Category"]=="High Potential"]

bulk_scale = pd.DataFrame({
    "Record Type": "Keyword",
    "Campaign": scale_df.get("campaign",""),
    "Ad Group": scale_df.get("ad group",""),
    "Keyword Text": scale_df.get("search term",""),
    "Match Type": "exact",
    "Bid": round(scale_df["CPC"]*1.2,2),
    "State": "enabled"
})

st.download_button(
    "Download Scale Bulk",
    bulk_scale.to_csv(index=False),
    "amazon_scale_bulk.csv"
)
