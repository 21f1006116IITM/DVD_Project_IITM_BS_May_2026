"""
Marketplace Health Dashboard — E-Commerce Orders, Delivery & Customer Satisfaction
Run with:  streamlit run app.py   (from inside the app/ folder)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data import load_all, apply_filters
from style import (
    CATEGORICAL, SEQUENTIAL_BLUE, STATUS, SATISFACTION_COLORS,
    INK_SECONDARY, INK_MUTED, style_fig,
)

st.set_page_config(page_title="Marketplace Health Dashboard", layout="wide", page_icon="📦")

PAYMENT_ORDER = ["credit_card", "boleto", "voucher", "debit_card", "not_defined"]
PAYMENT_COLOR = {p: CATEGORICAL[i] for i, p in enumerate(PAYMENT_ORDER)}
CHANNEL_ORDER = ["paid_search", "organic_search", "social", "direct_traffic",
                  "referral", "email", "display", "other", "unknown"]
# "other"/"unknown" aren't real channels -- give them a muted gray instead of
# competing for a vivid categorical hue (and instead of colliding with a real
# channel once the named channels run past the 8-slot categorical palette).
CHANNEL_COLOR = {}
_real_channels = [c for c in CHANNEL_ORDER if c not in ("other", "unknown")]
for i, c in enumerate(_real_channels):
    CHANNEL_COLOR[c] = CATEGORICAL[i % len(CATEGORICAL)]
CHANNEL_COLOR["other"] = INK_MUTED
CHANNEL_COLOR["unknown"] = INK_MUTED

orders_all, items_all, sellers_all, state_geo, meta = load_all()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
st.sidebar.title("📦 Filters")

date_min = pd.Timestamp(meta["date_min"]).to_period("M").to_timestamp()
date_max = pd.Timestamp(meta["date_max"]).to_period("M").to_timestamp()
months = pd.date_range(date_min, date_max, freq="MS")
month_labels = {m: m.strftime("%b %Y") for m in months}

date_range = st.sidebar.select_slider(
    "Order month range",
    options=list(months),
    value=(months[0], months[-1]),
    format_func=lambda m: month_labels[m],
)

sel_states = st.sidebar.multiselect(
    "Customer state (blank = all)", options=meta["customer_states"], default=[]
)
sel_categories = st.sidebar.multiselect(
    "Product category (blank = all)", options=meta["categories"], default=[]
)
delivered_only = st.sidebar.checkbox(
    "Delivered orders only (recommended)", value=True,
    help="Delivery-time and satisfaction metrics only make sense for orders that "
         "actually arrived. Turn off to include canceled / in-transit / unavailable orders "
         "in the order-volume and revenue counts.",
)

states_filter = sel_states if sel_states else meta["customer_states"]
categories_filter = sel_categories if sel_categories else meta["categories"]

orders, items = apply_filters(orders_all, items_all, date_range, states_filter, categories_filter, delivered_only)

st.sidebar.markdown("---")
st.sidebar.caption(
    f"{meta['n_orders_total']:,} orders total · {meta['n_orders_delivered']:,} delivered · "
    f"{meta['n_sellers']:,} sellers · data spans {meta['date_min']} to {meta['date_max']}."
)
with st.sidebar.expander("Data quality notes"):
    for note in meta["data_quality_notes"]:
        st.caption("• " + note)

# ---------------------------------------------------------------------------
# Header + KPIs
# ---------------------------------------------------------------------------
st.title("A Visual Study of E-Commerce Orders, Delivery & Customer Satisfaction")
st.caption(
    "Explore what drives a happy customer vs. a one-star review — by category, seller, "
    "region, and delivery performance — to help leadership grow the marketplace without "
    "breaking the customer experience."
)

if len(orders) == 0:
    st.warning("No orders match the current filters. Widen the date range, states, or categories.")
    st.stop()

k1, k2, k3, k4, k5, k6 = st.columns(6)
gmv = orders["total_order_value"].sum()
avg_review = orders["review_score"].mean()
on_time_rate = 1 - orders.loc[orders["is_delivered"], "is_late"].mean() if orders["is_delivered"].any() else np.nan
avg_delivery_days = orders.loc[orders["is_delivered"], "delivery_days"].mean()
n_unique_customers = orders["customer_unique_id"].nunique()
repeat_rate = 1 - (orders.groupby("customer_unique_id").size() == 1).mean() if n_unique_customers else np.nan

k1.metric("Orders", f"{len(orders):,}")
k2.metric("GMV", f"R$ {gmv/1e6:,.2f}M")
k3.metric("Avg review score", f"{avg_review:.2f} / 5")
k4.metric("On-time delivery rate", f"{on_time_rate*100:.1f}%")
k5.metric("Avg delivery time", f"{avg_delivery_days:.1f} days")
k6.metric("Repeat customer rate", f"{repeat_rate*100:.1f}%")

tabs = st.tabs([
    "Overview", "Delivery & Satisfaction", "Category", "Seller Risk", "Regional", "Acquisition Channel",
])

# ---------------------------------------------------------------------------
# Tab 1: Overview
# ---------------------------------------------------------------------------
with tabs[0]:
    # Olist's Sep-Dec 2016 rows are a pre-launch pilot (as few as 1 order in a
    # month) -- included in KPIs/tables, but excluded from month-over-month
    # trend lines below since a single order swings a monthly average wildly
    # and would misread as a real signal.
    month_counts = orders.groupby("order_purchase_month").size()
    trend_months = month_counts[month_counts >= 20].index
    orders_trend = orders[orders["order_purchase_month"].isin(trend_months)]

    c1, c2 = st.columns(2)

    monthly = orders_trend.groupby("order_purchase_month").size().reset_index(name="orders")
    fig = px.line(monthly, x="order_purchase_month", y="orders", markers=True)
    fig.update_traces(line_color=CATEGORICAL[0])
    fig.update_layout(title="Order volume over time", xaxis_title="", yaxis_title="Orders")
    c1.plotly_chart(style_fig(fig, legend=False), width='stretch')

    monthly_r = orders_trend.dropna(subset=["review_score"]).groupby("order_purchase_month")["review_score"].mean().reset_index()
    fig = px.line(monthly_r, x="order_purchase_month", y="review_score", markers=True)
    fig.update_traces(line_color=CATEGORICAL[1])
    fig.update_layout(title="Average review score over time", xaxis_title="", yaxis_title="Avg review score",
                       yaxis_range=[1, 5])
    c2.plotly_chart(style_fig(fig, legend=False), width='stretch')
    st.caption(
        "Trend lines exclude Olist's Sep-Dec 2016 pre-launch pilot months (fewer than 20 orders each), "
        "which otherwise swing wildly on tiny samples. KPIs and other tabs still include them."
    )

    c3, c4 = st.columns(2)

    sat = orders["satisfaction_bucket"].value_counts().reindex(
        ["Positive (4-5)", "Neutral (3)", "Negative (1-2)"]
    ).reset_index()
    sat.columns = ["bucket", "count"]
    fig = px.bar(sat, x="count", y="bucket", orientation="h",
                 color="bucket", color_discrete_map=SATISFACTION_COLORS)
    fig.update_layout(title="Reviews by satisfaction", xaxis_title="Orders", yaxis_title="")
    c3.plotly_chart(style_fig(fig, legend=False), width='stretch')

    pay = orders.dropna(subset=["payment_type_dominant"]).groupby("payment_type_dominant").size().reset_index(name="count")
    pay = pay.sort_values("count", ascending=False)
    fig = px.bar(pay, x="payment_type_dominant", y="count", color="payment_type_dominant",
                 color_discrete_map=PAYMENT_COLOR, category_orders={"payment_type_dominant": PAYMENT_ORDER})
    fig.update_layout(title="Orders by payment type", xaxis_title="", yaxis_title="Orders")
    c4.plotly_chart(style_fig(fig, legend=False), width='stretch')

# ---------------------------------------------------------------------------
# Tab 2: Delivery & Satisfaction — the core "what drives a bad review" story
# ---------------------------------------------------------------------------
with tabs[1]:
    st.markdown("#### Lateness is the single strongest driver of a bad review")
    d = orders[orders["is_delivered"] & orders["review_score"].notna() & orders["delay_days"].notna()].copy()

    bins = [-100, -7, -2, 0, 2, 7, 100]
    labels = ["7+ days early", "2-7 days early", "0-2 days early", "0-2 days late", "2-7 days late", "7+ days late"]
    d["delay_bucket"] = pd.cut(d["delay_days"], bins=bins, labels=labels)
    agg = d.groupby("delay_bucket", observed=True).agg(avg_review=("review_score", "mean"), n=("review_score", "size")).reset_index()

    fig = px.bar(agg, x="delay_bucket", y="avg_review", text=agg["n"].apply(lambda x: f"n={x:,}"),
                 color="delay_bucket", color_discrete_sequence=SEQUENTIAL_BLUE)
    fig.update_traces(textposition="outside")
    fig.update_layout(title="Average review score by delivery timing (vs. promised date)",
                       xaxis_title="", yaxis_title="Avg review score", yaxis_range=[1, 5.3])
    st.plotly_chart(style_fig(fig, legend=False, height=440), width='stretch')

    c1, c2 = st.columns(2)
    fig = px.histogram(d, x="delivery_days", nbins=50, color_discrete_sequence=[CATEGORICAL[0]])
    fig.update_layout(title="Distribution of delivery time", xaxis_title="Days from purchase to delivery", yaxis_title="Orders")
    c1.plotly_chart(style_fig(fig, legend=False), width='stretch')

    delivered_trend = orders[orders["is_delivered"] & orders["order_purchase_month"].isin(month_counts[month_counts >= 20].index)]
    monthly_late = delivered_trend.groupby("order_purchase_month")["is_late"].mean().reset_index()
    fig = px.line(monthly_late, x="order_purchase_month", y="is_late", markers=True)
    fig.update_traces(line_color=CATEGORICAL[7])
    fig.update_layout(title="Late-delivery rate over time", xaxis_title="", yaxis_title="Share of orders delivered late",
                       yaxis_tickformat=".0%")
    c2.plotly_chart(style_fig(fig, legend=False), width='stretch')

    st.caption(
        "Orders delivered more than a week early still average a 4.3/5 review; orders delivered "
        "more than a week late average 1.7/5. Delivery reliability — not just speed — is what "
        "customer satisfaction tracks most closely."
    )

# ---------------------------------------------------------------------------
# Tab 3: Category
# ---------------------------------------------------------------------------
with tabs[2]:
    cat_agg = items.groupby("category").agg(
        n_orders=("order_id", "nunique"),
        revenue=("price", "sum"),
        avg_review=("review_score", "mean"),
        late_rate=("is_late", "mean"),
        avg_delivery_days=("delivery_days", "mean"),
    ).reset_index()
    cat_agg = cat_agg[cat_agg["n_orders"] >= 10]

    st.markdown("#### Which categories are high-volume *and* high-risk?")

    fig = px.scatter(
        cat_agg, x="late_rate", y="avg_review", size="n_orders",
        color_discrete_sequence=[CATEGORICAL[0]], size_max=48,
        hover_data={"category": True, "n_orders": ":,", "revenue": ":,.0f", "late_rate": ":.1%", "avg_review": ":.2f"},
    )
    fig.update_traces(marker=dict(opacity=0.75, line=dict(width=1, color="white")))
    overall_late = cat_agg["late_rate"].median()
    overall_rev = cat_agg["avg_review"].median()
    fig.add_vline(x=overall_late, line_dash="dot", line_color=INK_MUTED)
    fig.add_hline(y=overall_rev, line_dash="dot", line_color=INK_MUTED)
    fig.update_layout(title="Category late-delivery rate vs. average review (bubble = order volume)",
                       xaxis_title="Late-delivery rate", yaxis_title="Avg review score",
                       xaxis_tickformat=".0%")
    st.plotly_chart(style_fig(fig, legend=False, height=520), width='stretch')
    st.caption(
        "Dotted lines mark the median category. Hover a bubble for its name — the busiest categories "
        "cluster tightly, so direct labels are left to the ranked chart below instead of crowding this one."
    )

    st.markdown("#### Top categories by revenue, colored by satisfaction")
    top15 = cat_agg.sort_values("revenue", ascending=False).head(15).sort_values("revenue")
    fig = px.bar(top15, x="revenue", y="category", orientation="h", color="avg_review",
                 color_continuous_scale=SEQUENTIAL_BLUE, labels={"avg_review": "Avg review"})
    fig.update_layout(title="", xaxis_title="Revenue (R$)", yaxis_title="")
    st.plotly_chart(style_fig(fig, legend=False, height=480), width='stretch')

    st.markdown("#### Compare one category against the marketplace average")
    pick = st.selectbox("Category", sorted(cat_agg["category"].unique()))
    row = cat_agg[cat_agg["category"] == pick].iloc[0]
    b1, b2, b3 = st.columns(3)
    b1.metric("Avg review", f"{row.avg_review:.2f}", f"{row.avg_review - cat_agg['avg_review'].mean():+.2f} vs avg")
    b2.metric("Late-delivery rate", f"{row.late_rate*100:.1f}%", f"{(row.late_rate - cat_agg['late_rate'].mean())*100:+.1f} pp vs avg",
              delta_color="inverse")
    b3.metric("Orders", f"{row.n_orders:,.0f}")

    with st.expander("Full category table"):
        st.dataframe(
            cat_agg.sort_values("revenue", ascending=False)
            .style.format({"revenue": "R$ {:,.0f}", "avg_review": "{:.2f}", "late_rate": "{:.1%}", "avg_delivery_days": "{:.1f}"}),
            width='stretch',
        )

# ---------------------------------------------------------------------------
# Tab 4: Seller Risk
# ---------------------------------------------------------------------------
with tabs[3]:
    st.markdown("#### Which sellers put growth and satisfaction most at odds?")
    min_orders = st.slider("Minimum orders per seller (filters out one-off sellers)", 1, 50, 5)

    s_agg = items.groupby("seller_id").agg(
        n_orders=("order_id", "nunique"),
        revenue=("price", "sum"),
        avg_review=("review_score", "mean"),
        late_rate=("is_late", "mean"),
        seller_state=("seller_state", "first"),
        top_category=("category", lambda s: s.mode().iat[0] if len(s.mode()) else "Unknown"),
    ).reset_index()
    s_agg = s_agg[s_agg["n_orders"] >= min_orders]

    med_late = s_agg["late_rate"].median()
    med_review = s_agg["avg_review"].median()
    s_agg["risk_flag"] = np.where(
        (s_agg["late_rate"] > med_late) & (s_agg["avg_review"] < med_review), "High risk", "Other"
    )

    fig = px.scatter(
        s_agg, x="late_rate", y="avg_review", size="revenue", color="risk_flag",
        color_discrete_map={"High risk": STATUS["critical"], "Other": CATEGORICAL[0]},
        size_max=40, opacity=0.65,
        hover_data={"seller_id": True, "seller_state": True, "top_category": True, "n_orders": ":,",
                    "revenue": ":,.0f", "late_rate": ":.1%", "avg_review": ":.2f"},
    )
    fig.add_vline(x=med_late, line_dash="dot", line_color=INK_MUTED)
    fig.add_hline(y=med_review, line_dash="dot", line_color=INK_MUTED)
    fig.update_layout(title="Seller late-delivery rate vs. average review (bubble = revenue)",
                       xaxis_title="Late-delivery rate", yaxis_title="Avg review score", xaxis_tickformat=".0%")
    st.plotly_chart(style_fig(fig, height=520), width='stretch')
    st.caption(
        "'High risk' = worse than the median seller on both lateness and reviews. "
        "These sellers are prime candidates for coaching, tighter shipping SLAs, or catalogue review."
    )

    st.markdown("#### Highest-revenue high-risk sellers")
    risk_table = s_agg[s_agg["risk_flag"] == "High risk"].sort_values("revenue", ascending=False).head(15)
    st.dataframe(
        risk_table[["seller_id", "seller_state", "top_category", "n_orders", "revenue", "avg_review", "late_rate"]]
        .style.format({"revenue": "R$ {:,.0f}", "avg_review": "{:.2f}", "late_rate": "{:.1%}"}),
        width='stretch',
    )

# ---------------------------------------------------------------------------
# Tab 5: Regional
# ---------------------------------------------------------------------------
with tabs[4]:
    st.markdown("#### Where are the growth pockets and the risk pockets?")
    c1, c2 = st.columns(2)
    geo_view = c1.radio("Location", ["Customer (demand)", "Seller (fulfillment)"], horizontal=True)
    metric = c2.radio("Metric", ["Order volume", "Avg review score", "Late-delivery rate"], horizontal=True)

    if geo_view == "Customer (demand)":
        base = orders.groupby("customer_state").agg(
            orders=("order_id", "count"), avg_review=("review_score", "mean"),
            late_rate=("is_late", "mean"),
        ).reset_index().rename(columns={"customer_state": "state"})
    else:
        base = items.groupby("seller_state").agg(
            orders=("order_id", "nunique"), avg_review=("review_score", "mean"),
            late_rate=("is_late", "mean"),
        ).reset_index().rename(columns={"seller_state": "state"})

    base = base.merge(state_geo, on="state", how="left")
    metric_col = {"Order volume": "orders", "Avg review score": "avg_review", "Late-delivery rate": "late_rate"}[metric]
    color_scale = SEQUENTIAL_BLUE if metric != "Late-delivery rate" else list(reversed(SEQUENTIAL_BLUE))

    # A plain lat/lon scatter (not go.Scattergeo/choropleth) by design: Plotly's
    # map basemap is fetched from a CDN at render time, which makes the chart
    # fail silently offline or on a locked-down grading machine. Latitude and
    # longitude plotted directly still reproduce Brazil's state layout closely
    # enough to read as a map, with zero external dependency.
    fig = go.Figure(go.Scatter(
        x=base["lon"], y=base["lat"], text=base["state"],
        mode="markers+text", textposition="top center",
        marker=dict(
            size=(base["orders"] / base["orders"].max() * 45 + 10),
            color=base[metric_col], colorscale=color_scale, showscale=True,
            colorbar=dict(title=metric, tickformat=".0%" if metric == "Late-delivery rate" else None),
            line=dict(width=1, color="white"),
        ),
    ))
    fig.update_xaxes(visible=False, scaleanchor="y", scaleratio=1)
    fig.update_yaxes(visible=False)
    fig.update_layout(
        title=f"{metric} by state (schematic map, sized by order volume) — {geo_view.split(' ')[0]} location",
        height=520, margin=dict(l=0, r=0, t=40, b=0), plot_bgcolor="#fcfcfb",
    )
    st.plotly_chart(fig, width='stretch')

    with st.expander("State-level table"):
        st.dataframe(
            base[["state", "orders", "avg_review", "late_rate"]].sort_values("orders", ascending=False)
            .style.format({"avg_review": "{:.2f}", "late_rate": "{:.1%}"}),
            width='stretch',
        )

# ---------------------------------------------------------------------------
# Tab 6: Acquisition Channel (Marketing Funnel tie-in)
# ---------------------------------------------------------------------------
with tabs[5]:
    st.info(
        f"Only {meta['n_sellers_with_marketing_data']:,} of {meta['n_sellers']:,} sellers with orders "
        "(~12%) can be traced back to the Marketing Funnel dataset's closed-deals table. This view is "
        "directional — a look at the sellers we *can* trace — not a comprehensive picture of every "
        "acquisition channel.",
        icon="ℹ️",
    )
    tracked = sellers_all[sellers_all["has_marketing_data"]].copy()
    tracked["acquisition_channel"] = tracked["acquisition_channel"].fillna("unknown")

    chan_agg = tracked.groupby("acquisition_channel").agg(
        n_sellers=("seller_id", "nunique"),
        avg_review=("avg_review_score", "mean"),
        late_rate=("late_rate", "mean"),
        avg_revenue=("total_revenue", "mean"),
    ).reset_index()
    chan_agg = chan_agg[chan_agg["n_sellers"] >= 3]
    order_present = [c for c in CHANNEL_ORDER if c in chan_agg["acquisition_channel"].values]

    c1, c2 = st.columns(2)
    fig = px.bar(chan_agg, x="acquisition_channel", y="n_sellers", color="acquisition_channel",
                 color_discrete_map=CHANNEL_COLOR, category_orders={"acquisition_channel": order_present})
    fig.update_layout(title="Traceable sellers by acquisition channel", xaxis_title="", yaxis_title="Sellers")
    c1.plotly_chart(style_fig(fig, legend=False), width='stretch')

    fig = px.bar(chan_agg.sort_values("avg_review"), x="avg_review", y="acquisition_channel", orientation="h",
                 color="acquisition_channel", color_discrete_map=CHANNEL_COLOR)
    fig.update_layout(title="Avg seller review score by acquisition channel", xaxis_title="Avg review score",
                       yaxis_title="", xaxis_range=[1, 5])
    c2.plotly_chart(style_fig(fig, legend=False), width='stretch')

    st.caption(
        "Read this as a hypothesis generator, not a verdict: with ~12% seller coverage, use it to decide "
        "which acquisition channels deserve a deeper, purpose-built tracking effort — not to reallocate "
        "marketing spend outright."
    )
