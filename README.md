# Marketplace Health Dashboard

A Visual Study of E-Commerce Orders, Delivery & Customer Satisfaction — built on
the Olist Brazilian E-Commerce dataset plus the Marketing Funnel dataset.

## Quick start

```bash
pip install -r requirements.txt
cd app
streamlit run app.py
```

Opens at `http://localhost:8501`. The dashboard reads the pre-built tables in
`data/`, so it starts instantly — no need to re-run the data pipeline unless
you've changed the raw data or the cleaning logic.

## Project structure

```
├── raw_data/                    # place the raw Olist + Marketing Funnel CSVs here (not shipped — see below)
│   └── Project Dataset/
│       ├── E-Commerce Dataset/
│       └── Marketing Funnel/
├── scripts/
│   ├── profile_data.py          # initial data profiling (schemas, missingness, cardinalities)
│   └── build_dataset.py         # cleans, merges, and derives the analytical tables
├── data/                        # output of build_dataset.py (already included, ready to use)
│   ├── orders_fact.parquet      # grain = order   → KPIs, delivery/satisfaction trends
│   ├── items_fact.parquet       # grain = order item → category & seller drill-down
│   ├── seller_fact.parquet      # grain = seller  → seller risk & acquisition channel
│   ├── state_geo.parquet        # state centroid lat/lon for the regional map
│   └── meta.json                # filter option lists + data-quality notes
├── app/
│   ├── app.py                   # Streamlit app (6 tabs, sidebar filters, KPI row)
│   ├── data.py                  # cached loading + filtering
│   └── style.py                 # shared color palette (colorblind-validated) & chart chrome
└── requirements.txt
```

`raw_data/` isn't included in this package to keep it lightweight — the
dashboard runs entirely off the `data/` parquet files. To reproduce the
pipeline from scratch: extract the original dataset zip into `raw_data/`
matching the structure above, then run:

```bash
python scripts/profile_data.py     # optional — prints the data profiling this was built on
python scripts/build_dataset.py    # rebuilds everything in data/
```

## What's in the dashboard

Sidebar filters (order month range, customer state, product category, and a
"delivered orders only" toggle) apply across all six tabs:

1. **Overview** — KPI row (orders, GMV, avg review, on-time rate, avg delivery
   time, repeat-customer rate) plus order volume, review-score, payment-type,
   and satisfaction-mix trends.
2. **Delivery & Satisfaction** — the central finding: average review score by
   how early/late an order arrived vs. its promised date. Orders 7+ days
   early average 4.3/5; orders 7+ days late average 1.7/5. Delivery
   *reliability*, not raw speed, is what satisfaction tracks most closely.
3. **Category** — which product categories are both high-volume and
   high-risk (late + poorly reviewed), plus a one-click comparison of any
   category against the marketplace average.
4. **Seller Risk** — a late-rate vs. review-score scatter (bubble = revenue)
   flagging sellers worse than the median on both axes, with a ranked table
   of the highest-revenue offenders — the sellers most worth coaching or
   holding to tighter SLAs.
5. **Regional** — a dependency-free schematic map (plain lat/lon scatter, not
   a tile-based map — see note below) of order volume, review score, and
   late-delivery rate by state, for both customer demand and seller
   fulfillment locations.
6. **Acquisition Channel** — ties in the Marketing Funnel dataset: seller
   performance by how they were acquired. Coverage caveat: only ~12% of
   active sellers can be traced to a closed deal, so this tab is explicitly
   framed as a hypothesis generator, not a verdict.

## Data quality notes (see also `data/meta.json`)

- 2.6% of orders have no delivered-customer date (mostly canceled/unavailable/
  still-shipping orders); delivery-time and lateness metrics are computed only
  over delivered orders with both dates present.
- 547 orders had more than one review row; the most recent review per order
  was kept.
- 1.9% of products have no category; labeled "Unknown" rather than dropped.
- Only 380 of 3,095 sellers with orders also appear in the Marketing Funnel's
  closed-deals table — the Acquisition Channel tab is directional, not
  comprehensive.
- Order-level review scores are attached to every item in that order for
  category/seller rollups, since Olist reviews are per-order, not per-item —
  a shared-blame caveat worth stating explicitly in the report.
- Olist's Sep–Dec 2016 rows are a pre-launch pilot (as few as 1 order in a
  month); included in KPIs and tables but excluded from the month-over-month
  trend lines, which would otherwise swing wildly on a handful of orders.
- The **late-delivery rate over time** chart shows a sharp spike around
  Apr–May 2018 — that lines up with Brazil's nationwide trucker strike
  (a real logistics shock, not a data error), worth a callout in the report.

## Design choices worth explaining in your write-up

- **Why Streamlit + Plotly**: fastest path from pandas to an interactive,
  filterable dashboard in pure Python — no separate BI tool license, and easy
  to read/modify/re-run for the technical appendix.
- **Why a plain-scatter "map" instead of a real choropleth**: Plotly's
  geographic chart types (`Scattergeo`/`Choropleth`) fetch their base map
  tiles from a CDN at render time. That's a silent failure risk on a
  locked-down grading machine or offline demo, so the regional view plots
  state centroids' latitude/longitude directly — no basemap, no network
  dependency, and it still reads clearly as Brazil's state layout.
- **Color palette**: every chart uses one fixed, colorblind-validated palette
  (`app/style.py`) — a fixed-order categorical set, a single-hue sequential
  ramp for magnitude, and reserved status colors (green/amber/red) only for
  actual satisfaction state — rather than each chart improvising its own
  colors.
