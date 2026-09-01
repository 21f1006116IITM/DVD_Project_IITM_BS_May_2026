"""
Build analytical tables for the E-Commerce Orders, Delivery & Customer Satisfaction
dashboard, from the raw Olist + Marketing Funnel CSVs.

Outputs (parquet) written to /home/claude/project/data/:
  - orders_fact.parquet   grain = order        (KPIs, delivery/satisfaction trends)
  - items_fact.parquet    grain = order_item   (category & seller drill-down)
  - seller_fact.parquet   grain = seller       (seller risk / acquisition channel)
  - state_geo.parquet     grain = state        (map centroids)
  - meta.json             filter option lists, date range, data-quality notes
"""
import json
import pandas as pd
import numpy as np
from pathlib import Path

RAW = Path("/home/claude/project/raw_data/Project Dataset")
ECOM = RAW / "E-Commerce Dataset "
MKT = RAW / "Marketing Funnel"
OUT = Path("/home/claude/project/data")
OUT.mkdir(parents=True, exist_ok=True)

DATE_COLS_ORDERS = [
    "order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
    "order_delivered_customer_date", "order_estimated_delivery_date",
]

print("Loading raw tables...")
orders = pd.read_csv(ECOM / "orders_dataset.csv", parse_dates=DATE_COLS_ORDERS)
items = pd.read_csv(ECOM / "order_items_dataset.csv", parse_dates=["shipping_limit_date"])
payments = pd.read_csv(ECOM / "order_payments_dataset.csv")
reviews = pd.read_csv(ECOM / "order_reviews_dataset.csv",
                      parse_dates=["review_creation_date", "review_answer_timestamp"])
products = pd.read_csv(ECOM / "products_dataset.csv")
customers = pd.read_csv(ECOM / "customers_dataset.csv")
sellers = pd.read_csv(ECOM / "sellers_dataset.csv")
geo = pd.read_csv(ECOM / "geolocation_dataset.csv")
cat_translation = pd.read_csv(ECOM / "product_category_name_translation.csv")
mql = pd.read_csv(MKT / "marketing_qualified_leads_dataset.csv", parse_dates=["first_contact_date"])
closed_deals = pd.read_csv(MKT / "closed_deals_dataset.csv", parse_dates=["won_date"])

# ---------------------------------------------------------------------------
# 1. Category name cleanup: translate to English, fall back to raw name /
#    "unknown" for the 2 categories missing from the translation table and
#    for products with a null category (1.9% of products).
# ---------------------------------------------------------------------------
products = products.merge(cat_translation, on="product_category_name", how="left")
products["category_english"] = (
    products["product_category_name_english"]
    .fillna(products["product_category_name"])
    .fillna("unknown")
    .str.replace("_", " ")
    .str.title()
)

# ---------------------------------------------------------------------------
# 2. Reviews: ~0.6% of orders have more than one review row (a customer left
#    a follow-up review). Keep the most recent one per order.
# ---------------------------------------------------------------------------
reviews_dedup = (
    reviews.sort_values("review_answer_timestamp")
    .drop_duplicates(subset="order_id", keep="last")
    .assign(has_review_comment=lambda d: d["review_comment_message"].notna())
    [["order_id", "review_score", "has_review_comment", "review_creation_date"]]
)

# ---------------------------------------------------------------------------
# 3. Payments: multiple installment rows per order -> collapse to one row.
# ---------------------------------------------------------------------------
pay_agg = payments.groupby("order_id").agg(
    payment_value=("payment_value", "sum"),
    max_installments=("payment_installments", "max"),
).reset_index()
# dominant payment type = the type with the largest payment_value within the order
dominant_type = (
    payments.sort_values("payment_value", ascending=False)
    .drop_duplicates(subset="order_id", keep="first")
    [["order_id", "payment_type"]]
    .rename(columns={"payment_type": "payment_type_dominant"})
)
pay_agg = pay_agg.merge(dominant_type, on="order_id", how="left")

# ---------------------------------------------------------------------------
# 4. Items joined with product + seller info (grain = order_item) -- this is
#    the fact table used for category- and seller-level drill-downs.
# ---------------------------------------------------------------------------
items_full = (
    items.merge(products[["product_id", "category_english", "product_weight_g"]],
                on="product_id", how="left")
    .merge(sellers, on="seller_id", how="left")
)
items_full["category_english"] = items_full["category_english"].fillna("Unknown")

