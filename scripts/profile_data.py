import pandas as pd
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 160)

BASE = "/home/claude/project/raw_data/Project Dataset/E-Commerce Dataset "
MBASE = "/home/claude/project/raw_data/Project Dataset/Marketing Funnel"

files = {
    "orders": f"{BASE}/orders_dataset.csv",
    "items": f"{BASE}/order_items_dataset.csv",
    "payments": f"{BASE}/order_payments_dataset.csv",
    "reviews": f"{BASE}/order_reviews_dataset.csv",
    "products": f"{BASE}/products_dataset.csv",
    "customers": f"{BASE}/customers_dataset.csv",
    "sellers": f"{BASE}/sellers_dataset.csv",
    "geo": f"{BASE}/geolocation_dataset.csv",
    "cat_translation": f"{BASE}/product_category_name_translation.csv",
    "mql": f"{MBASE}/marketing_qualified_leads_dataset.csv",
    "closed_deals": f"{MBASE}/closed_deals_dataset.csv",
}

dfs = {}
for name, path in files.items():
    df = pd.read_csv(path)
    dfs[name] = df
    print(f"\n=== {name} : shape={df.shape} ===")
    print(df.dtypes)
    na = df.isna().mean().sort_values(ascending=False)
    na = na[na > 0]
    if len(na):
        print("-- missing % --")
        print((na * 100).round(1))

print("\n=== orders.order_status value_counts ===")
print(dfs["orders"]["order_status"].value_counts())

print("\n=== orders date range ===")
for c in ["order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
          "order_delivered_customer_date", "order_estimated_delivery_date"]:
    s = pd.to_datetime(dfs["orders"][c], errors="coerce")
    print(c, s.min(), "->", s.max(), " nulls:", s.isna().sum())

print("\n=== key cardinalities ===")
print("orders unique order_id:", dfs["orders"]["order_id"].nunique(), "/", len(dfs["orders"]))
print("items unique order_id:", dfs["items"]["order_id"].nunique(), "rows:", len(dfs["items"]))
print("reviews unique order_id:", dfs["reviews"]["order_id"].nunique(), "rows:", len(dfs["reviews"]))
print("reviews dup order_id count:", (dfs["reviews"]["order_id"].value_counts() > 1).sum())
print("payments unique order_id:", dfs["payments"]["order_id"].nunique(), "rows:", len(dfs["payments"]))
print("customers unique customer_id:", dfs["customers"]["customer_id"].nunique(), "unique customer_unique_id:", dfs["customers"]["customer_unique_id"].nunique())
print("products unique product_id:", dfs["products"]["product_id"].nunique())
print("sellers unique seller_id:", dfs["sellers"]["seller_id"].nunique())

print("\n=== category coverage ===")
cats = set(dfs["products"]["product_category_name"].dropna().unique())
trans = set(dfs["cat_translation"]["product_category_name"].dropna().unique())
print("categories in products not in translation table:", cats - trans)

print("\n=== review_score distribution ===")
print(dfs["reviews"]["review_score"].value_counts().sort_index())

print("\n=== marketing funnel overlap with sellers ===")
print("closed_deals unique seller_id:", dfs["closed_deals"]["seller_id"].nunique())
print("closed_deals seller_id also in sellers_dataset:", dfs["closed_deals"]["seller_id"].isin(dfs["sellers"]["seller_id"]).sum(), "/", len(dfs["closed_deals"]))
print("mql unique mql_id:", dfs["mql"]["mql_id"].nunique(), "rows:", len(dfs["mql"]))
print("closed_deals unique mql_id:", dfs["closed_deals"]["mql_id"].nunique(), "rows:", len(dfs["closed_deals"]))

print("\n=== states present ===")
print("customer_state:", sorted(dfs["customers"]["customer_state"].unique()))
print("seller_state:", sorted(dfs["sellers"]["seller_state"].unique()))
