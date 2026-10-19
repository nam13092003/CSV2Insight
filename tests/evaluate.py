"""Evaluate: recall of planted insights + false-positive rate on pure-noise data."""
import json
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tableinsight.pipeline import analyze  # noqa

KIND_MAP = {
    "trend": {"trend", "segment_trend"}, "seasonality": {"seasonality"},
    "dominance": {"contribution", "dominance"}, "correlation": {"correlation"},
    "group_diff": {"group_diff", "drivers"}, "change_point": {"change_point", "segment_change"},
    "missing": {"missing"}, "duplicates": {"duplicates"}, "outliers": {"outliers"},
    "constant": {"constant_column"}, "concentration": {"pareto", "concentration"},
    "missing_pattern": {"missing_pattern"}, "hierarchy": {"hierarchy"},
}


def recall(csv, truth_json):
    r = analyze(csv)
    truth = json.load(open(truth_json))
    ins = r["insights"]
    top = set(r["top_insights"])
    rows = []
    for name, t in truth.items():
        hits = [i for i in ins if i["type"] in KIND_MAP[t["kind"]] and set(t["cols"]) <= set(i["columns"])
                and (not t.get("value") or t["value"] in json.dumps(i["facts"], ensure_ascii=False))]
        pos = min((ins.index(h) + 1 for h in hits), default=None)
        rows.append((name, bool(hits), pos, any(h["id"] in top for h in hits)))
    found = sum(r_[1] for r_ in rows)
    for r_ in rows:
        print(f"  {'OK ' if r_[1] else 'MISS'} {r_[0]:28s} rank={r_[2]} top={'Y' if r_[3] else '-'}")
    print(f"  recall = {found}/{len(rows)}; total insights = {len(ins)}")
    return found / len(rows)


def noise_fp(seeds=5, n=3000):
    """Independent random columns: any analytic insight is a false positive."""
    fps = []
    for sd in range(seeds):
        rng = np.random.default_rng(100 + sd)
        df = pd.DataFrame({
            "date": (pd.Timestamp("2022-01-01") + pd.to_timedelta(rng.integers(0, 900, n), unit="D")).strftime("%Y-%m-%d"),
            "region": rng.choice(list("ABCDE"), n), "segment": rng.choice(["x", "y", "z"], n),
            "store": rng.choice([f"S{i}" for i in range(25)], n),
            "sales": np.round(rng.lognormal(5, 1, n), 2), "price": np.round(rng.normal(50, 10, n), 2),
            "units": rng.poisson(3, n), "score": rng.integers(1, 6, n), "flag": rng.integers(0, 2, n),
        })
        r = analyze(df)
        bad = [i for i in r["insights"] if i["type"] not in ("skew", "concentration", "outliers", "imbalance")]
        fps.append(len(bad))
        for b in bad:
            print("   FP:", b["type"], b["text"]["en"][:140])
    print(f"  noise false positives per dataset: {fps}")
    return fps


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    base = os.path.join(here, "..", "examples")
    os.makedirs(base, exist_ok=True)
    for gen, name in (("make_synthetic.py", "sales_synthetic"), ("make_synthetic_hr.py", "hr_synthetic")):
        csv = os.path.join(base, name + ".csv")
        if not os.path.exists(csv):
            os.system(f'"{sys.executable}" "{os.path.join(here, gen)}" "{csv}"')
        print(f"== planted-insight recall: {name} ==")
        recall(csv, csv.replace(".csv", "_truth.json"))
    print("== pure-noise false positives (should be 0) ==")
    noise_fp()
