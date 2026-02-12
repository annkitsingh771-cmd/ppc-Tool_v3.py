import streamlit as st
import pandas as pd
import numpy as np
import re

st.set_page_config(layout="wide")
st.title("🚀 Amazon PPC Enterprise AI Platform – Phase 2")

# =========================================
# SETTINGS
# =========================================

strategy = st.sidebar.selectbox(
    "Strategy Mode",
    ["Balanced", "Growth", "Strict Profit"]
)

target_acos_input = st.sidebar.slider("Default Target ACOS (%)", 10, 60, 35) / 100
breakeven_roas_default = 1 / target_acos_input
base_name = st.sidebar.text_input("Base Campaign Name", "Product")

# =========================================
# FILE UPLOADS
# =========================================

search_file = st.file_uploader("Upload Search Term Report", type=["csv","xlsx"])
cost_file = st.file_uploader("Upload SKU Cost File (Optional)", type=["csv"])
business_file = st.file_uploader("Upload Business Report (Optional)", type=["csv","xlsx"])

if not search_file:
    st.stop()

# =========================================
# READ SEARCH TERM FILE
# =========================================

if search_file.name.endswith(".csv"):
    df = pd.read_csv(search_file)
else:
    df = pd.read_excel(search_file)

df.columns = df.columns.str.lower().str.strip()

sales_col = None
for col in df.columns:
    if "total sales" in col:
        sales_col = col
        break

if sales_col is None:
    st.error("Sales column not found.")
    st.stop()

rename_map = {}

if "customer search term" in df.columns:
    rename_map["customer search term"] = "search_term"
if "advertised sku" in df.columns:
    rename_map["advertised sku"] = "sku"
if "spend" in df.columns:
    rename_map["spend"] = "spend"
if "clicks" in df.columns:
    rename_map["clicks"] = "clicks"
if "impressions" in df.columns:
    rename_map["impressions"] = "impressions"
if "7 day total orders (#)" in df.columns:
    rename_map["7 day total orders (#)"] = "orders"

rename_map[sales_col] = "sales"
df = df.rename(columns=rename_map)

for col in ["spend","sales","clicks","impressions","orders"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

# =========================================
# BASIC METRICS
# =========================================

df["roas"] = np.where(df["spend"]>0, df["sales"]/df["spend"],0)
df["acos"] = np.where(df["sales"]>0, df["spend"]/df["sales"],0)
df["cpc"] = np.where(df["clicks"]>0, df["spend"]/df["clicks"],0)
df["confidence"] = np.clip((df["clicks"]/50)*100,0,100)

# =========================================
# AI CLUSTERING
# =========================================

def extract_root(text):
    words = re.findall(r'\w+', str(text))
    return " ".join(words[:2])

df["cluster"] = df["search_term"].apply(extract_root)

cluster_summary = df.groupby("cluster").agg({
    "spend":"sum",
    "sales":"sum"
}).reset_index()

cluster_summary["roas"] = np.where(
    cluster_summary["spend"]>0,
    cluster_summary["sales"]/cluster_summary["spend"],0
)

# =========================================
# PROFIT ENGINE
# =========================================

profit_mode = False

if cost_file:
    profit_mode = True
    cost_df = pd.read_csv(cost_file)
    cost_df.columns = cost_df.columns.str.lower()

    cost_df["total_cost"] = (
        cost_df["product_cost"] +
        cost_df["amazon_fees"] +
        cost_df["shipping"]
    )

    df = df.merge(cost_df, on="sku", how="left")
    df["profit"] = df["sales"] - df["spend"] - (df["orders"]*df["total_cost"])

# =========================================
# TRUE TACOS
# =========================================

tacos = None
if business_file:
    if business_file.name.endswith(".csv"):
        business_df = pd.read_csv(business_file)
    else:
        business_df = pd.read_excel(business_file)

    business_df.columns = business_df.columns.str.lower()
    if "total sales" in business_df.columns:
        total_revenue = business_df["total sales"].sum()
        tacos = df["spend"].sum()/total_revenue if total_revenue>0 else 0

# =========================================
# CLASSIFICATION
# =========================================

def classify(row):
    if row["spend"]>300 and row["sales"]==0:
        return "Negative"
    if row["roas"]>=breakeven_roas_default:
        return "Scale"
    if row["sales"]>0:
        return "Harvest"
    return "Watch"

df["action"] = df.apply(classify, axis=1)

# =========================================
# DASHBOARD
# =========================================

c1,c2,c3,c4 = st.columns(4)
c1.metric("Spend", f"₹{df['spend'].sum():,.0f}")
c2.metric("Sales", f"₹{df['sales'].sum():,.0f}")
c3.metric("ROAS", round(df['sales'].sum()/df['spend'].sum(),2))
if tacos:
    c4.metric("True TACOS", f"{round(tacos*100,2)}%")
else:
    c4.metric("Clusters", df["cluster"].nunique())

st.divider()

# =========================================
# CLUSTER VIEW
# =========================================

st.subheader("Cluster Intelligence")
st.dataframe(cluster_summary.sort_values("roas",ascending=False), use_container_width=True)

# =========================================
# BUDGET REDISTRIBUTION
# =========================================

waste_pool = df[df["action"]=="Negative"]["spend"].sum()
scale_pool = df[df["action"]=="Scale"]["spend"].sum()

st.subheader("AI Budget Suggestion")
st.write(f"Recoverable Waste: ₹{round(waste_pool,0)}")
st.write(f"Scaling Allocation: ₹{round(scale_pool,0)}")

# =========================================
# DYNAMIC BID OPTIMIZER
# =========================================

def dynamic_bid(row):
    if row["action"]=="Scale":
        return round(row["cpc"]*(1 + row["confidence"]/200),2)
    if row["action"]=="Harvest":
        return round(row["cpc"],2)
    return round(row["cpc"]*0.8,2)

df["suggested_bid"] = df.apply(dynamic_bid, axis=1)

# =========================================
# AUTO CAMPAIGN BULK
# =========================================

exact_campaign = f"Exact | {base_name}"
bulk_rows = []

bulk_rows.append({
    "Record Type":"Campaign",
    "Campaign":exact_campaign,
    "Campaign Daily Budget":500,
    "State":"enabled"
})

bulk_rows.append({
    "Record Type":"Ad Group",
    "Campaign":exact_campaign,
    "Ad Group":"Main",
    "State":"enabled"
})

for _,row in df.iterrows():

    if row["action"]=="Scale":
        bulk_rows.append({
            "Record Type":"Keyword",
            "Campaign":exact_campaign,
            "Ad Group":"Main",
            "Keyword Text":row["search_term"],
            "Match Type":"Exact",
            "Bid":row["suggested_bid"],
            "State":"enabled"
        })

    if row["action"]=="Negative":
        bulk_rows.append({
            "Record Type":"Negative Keyword",
            "Campaign":exact_campaign,
            "Keyword Text":row["search_term"],
            "Match Type":"Negative Exact",
            "State":"enabled"
        })

bulk_df = pd.DataFrame(bulk_rows)

st.download_button(
    "Download AI Bulk File",
    bulk_df.to_csv(index=False),
    "enterprise_ai_bulk.csv"
)
