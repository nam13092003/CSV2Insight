"""Score, de-duplicate and diversify insights (QuickInsights-style: interestingness = prior x effect x impact)."""

# business-interest prior per insight type
TYPE_WEIGHT = {
    "trend": 1.0, "change_point": 0.95, "segment_change": 1.0, "segment_trend": 0.9, "seasonality": 0.9, "drivers": 0.95,
    "contribution": 0.85, "pareto": 0.85, "group_diff": 0.85, "correlation": 0.8, "association": 0.75,
    "anomaly_period": 0.75, "outliers": 0.6, "dominance": 0.55, "concentration": 0.6, "duplicates": 0.7,
    "missing": 0.6, "missing_pattern": 0.75, "constant_column": 0.4, "empty_column": 0.4, "redundancy": 0.45, "skew": 0.35,
    "imbalance": 0.4, "hierarchy": 0.3, "derived_column": 0.35, "coupled": 0.35, "derived_measure": 0.35,
}

THEME = {
    "trend": "time", "change_point": "time", "segment_change": "time", "segment_trend": "time", "seasonality": "time", "anomaly_period": "time",
    "drivers": "segment", "contribution": "segment", "pareto": "segment", "group_diff": "segment",
    "association": "relation", "correlation": "relation", "redundancy": "quality",
    "outliers": "distribution", "dominance": "distribution", "concentration": "distribution", "skew": "distribution",
    "imbalance": "distribution", "duplicates": "quality", "missing": "quality", "missing_pattern": "quality", "constant_column": "quality",
    "empty_column": "quality", "hierarchy": "quality", "derived_column": "quality", "coupled": "quality", "derived_measure": "quality",
}


def score(i):
    w = TYPE_WEIGHT.get(i["type"], 0.5)
    return round(w * i["strength"] * (0.6 + 0.4 * i["impact"]), 4)


STRUCTURAL = {"redundancy", "hierarchy", "derived_column", "coupled", "derived_measure"}


def rank(insights, secondary_cols=(), top_k=12, per_type_cap=3, trivial=()):
    sec = set(secondary_cols)
    kept = []
    for i in insights:
        if i["type"] not in STRUCTURAL:
            cols = set(i["columns"])
            if sec & cols:
                continue
            if i["type"] != "drivers" and any(pr <= cols for pr in trivial):
                continue
        i["score"] = score(i)
        i["theme"] = THEME.get(i["type"], "other")
        kept.append(i)
    # dedupe identical (type, column-set)
    best = {}
    for i in kept:
        k = (i["type"], frozenset(i["columns"]))
        if k not in best or i["score"] > best[k]["score"]:
            best[k] = i
    kept = list(best.values())
    # group_diff A->B vs B->A, and contribution vs dominance on same dim: keep stronger
    by_pair = {}
    for i in kept:
        if i["type"] in ("group_diff", "association", "correlation"):
            k = frozenset(i["columns"])
            if k in by_pair and by_pair[k]["score"] >= i["score"]:
                i["_drop"] = True
            else:
                if k in by_pair:
                    by_pair[k]["_drop"] = True
                by_pair[k] = i
    contrib_dims = {i["columns"][0] for i in kept if i["type"] in ("contribution", "pareto")}
    for i in kept:
        if i["type"] == "dominance" and i["columns"][0] in contrib_dims:
            i["score"] *= 0.5
    # a segment_change already explains change_point in total only partially; keep both.
    kept = [i for i in kept if not i.get("_drop")]
    kept.sort(key=lambda x: -x["score"])

    # diversity-aware top-k (MMR-like): cap per type and penalize column overlap
    top, counts = [], {}
    pool = kept[:]
    while pool and len(top) < top_k:
        best_j, best_v = None, -1
        for j, i in enumerate(pool):
            if counts.get(i["type"], 0) >= per_type_cap:
                continue
            pen = 0.0
            for t in top:
                ov = len(set(i["columns"]) & set(t["columns"])) / max(1, len(set(i["columns"])))
                pen = max(pen, 0.5 * ov + (0.3 if ov > 0 and t["type"] == i["type"] else 0))
            v = i["score"] * (1 - min(0.9, pen))
            if v > best_v:
                best_j, best_v = j, v
        if best_j is None:
            break
        i = pool.pop(best_j)
        counts[i["type"]] = counts.get(i["type"], 0) + 1
        top.append(i)
    for n, i in enumerate(kept, 1):
        i["id"] = f"I{n:02d}"
    return kept, top
