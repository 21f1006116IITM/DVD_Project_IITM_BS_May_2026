"""Data loading + filtering for the dashboard."""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@st.cache_data
def load_all():
    orders = pd.read_parquet(DATA_DIR / "orders_fact.parquet")
    items = pd.read_parquet(DATA_DIR / "items_fact.parquet")
    sellers = pd.read_parquet(DATA_DIR / "seller_fact.parquet")
    state_geo = pd.read_parquet(DATA_DIR / "state_geo.parquet")
    with open(DATA_DIR / "meta.json") as f:
        meta = json.load(f)
    return orders, items, sellers, state_geo, meta


def apply_filters(orders, items, date_range, states, categories, delivered_only):
    start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])

    o = orders[
        orders["order_purchase_month"].between(start, end)
        & (orders["customer_state"].isin(states) if states else True)
        & (orders["main_category"].isin(categories) if categories else True)
    ]
    if delivered_only:
        o = o[o["is_delivered"]]

    i = items[
        items["order_purchase_month"].between(start, end)
        & (items["customer_state"].isin(states) if states else True)
        & (items["category"].isin(categories) if categories else True)
    ]
    if delivered_only:
        i = i[i["order_status"] == "delivered"]

    return o, i
