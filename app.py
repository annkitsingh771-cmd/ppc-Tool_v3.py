import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("🚀 Amazon PPC Enterprise AI Platform")

# =========================================
# SIDEBAR SETTINGS
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

search_file = st.file_uploader(
    "Upload Search Term Report",
    type=["csv", "xlsx"]
)

cost_file = st.file_uploader(
    "Upload SKU Cost File (Optional)",
    type=["csv"]
)

business_file = st.file_uploader(
    "Upload Business Report (Optional - For TACOS)",
    type=["csv", "xlsx"]
)

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

# Auto detect sales column
sales_col = None
for col in df.columns:
    if "total sales" in col:
        sales_col = col
        break

if sales_col is None:
    st.error("Sales column not found in Search Term report.")
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

for col in ["spend", "sales", "clicks", "impressions", "orders"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

# =========================================
# BASIC METRICS
# =========================================

df["roas"] = np.where(df["spend"] > 0, df["sales"] / df["spend"], 0)
df["acos"] = np.where(df["sales"] > 0, df["spend"] / df["sales"], 0)
df["cpc"] = np.where(df["clicks"] > 0, df["spend"] / df["clicks"], 0)
df["ctr"] = np.where(df["impressions"] > 0, df["clicks"] / df["impressions"], 0)

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

    df["profit_per_unit"] = df["selling_price"] - df["total_cost"]
    df["profit"] = df["sales"] - df["spend"] - (df["orders"] * df["total_cost"])

    df["break_even_acos"] = np.where(
        df["selling_price"] > 0,
        df["profit_per_unit"] / df["selling_price"],
        target_acos_input
    )

# =========================================
# TRUE TACOS MODEL
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
        tacos = df["spend"].sum() / total_revenue if total_revenue > 0 else 0

# =========================================
# CLASSIFICATION LOGIC
# =========================================

def classify(row):

    if row["spend"] > 300 and row["sales"] == 0:
        return "Negative"

    if profit_mode:
        if row["profit"] < 0:
            return "Loss"
        breakeven_roas = 1 / row["break_even_acos"] if row["break_even_acos"] > 0 else breakeven_roas_default
    else:
        breakeven_roas = breakeven_roas_default

    if strategy == "Growth":
        if row["roas"] >= breakeven_roas * 0.8:
            return "Scale"

    if strategy == "Strict Profit":
        if row["roas"] >= breakeven_roas * 1.2:
            return "Scale"

    if strategy == "Balanced":
        if row["roas"] >= breakeven_roas:
            return "Scale"

    if row["sales"] > 0:
        return "Harvest"

    return "Watch"

df["action"] = df.apply(classify, axis=1)

# =========================================
# DASHBOARD METRICS
# =========================================

col1, col2, col3, col4 = st.columns(4)

col1.metric("Spend", f"₹{df['spend'].sum():,.0f}")
col2.metric("Sales", f"₹{df['sales'].sum():,.0f}")
col3.metric("ROAS", round(df['sales'].sum() / df['spend'].sum(), 2))

if profit_mode:
    col4.metric("Profit", f"₹{df['profit'].sum():,.0f}")
else:
    col4.metric("Mode", "Revenue")

if tacos:
    st.metric("True TACOS", f"{round(tacos*100,2)}%")

st.divider()

# =========================================
# SKU PERFORMANCE VIEW
# =========================================

if "sku" in df.columns:
    sku_summary = df.groupby("sku").agg({
        "spend":"sum",
        "sales":"sum"
    }).reset_index()

    if profit_mode:
        sku_summary["profit"] = df.groupby("sku")["profit"].sum().values

    st.subheader("SKU Performance")
    st.dataframe(sku_summary, use_container_width=True)

# =========================================
# BUDGET REDISTRIBUTION ENGINE
# =========================================

waste_budget = df[df["action"]=="Negative"]["spend"].sum()
scale_budget = df[df["action"]=="Scale"]["spend"].sum()

st.subheader("Budget Engine")

st.write(f"Recoverable Waste Budget: ₹{round(waste_budget,0)}")
st.write(f"Currently Scaling Budget: ₹{round(scale_budget,0)}")

# =========================================
# AUTO CAMPAIGN CREATION
# =========================================

exact_campaign = f"Exact | {base_name}"
phrase_campaign = f"Phrase | {base_name}"
broad_campaign = f"Broad | {base_name}"

bulk_rows = []

for campaign in [exact_campaign, phrase_campaign, broad_campaign]:
    bulk_rows.append({
        "Record Type":"Campaign",
        "Campaign":campaign,
        "Campaign Daily Budget":500,
        "State":"enabled"
    })
    bulk_rows.append({
        "Record Type":"Ad Group",
        "Campaign":campaign,
        "Ad Group":"Main",
        "State":"enabled"
    })

for _, row in df.iterrows():

    if row["action"] == "Scale":
        bid_multiplier = 1.2 if strategy=="Growth" else 1.1
        bulk_rows.append({
            "Record Type":"Keyword",
            "Campaign":exact_campaign,
            "Ad Group":"Main",
            "Keyword Text":row["search_term"],
            "Match Type":"Exact",
            "Bid":round(row["cpc"]*bid_multiplier,2),
            "State":"enabled"
        })

    if row["action"] == "Negative":
        bulk_rows.append({
            "Record Type":"Negative Keyword",
            "Campaign":exact_campaign,
            "Keyword Text":row["search_term"],
            "Match Type":"Negative Exact",
            "State":"enabled"
        })

bulk_df = pd.DataFrame(bulk_rows)

st.divider()
st.download_button(
    "Download Enterprise Bulk File",
    bulk_df.to_csv(index=False),
    "enterprise_bulk_upload.csv"
)
