"""End-to-end: CSV -> profile -> mine -> rank -> (optional LLM narration) -> JSON/Markdown/HTML."""
import json
import time
import numpy as np
import pandas as pd

from .profile import read_csv_robust, infer_roles, summarize_columns
from . import miners as M
from .rank import rank


def _secondary(df, roles, pairs):
    """For each redundant pair choose the column to drop (keep the one with more descriptive labels)."""
    def desc(c):
        s = df[c]
        if s.dtype == bool or pd.api.types.is_numeric_dtype(s):
            return 100.0 if roles[c]["role"] == "measure" and not roles[c].get("also_dimension") else 0.0
        return float(s.dropna().astype(str).str.len().mean())
    drop = set()
    for a, b, _ in pairs:
        if a in drop or b in drop:
            continue
        drop.add(b if desc(a) >= desc(b) else a)
    return drop


def analyze(path_or_df, target=None, top_k=10, role_overrides=None, max_rows=1_000_000, seed=0):
    t0 = time.time()
    raw = read_csv_robust(path_or_df) if isinstance(path_or_df, str) else path_or_df
    n_raw = len(raw)
    sampled = False
    if n_raw > max_rows:
        raw = raw.sample(max_rows, random_state=seed).sort_index()
        sampled = True
    df, roles = infer_roles(raw, role_overrides)
    ctx = M.Ctx(df, roles, target)

    found = []
    found += M.mine_structure(ctx)
    found += M.mine_derived_measures(ctx)
    found += M.mine_quality(ctx)
    found += M.mine_distribution(ctx)
    corr, red_num = M.mine_correlations(ctx)
    cc, red_cat = M.mine_cat_cat(ctx)   # also marks near-deterministic pairs as trivial
    found += corr + cc
    secondary = _secondary(df, roles, red_num + red_cat) | ctx.fd_secondary
    ctx.secondary = secondary
    ctx.redundant_pairs = {frozenset((a, b)) for a, b, _ in red_num + red_cat}
    ctx.target_col = M.pick_target(ctx)
    found += M.mine_dim_measure(ctx)
    found += M.mine_missing_patterns(ctx)
    found += M.mine_time(ctx)
    found += M.mine_drivers(ctx, red_num + red_cat)
    found += M.redundancy_insights(red_num, "num") + M.redundancy_insights(red_cat, "cat")
    trivial = ctx.trivial
    all_ins, _ = rank(found, secondary, top_k=top_k, trivial=trivial)
    analytic = [i for i in all_ins if i["theme"] != "quality"]
    _, top = rank(analytic, secondary, top_k=top_k, trivial=trivial)
    # rank() re-assigns ids; re-number global list deterministically
    for n, i in enumerate(all_ins, 1):
        i["id"] = f"I{n:02d}"
    return {
        "dataset": {"source": path_or_df if isinstance(path_or_df, str) else "<dataframe>", "rows": n_raw,
                    "columns": int(raw.shape[1]), "analyzed_rows": len(df), "sampled": sampled,
                    "target": M.pick_target(ctx)},
        "columns": summarize_columns(df, roles),
        "top_insights": [i["id"] for i in top],
        "insights": all_ins,
        "secondary_columns": sorted(secondary),
        "elapsed_sec": round(time.time() - t0, 2),
    }


def to_jsonable(o):
    if isinstance(o, dict):
        return {str(k): to_jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [to_jsonable(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, float) and not np.isfinite(o):
        return None
    if isinstance(o, (pd.Timestamp, pd.Period)):
        return str(o)
    return o
