"""Generate a synthetic sales CSV with KNOWN planted insights (ground truth for evaluation)."""
import numpy as np
import pandas as pd
import json
import sys

rng = np.random.default_rng(42)
N = 8000
dates = pd.to_datetime("2023-01-01") + pd.to_timedelta(rng.integers(0, 731, N), unit="D")
dates = pd.Series(dates).sort_values().reset_index(drop=True)

regions = rng.choice(["West", "North", "South", "East", "Central"], N, p=[0.40, 0.18, 0.16, 0.14, 0.12])
channels = rng.choice(["Online", "Store", "Partner"], N, p=[0.5, 0.35, 0.15])
cats = rng.choice(["Electronics", "Furniture", "Office", "Clothing"], N, p=[0.3, 0.25, 0.25, 0.2])
base_price = {"Electronics": 450, "Furniture": 300, "Office": 40, "Clothing": 60}
unit_price = np.array([base_price[c] for c in cats]) * rng.lognormal(0, 0.35, N)

discount = np.round(rng.choice([0, 0.05, 0.1, 0.15, 0.2, 0.3], N, p=[.3, .2, .2, .12, .1, .08]), 2)
quantity = np.maximum(1, np.round(rng.poisson(2 + discount * 20))).astype(int)  # P4 discount -> quantity
bulk = rng.choice(N, 12, replace=False)
quantity[bulk] = rng.integers(150, 300, 12)  # P10 outliers

# P1 trend & P2 December seasonality via multiplier on quantity/price
t = (dates - dates.min()).dt.days.values / 730
mult = 1 + 0.45 * t
mult = mult * np.where(dates.dt.month.values == 12, 1.8, 1.0)
# P6 Furniture drop from 2024-07
fur_drop = (cats == "Furniture") & (dates.values >= np.datetime64("2024-07-01"))
mult = mult * np.where(fur_drop, 0.45, 1.0)
revenue = np.round(unit_price * quantity * (1 - discount) * mult, 2)

reps = np.array([f"Rep_{i:02d}" for i in range(30)])
rep_p = np.ones(30); rep_p[:3] = 6; rep_p /= rep_p.sum()  # P12 concentration in top reps
sales_rep = rng.choice(reps, N, p=rep_p)

ret_p = np.where(channels == "Online", 0.18, 0.06)  # P5
returned = (rng.random(N) < ret_p).astype(int)
sat = np.clip(np.round(rng.normal(4.1, 0.7, N) - returned * 1.4), 1, 5).astype(int)  # P7
age = rng.normal(38, 11, N).round().clip(18, 80)
age[rng.random(N) < 0.15] = np.nan  # P8

df = pd.DataFrame({
    "order_id": [f"ORD{100000+i}" for i in range(N)],
    "order_date": dates.dt.strftime("%Y-%m-%d"),
    "region": regions, "channel": channels, "category": cats, "sales_rep": sales_rep,
    "unit_price": unit_price.round(2), "quantity": quantity, "discount": discount,
    "revenue": revenue, "customer_age": age, "satisfaction": sat, "returned": returned,
    "country": "VN",  # P11 constant
})
df = pd.concat([df, df.sample(50, random_state=1)], ignore_index=True)  # P9 duplicates
out = sys.argv[1] if len(sys.argv) > 1 else "sales_synthetic.csv"
df.to_csv(out, index=False)

truth = {
    "P1_trend": {"kind": "trend", "cols": ["revenue", "order_date"]},
    "P2_december": {"kind": "seasonality", "cols": ["revenue", "order_date"]},
    "P3_west_dominant": {"kind": "dominance", "cols": ["region", "revenue"], "value": "West"},
    "P4_discount_qty": {"kind": "correlation", "cols": ["discount", "quantity"]},
    "P5_online_returns": {"kind": "group_diff", "cols": ["channel", "returned"], "value": "Online"},
    "P6_furniture_drop": {"kind": "change_point", "cols": ["category", "revenue"], "value": "Furniture"},
    "P7_returned_satisfaction": {"kind": "group_diff", "cols": ["returned", "satisfaction"]},
    "P8_age_missing": {"kind": "missing", "cols": ["customer_age"]},
    "P9_duplicates": {"kind": "duplicates", "cols": []},
    "P10_qty_outliers": {"kind": "outliers", "cols": ["quantity"]},
    "P11_constant": {"kind": "constant", "cols": ["country"]},
    "P12_rep_concentration": {"kind": "concentration", "cols": ["sales_rep", "revenue"]},
    "P13_price_by_category": {"kind": "group_diff", "cols": ["category", "unit_price"]},
}
json.dump(truth, open(out.replace(".csv", "_truth.json"), "w"), indent=2)
print(df.shape)