orders_small = orders[["order_id", "customer_id", "order_status"] + DATE_COLS_ORDERS]
customers_small = customers[["customer_id", "customer_unique_id", "customer_city", "customer_state"]]

items_full = (
    items_full.merge(orders_small, on="order_id", how="left")
    .merge(customers_small, on="customer_id", how="left")
    .merge(reviews_dedup[["order_id", "review_score"]], on="order_id", how="left")
)

items_full["delivery_days"] = (
    items_full["order_delivered_customer_date"] - items_full["order_purchase_timestamp"]
).dt.total_seconds() / 86400
items_full["delay_days"] = (
    items_full["order_delivered_customer_date"] - items_full["order_estimated_delivery_date"]
).dt.total_seconds() / 86400
items_full["is_late"] = items_full["delay_days"] > 0
items_full["order_purchase_month"] = items_full["order_purchase_timestamp"].values.astype("datetime64[M]")

items_fact = items_full[[
    "order_id", "order_item_id", "product_id", "seller_id", "seller_state", "seller_city",
    "category_english", "price", "freight_value", "product_weight_g",
    "customer_id", "customer_state", "customer_city",
    "order_status", "order_purchase_timestamp", "order_purchase_month",
    "delivery_days", "delay_days", "is_late", "review_score",
]].rename(columns={"category_english": "category"})

items_fact.to_parquet(OUT / "items_fact.parquet", index=False)
print("items_fact:", items_fact.shape)

# ---------------------------------------------------------------------------
# 5. Orders fact table (grain = order) -- KPIs & overall delivery/satisfaction
#    trends. One row per order with items/payments/review rolled up.
# ---------------------------------------------------------------------------
item_agg = items.groupby("order_id").agg(
    n_items=("order_item_id", "count"),
    n_sellers=("seller_id", "nunique"),
    n_products=("product_id", "nunique"),
    total_price=("price", "sum"),
    total_freight=("freight_value", "sum"),
).reset_index()

# a single representative category per order = category of its highest-value item
top_item = items.merge(products[["product_id", "category_english"]], on="product_id", how="left")
top_item = (
    top_item.sort_values("price", ascending=False)
    .drop_duplicates(subset="order_id", keep="first")
    [["order_id", "category_english"]]
    .rename(columns={"category_english": "main_category"})
)
top_item["main_category"] = top_item["main_category"].fillna("Unknown")

orders_fact = (
    orders.merge(customers_small, on="customer_id", how="left")
    .merge(item_agg, on="order_id", how="left")
    .merge(top_item, on="order_id", how="left")
    .merge(pay_agg, on="order_id", how="left")
    .merge(reviews_dedup, on="order_id", how="left")
)

orders_fact["total_order_value"] = orders_fact["total_price"] + orders_fact["total_freight"]
orders_fact["delivery_days"] = (
    orders_fact["order_delivered_customer_date"] - orders_fact["order_purchase_timestamp"]
).dt.total_seconds() / 86400
orders_fact["promised_days"] = (
    orders_fact["order_estimated_delivery_date"] - orders_fact["order_purchase_timestamp"]
).dt.total_seconds() / 86400
orders_fact["delay_days"] = (
    orders_fact["order_delivered_customer_date"] - orders_fact["order_estimated_delivery_date"]
).dt.total_seconds() / 86400
orders_fact["is_late"] = orders_fact["delay_days"] > 0
orders_fact["is_delivered"] = orders_fact["order_status"] == "delivered"
orders_fact["satisfaction_bucket"] = np.select(
    [orders_fact["review_score"] <= 2, orders_fact["review_score"] == 3, orders_fact["review_score"] >= 4],
    ["Negative (1-2)", "Neutral (3)", "Positive (4-5)"],
    default=None,
)
orders_fact.loc[orders_fact["review_score"].isna(), "satisfaction_bucket"] = None
orders_fact["order_purchase_month"] = orders_fact["order_purchase_timestamp"].values.astype("datetime64[M]")

orders_fact.to_parquet(OUT / "orders_fact.parquet", index=False)
print("orders_fact:", orders_fact.shape)

