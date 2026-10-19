"""Hold-out synthetic HR dataset with planted insights (not used for tuning)."""
import json
import sys
import numpy as np
import pandas as pd

rng = np.random.default_rng(2026)
N = 5000
dept_div = {"Sales": "Commercial", "Marketing": "Commercial", "Engineering": "Tech", "Data": "Tech",
            "Support": "Operations", "Finance": "Operations"}
dept = rng.choice(list(dept_div), N, p=[.25, .1, .25, .1, .2, .1])
division = np.array([dept_div[d] for d in dept])                       # H8 hierarchy
base_sal = {"Sales": 18, "Marketing": 20, "Engineering": 32, "Data": 35, "Support": 12, "Finance": 22}
salary = np.round(np.array([base_sal[d] for d in dept]) * rng.lognormal(0, 0.2, N), 1)  # H3 (million VND)
age = rng.integers(22, 60, N)
tenure = np.clip(np.round((age - 22) * rng.uniform(0.1, 0.6, N) + rng.normal(0, 1, N), 1), 0, None)  # H4
overtime = rng.choice(["Yes", "No"], N, p=[.3, .7])
logit = -2.2 + 1.3 * (overtime == "Yes") - 0.05 * (salary - 20) - 0.08 * tenure
churn = (rng.random(N) < 1 / (1 + np.exp(-logit))).astype(int)        # H1, H2
# hire dates: growth over time (H6), almost no weekend hires (H5)
days = pd.date_range("2021-01-01", "2024-12-31")
w = np.linspace(1, 2.5, len(days)) * np.where(days.weekday >= 5, 0.15, 1.0)
hire = rng.choice(days, N, p=w / w.sum())
sat = rng.integers(1, 6, N).astype(float)
miss = rng.random(N) < np.where(dept == "Sales", 0.45, 0.05)           # H7 missing pattern
sat[miss] = np.nan
commute = np.round(rng.gamma(2, 4, N), 1)
commute[rng.choice(N, 8, replace=False)] = rng.uniform(300, 600, 8)   # H10 outliers
df = pd.DataFrame({"employee_id": [f"E{i:05d}" for i in range(N)], "hire_date": pd.Series(hire).dt.strftime("%Y-%m-%d"),
                   "department": dept, "division": division, "age": age, "tenure_years": tenure,
                   "monthly_salary_m": salary, "overtime": overtime, "satisfaction": sat,
                   "commute_km": commute, "churn": churn})
out = sys.argv[1] if len(sys.argv) > 1 else "hr_synthetic.csv"
df.to_csv(out, index=False)
truth = {
    "H1_overtime_churn": {"kind": "group_diff", "cols": ["overtime", "churn"]},
    "H2_salary_driver": {"kind": "group_diff", "cols": ["churn", "monthly_salary_m"]},
    "H3_salary_by_dept": {"kind": "group_diff", "cols": ["department", "monthly_salary_m"]},
    "H4_tenure_age": {"kind": "correlation", "cols": ["age", "tenure_years"]},
    "H5_weekday_hires": {"kind": "seasonality", "cols": ["hire_date", "weekday"]},
    "H6_hiring_trend": {"kind": "trend", "cols": ["hire_date"]},
    "H7_missing_sat_sales": {"kind": "missing_pattern", "cols": ["satisfaction", "department"]},
    "H8_dept_division": {"kind": "hierarchy", "cols": ["department", "division"]},
    "H10_commute_outliers": {"kind": "outliers", "cols": ["commute_km"]},
}
json.dump(truth, open(out.replace(".csv", "_truth.json"), "w"), indent=2)