# ---------------------------------------------------------------------------
# 6. Seller fact table (grain = seller) -- for the seller-risk view, enriched
#    with Marketing Funnel acquisition data where available (only ~380 of the
#    3095 active sellers appear in the closed_deals table -- a coverage
#    limitation called out explicitly in the dashboard/report).
# ---------------------------------------------------------------------------
seller_items = items_fact.merge(
    orders_fact[["order_id", "review_score"]].rename(columns={"review_score": "order_review_score"}),
    on="order_id", how="left",
)
seller_agg = seller_items.groupby("seller_id").agg(
    n_orders=("order_id", "nunique"),
    n_items=("order_item_id", "count"),
    total_revenue=("price", "sum"),
    avg_price=("price", "mean"),
    avg_review_score=("review_score", "mean"),
    pct_negative_reviews=("review_score", lambda s: (s <= 2).mean()),
    late_rate=("is_late", "mean"),
    avg_delivery_days=("delivery_days", "mean"),
    n_categories=("category", "nunique"),
).reset_index()
top_cat_by_seller = (
    seller_items.groupby(["seller_id", "category"]).size().reset_index(name="n")
    .sort_values("n", ascending=False).drop_duplicates("seller_id")
    [["seller_id", "category"]].rename(columns={"category": "top_category"})
)
seller_state = sellers[["seller_id", "seller_state", "seller_city"]]
seller_agg = (
    seller_agg.merge(seller_state, on="seller_id", how="left")
    .merge(top_cat_by_seller, on="seller_id", how="left")
)

deals_mql = closed_deals.merge(mql[["mql_id", "origin", "first_contact_date"]], on="mql_id", how="left")
deals_mql = deals_mql[["seller_id", "origin", "business_segment", "lead_type", "won_date"]].rename(
    columns={"origin": "acquisition_channel"}
)
seller_agg = seller_agg.merge(deals_mql, on="seller_id", how="left")
seller_agg["has_marketing_data"] = seller_agg["acquisition_channel"].notna()

seller_agg.to_parquet(OUT / "seller_fact.parquet", index=False)
print("seller_fact:", seller_agg.shape, " | with marketing-funnel match:", seller_agg["has_marketing_data"].sum())

# ---------------------------------------------------------------------------
# 7. State centroids for the map view -- median lat/lon per state, clipped to
#    a rough Brazil bounding box to drop clearly erroneous geocodes.
# ---------------------------------------------------------------------------
geo_clean = geo[
    geo["geolocation_lat"].between(-34, 6) & geo["geolocation_lng"].between(-74, -33)
]
state_geo = geo_clean.groupby("geolocation_state").agg(
    lat=("geolocation_lat", "median"),
    lon=("geolocation_lng", "median"),
).reset_index().rename(columns={"geolocation_state": "state"})
state_geo.to_parquet(OUT / "state_geo.parquet", index=False)
print("state_geo:", state_geo.shape)

# ---------------------------------------------------------------------------
# 8. Metadata for dashboard filter widgets + a short data-quality note.
# ---------------------------------------------------------------------------
meta = {
    "date_min": str(orders_fact["order_purchase_timestamp"].min().date()),
    "date_max": str(orders_fact["order_purchase_timestamp"].max().date()),
    "categories": sorted(orders_fact["main_category"].dropna().unique().tolist()),
    "customer_states": sorted(orders_fact["customer_state"].dropna().unique().tolist()),
    "seller_states": sorted(seller_agg["seller_state"].dropna().unique().tolist()),
    "n_orders_total": int(len(orders_fact)),
    "n_orders_delivered": int(orders_fact["is_delivered"].sum()),
    "n_orders_with_review": int(orders_fact["review_score"].notna().sum()),
    "n_sellers": int(len(seller_agg)),
    "n_sellers_with_marketing_data": int(seller_agg["has_marketing_data"].sum()),
    "data_quality_notes": [
        "2.6% of orders (2,965) have no delivered-customer date -- mostly canceled/unavailable/shipped orders; delivery-time and lateness metrics are computed only over delivered orders with both dates present.",
        "547 orders had more than one review row; the most recent review per order was kept.",
        "1.9% of products have no category; these are labeled 'Unknown' rather than dropped.",
        "Only 380 of 3,095 sellers with at least one order also appear in the Marketing Funnel closed_deals table, so acquisition-channel analysis covers ~12% of sellers -- treated as a directional, not comprehensive, view.",
        "Order-level review scores are attached to every item in an order for category/seller rollups, since Olist reviews are per-order, not per-item -- a shared-blame caveat noted in the report.",
    ],
}
with open(OUT / "meta.json", "w") as f:
    json.dump(meta, f, indent=2)

print("\nDone. Files in", OUT)
for p in sorted(OUT.iterdir()):
    print(" -", p.name)
