"""Insight miners: each returns a list of Insight dicts with verified statistics.

Insight = {
  type, columns, strength (0..1 effect size), impact (0..1 coverage), p (p-value or None),
  facts (dict of numbers/labels), text {vi, en}, chart (optional)
}
"""
import math
import re
import numpy as np
import pandas as pd

from . import stats as st
from .profile import binary_as_float

ALPHA = 1e-3


# ---------------- formatting ----------------
def fmt(x, nd=None):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "n/a"
    if isinstance(x, (int, np.integer)):
        return f"{int(x):,}"
    x = float(x)
    if nd is not None:
        return f"{x:,.{nd}f}"
    a = abs(x)
    if a >= 1e9:
        return f"{x / 1e9:,.2f}B"
    if a >= 1e6:
        return f"{x / 1e6:,.2f}M"
    if a >= 1000:
        return f"{x:,.0f}"
    if x == round(x):
        return f"{int(round(x)):,}"
    if a >= 100:
        return f"{x:,.1f}"
    if a >= 1:
        return f"{x:,.2f}"
    return f"{x:.3g}"


def pct(x, nd=1):
    return f"{100 * x:.{nd}f}%"


def T(vi, en):
    return {"vi": vi, "en": en}


def ins(type_, columns, strength, impact, text, facts=None, p=None, chart=None):
    return {"type": type_, "columns": list(columns), "strength": float(max(0.0, min(1.0, strength))),
            "impact": float(max(0.0, min(1.0, impact))), "p": None if p is None else float(p),
            "facts": facts or {}, "text": text, "chart": chart}


# ---------------- context ----------------
class Ctx:
    def __init__(self, df, roles, target=None):
        self.df, self.roles, self.n = df, roles, len(df)
        self.target = target
        R = roles
        self.dates = [c for c, r in R.items() if r["role"] == "datetime"]
        self.binaries = [c for c, r in R.items() if r["role"] == "binary"]
        self.cont = [c for c, r in R.items() if r["role"] == "measure" and not r.get("also_dimension")]
        self.ordinal_meas = [c for c, r in R.items() if r["role"] == "measure" and r.get("also_dimension")
                             and r["n_unique"] >= 4]
        # numeric measures for distributions/correlations
        self.measures = self.cont + self.ordinal_meas
        self.sum_measures = [c for c in self.cont if R[c].get("agg") == "sum"]
        self.dims = [c for c, r in R.items() if (r["role"] == "dimension" and 2 <= r["n_unique"] <= 60)
                     or (r["role"] == "measure" and r.get("also_dimension"))] + self.binaries
        # date components (year/month columns that built a period) duplicate the time analysis
        comp = {c for r in R.values() for c in r.get("derived_from", [])}
        if self.dates:
            comp |= {c for c, r in R.items() if r.get("is_year")}
        self.dims = [d for d in self.dims if d not in comp]
        self.measures = [m for m in self.measures if m not in comp]
        self.cont = [m for m in self.cont if m not in comp]
        self.secondary = set()      # redundant columns to ignore
        self.trivial = set()        # frozensets of column pairs linked by definition/hierarchy
        self.redundant_pairs = set()
        self.target_col = None
        self.fd_secondary = set()
        self.highcard = [c for c, r in R.items() if r["role"] == "dimension" and r["n_unique"] > 60]
        self._num = {}

    def num(self, c):
        if c not in self._num:
            r = self.roles[c]
            s = binary_as_float(self.df[c], r) if r["role"] == "binary" else pd.to_numeric(self.df[c], errors="coerce")
            self._num[c] = s.astype(float)
        return self._num[c]

    def label(self, c):
        """Readable name for a binary measure (rate of positive class)."""
        r = self.roles[c]
        if r["role"] == "binary" and r.get("positive") not in (None, "1", "True", "true"):
            return f"{c}={r['positive']}"
        return c

    def is_rate(self, c):
        return self.roles[c]["role"] == "binary"


def _vfmt(ctx, c, v):
    return pct(v) if ctx.is_rate(c) else fmt(v)


def _groups(ctx, dim, min_size=None):
    s = ctx.df[dim]
    vc = s.value_counts()
    min_size = min_size or max(5, int(0.003 * ctx.n))
    keep = vc[vc >= min_size].index[:20]
    if ctx.roles[dim].get("ordinal"):
        keep = sorted(keep)
    return keep


# ======================= DATA QUALITY =======================
def mine_quality(ctx):
    out, df, n = [], ctx.df, ctx.n
    for c, r in ctx.roles.items():
        if r.get("derived_from"):
            continue
        m = r.get("missing_pct", 0)
        if r["role"] == "empty":
            out.append(ins("empty_column", [c], 1, 0.3, T(f"Cột `{c}` hoàn toàn trống — nên loại bỏ.",
                                                        f"Column `{c}` is completely empty — drop it.")))
        elif r["role"] == "constant":
            v = df[c].dropna().iloc[0]
            out.append(ins("constant_column", [c], 0.6, 0.3,
                           T(f"Cột `{c}` chỉ có một giá trị duy nhất (`{v}`) — không mang thông tin phân tích.",
                             f"Column `{c}` has a single value (`{v}`) — carries no analytical information."),
                           facts={"value": str(v)}))
        elif m >= 0.05:
            out.append(ins("missing", [c], min(1, m * 2), 1,
                           T(f"Cột `{c}` thiếu {pct(m)} giá trị ({fmt(int(round(m * n)))}/{fmt(n)} dòng).",
                             f"Column `{c}` is missing {pct(m)} of values ({fmt(int(round(m * n)))}/{fmt(n)} rows)."),
                           facts={"missing_pct": pct(m), "missing_rows": fmt(int(round(m * n))), "rows": fmt(n)}))
    has_id = any(r["role"] == "id" for r in ctx.roles.values())
    dup = int(df.duplicated().sum())
    if dup:
        out.append(ins("duplicates", [], min(1, 0.4 + dup / n * 10), 1,
                       T(f"Có {fmt(dup)} dòng trùng lặp hoàn toàn ({pct(dup / n, 2)} dữ liệu) — " + (
                           "cần khử trùng trước khi tổng hợp." if has_id else
                           "có thể là bản ghi nhập trùng hoặc các đối tượng có thuộc tính giống hệt nhau (bảng không có cột định danh); nên kiểm tra."),
                         f"{fmt(dup)} fully duplicated rows ({pct(dup / n, 2)} of data) — " + (
                           "deduplicate before aggregating." if has_id else
                           "may be double-entries or distinct entities with identical attributes (no ID column); verify.")),
                       facts={"duplicate_rows": fmt(dup), "duplicate_pct": pct(dup / n, 2)}))
    else:
        ids = [c for c, r in ctx.roles.items() if r["role"] == "id"]
        for c in ids:
            d = int(df[c].dropna().duplicated().sum())
            if d:
                out.append(ins("duplicates", [c], 0.6, 1,
                               T(f"Cột định danh `{c}` có {fmt(d)} giá trị lặp lại.",
                                 f"Identifier column `{c}` has {fmt(d)} repeated values."), facts={"dups": fmt(d)}))
    return out


def mine_missing_patterns(ctx):
    out, df, n = [], ctx.df, ctx.n
    # systematic missingness: is the missing-rate of a column very different across groups?
    for c, r in ctx.roles.items():
        m = r.get("missing_pct", 0)
        if not (0.05 <= m <= 0.95) or r.get("derived_from"):
            continue
        miss = df[c].isna().astype(float)
        best = None
        for d in ctx.dims:
            if d == c or d in ctx.secondary:
                continue
            keep = _groups(ctx, d, max(15, int(0.01 * n)))
            if len(keep) < 2:
                continue
            gs = [miss[df[d] == g].to_numpy() for g in keep]
            F, p, eta2 = st.anova_oneway(gs)
            if p < ALPHA and eta2 >= 0.05 and (best is None or eta2 > best[0]):
                rates = pd.Series([g.mean() for g in gs], index=[str(k) for k in keep])
                best = (eta2, d, rates, p)
        if best:
            eta2, d, rates, p = best
            hi, lo = rates.idxmax(), rates.idxmin()
            out.append(ins("missing_pattern", [c, d], min(1, math.sqrt(eta2) * 1.2), 1,
                           T(f"Dữ liệu thiếu của `{c}` không ngẫu nhiên: tỉ lệ thiếu là {pct(rates[hi])} ở `{d}={hi}` nhưng chỉ {pct(rates[lo])} ở `{d}={lo}` — phân tích trên `{c}` sẽ bị lệch về nhóm có dữ liệu.",
                             f"Missing `{c}` is not random: {pct(rates[hi])} missing for `{d}={hi}` vs. only {pct(rates[lo])} for `{d}={lo}` — analyses of `{c}` are biased toward groups that have data."),
                           facts={"column": c, "by": d, "highest_group": hi, "highest_missing": pct(rates[hi]),
                                  "lowest_group": lo, "lowest_missing": pct(rates[lo])}, p=p,
                           chart={**_bar(rates * 100, "%"), "highlight": [hi]}))
    return out


# ======================= UNIVARIATE =======================
def mine_distribution(ctx):
    out, df = [], ctx.df
    for c in ctx.cont:
        x = ctx.num(c).dropna().to_numpy()
        if len(x) < 20:
            continue
        sk = st.skewness(x)
        positive = (x > 0).all()
        z = np.log(x) if (positive and sk > 1) else x
        q1, q3 = np.percentile(z, [25, 75]); iqr = q3 - q1
        if iqr > 0:
            hi, lo = q3 + 3 * iqr, q1 - 3 * iqr
            mask = (z > hi) if z is not x else ((z > hi) | (z < lo))
            k = int(mask.sum())
            ext = float(np.max(np.abs(z[mask] - np.median(z))) / iqr) if k else 0.0
            ext_min = 3.5 if z is not x else 5.0  # log scale compresses distances
            if 0 < k <= 0.03 * len(x) and ext >= ext_min:  # far beyond the fence, not just the natural tail
                share = x[mask].sum() / x.sum() if ctx.roles[c].get("agg") == "sum" and x.sum() > 0 else None
                med = float(np.median(x))
                facts = {"n_outliers": fmt(k), "outlier_pct": pct(k / len(x), 2), "max": fmt(float(x.max())),
                         "min": fmt(float(x.min())), "median": fmt(med)}
                extra_vi = extra_en = ""
                if share is not None and share > 0.02:
                    facts["share_of_total"] = pct(share)
                    extra_vi = f"; riêng nhóm này chiếm {pct(share)} tổng `{c}`"
                    extra_en = f"; together they account for {pct(share)} of total `{c}`"
                ex = x[mask]
                rng_txt = f"{fmt(float(ex.min()))}–{fmt(float(ex.max()))}"
                out.append(ins("outliers", [c], min(1, ext / 8), max(0.2, share or 0),
                               T(f"`{c}` có {fmt(k)} giá trị ngoại lai cực đoan ({pct(k / len(x), 2)}), trong khoảng {rng_txt} so với trung vị {fmt(med)}{extra_vi}.",
                                 f"`{c}` has {fmt(k)} extreme outliers ({pct(k / len(x), 2)}), ranging {rng_txt} vs. a median of {fmt(med)}{extra_en}."),
                               facts={**facts, "outlier_range": rng_txt}))
        if abs(sk) >= 1.5:
            mean, med = float(x.mean()), float(np.median(x))
            side = ("phải", "right") if sk > 0 else ("trái", "left")
            out.append(ins("skew", [c], min(1, abs(sk) / 6), 0.5,
                           T(f"Phân phối `{c}` lệch {side[0]} mạnh (độ lệch {sk:.2f}): trung bình {fmt(mean)} nhưng trung vị chỉ {fmt(med)} — nên dùng trung vị khi báo cáo.",
                             f"`{c}` is strongly {side[1]}-skewed (skewness {sk:.2f}): mean {fmt(mean)} vs. median {fmt(med)} — report the median."),
                           facts={"skewness": f"{sk:.2f}", "mean": fmt(mean), "median": fmt(med)}))
        if ctx.roles[c].get("agg") == "sum" and positive and len(x) >= 50:
            xs = np.sort(x)[::-1]
            top10 = xs[: max(1, len(xs) // 10)].sum() / xs.sum()
            if top10 >= 0.4:
                g = st.gini(x)
                out.append(ins("concentration", [c], (top10 - 0.1) / 0.9, top10,
                               T(f"`{c}` tập trung cao: 10% dòng lớn nhất chiếm {pct(top10)} tổng giá trị (Gini {g:.2f}).",
                                 f"`{c}` is highly concentrated: the top 10% of rows hold {pct(top10)} of the total (Gini {g:.2f})."),
                               facts={"top10_share": pct(top10), "gini": f"{g:.2f}"}))
    # categorical dominance (row counts)
    for c in ctx.dims:
        r = ctx.roles[c]
        if r.get("ordinal"):
            continue
        vc = df[c].value_counts(normalize=True)
        k = len(vc)
        if k < 3:
            continue
        p1 = float(vc.iloc[0])
        if p1 >= max(0.3, 1.8 / k):
            out.append(ins("dominance", [c], (p1 - 1 / k) / (1 - 1 / k), p1,
                           T(f"`{c}` bị chi phối bởi `{vc.index[0]}` với {pct(p1)} số dòng (trong {k} nhóm).",
                             f"`{c}` is dominated by `{vc.index[0]}` with {pct(p1)} of rows (out of {k} groups)."),
                           facts={"top": str(vc.index[0]), "share": pct(p1), "n_groups": k},
                           chart=_bar(vc.head(12) * 100, "%")))
    for c in ctx.binaries:
        rate = float(ctx.num(c).mean())
        if rate < 0.1 or rate > 0.9:
            out.append(ins("imbalance", [c], abs(rate - 0.5) * 2 * 0.6, 0.5,
                           T(f"`{ctx.label(c)}` mất cân bằng: chỉ {pct(min(rate, 1 - rate))} thuộc nhóm thiểu số.",
                             f"`{ctx.label(c)}` is imbalanced: only {pct(min(rate, 1 - rate))} in the minority class."),
                           facts={"rate": pct(rate)}))
    return out


def _bar(series, unit=""):
    return {"kind": "bar", "labels": [str(i) for i in series.index], "values": [float(v) for v in series.values],
            "unit": unit}


# ======================= DIMENSION x MEASURE =======================
def mine_dim_measure(ctx):
    out, df = [], ctx.df
    meas = ctx.measures + ctx.binaries
    for d in ctx.dims:
        keep = _groups(ctx, d)
        if len(keep) < 2:
            continue
        sub_mask = df[d].isin(keep)
        for m in meas:
            if m == d or frozenset((d, m)) in ctx.trivial:
                continue
            if d == ctx.target_col and m in ctx.binaries:
                continue
            if ctx.roles[d].get("ordinal") and d in ctx.measures and m in ctx.measures:
                continue  # ordinal x numeric is covered by rank correlation
            y = ctx.num(m)
            gs = [y[(df[d] == g)].dropna().to_numpy() for g in keep]
            if sum(len(g) for g in gs) < 20:
                continue
            F, p, eta2 = st.anova_oneway(gs)
            if not (p < ALPHA and eta2 >= 0.02):
                continue
            means = pd.Series([g.mean() if len(g) else np.nan for g in gs], index=[str(k) for k in keep]).dropna()
            sizes = pd.Series([len(g) for g in gs], index=[str(k) for k in keep])
            big = sizes[sizes >= max(15, 0.01 * ctx.n)].index
            if len(big) >= 2:
                means = means[means.index.isin(big)]
            if len(means) < 2:
                continue
            overall = float(y[sub_mask].mean())
            hi, lo = means.idxmax(), means.idxmin()
            ratio = means.max() / means.min() if means.min() > 0 else None
            if ratio and ratio > 20:
                ratio = None
            what = f"tỉ lệ `{ctx.label(m)}`" if ctx.is_rate(m) else f"`{m}` trung bình"
            what_en = f"`{ctx.label(m)}` rate" if ctx.is_rate(m) else f"average `{m}`"
            vf = lambda v: _vfmt(ctx, m, v)
            ratio_vi = f" (gấp {ratio:.1f} lần)" if ratio and ratio >= 1.3 else ""
            ratio_en = f" ({ratio:.1f}x)" if ratio and ratio >= 1.3 else ""
            if len(means) == 2:
                txt = T(f"{what[0].upper() + what[1:]} khác biệt rõ theo `{d}`: `{hi}` là {vf(means[hi])} so với `{lo}` là {vf(means[lo])}{ratio_vi}.",
                        f"{what_en[0].upper() + what_en[1:]} differs by `{d}`: `{hi}` at {vf(means[hi])} vs. `{lo}` at {vf(means[lo])}{ratio_en}.")
            else:
                txt = T(f"{what[0].upper() + what[1:]} khác biệt rõ theo `{d}`: cao nhất ở `{hi}` ({vf(means[hi])}), thấp nhất ở `{lo}` ({vf(means[lo])}){ratio_vi}; trung bình chung {vf(overall)}.",
                        f"{what_en[0].upper() + what_en[1:]} varies by `{d}`: highest for `{hi}` ({vf(means[hi])}), lowest for `{lo}` ({vf(means[lo])}){ratio_en}; overall {vf(overall)}.")
            facts = {"dimension": d, "measure": m, "highest_group": hi, "highest_value": vf(means[hi]),
                     "lowest_group": lo, "lowest_value": vf(means[lo]), "overall": vf(overall),
                     "eta_squared": f"{eta2:.3f}"}
            if ratio:
                facts["ratio"] = f"{ratio:.1f}"
            ch = means * (100 if ctx.is_rate(m) else 1)
            strength = math.sqrt(eta2)
            if ctx.is_rate(m):  # Cohen's h between extreme groups
                h = abs(2 * math.asin(math.sqrt(min(1, max(0, means.max())))) - 2 * math.asin(math.sqrt(min(1, max(0, means.min())))))
                strength = max(strength, 0.7 * min(1, h / 1.2))
                facts["cohens_h"] = f"{h:.2f}"
            out.append(ins("group_diff", [d, m], strength, 1, txt, facts, p,
                           chart={**_bar(ch, "%" if ctx.is_rate(m) else ""), "highlight": [hi, lo]}))
        # contribution of sum measures
        if ctx.roles[d].get("ordinal"):
            continue
        for m in ctx.sum_measures:
            if m == d:
                continue
            tot = df.groupby(d)[m].sum().sort_values(ascending=False)
            if tot.sum() <= 0 or len(tot) < 3:
                continue
            share = tot / tot.sum()
            rows_share = df[d].value_counts(normalize=True)
            s1 = float(share.iloc[0]); top = share.index[0]
            kk = len(share)
            if kk >= 8:
                ntop = max(1, int(round(0.2 * kk)))
                topshare = float(share.iloc[:ntop].sum())
                if topshare >= 0.4 and topshare >= 1.6 * ntop / kk:
                    out.append(ins("pareto", [d, m], (topshare - ntop / kk) / (1 - ntop / kk), topshare,
                                   T(f"`{m}` tập trung theo `{d}`: {ntop}/{kk} nhóm hàng đầu ({', '.join(map(str, share.index[:min(ntop, 5)]))}) tạo ra {pct(topshare)} tổng `{m}`.",
                                     f"`{m}` is concentrated by `{d}`: the top {ntop} of {kk} ({', '.join(map(str, share.index[:min(ntop, 5)]))}) generate {pct(topshare)} of total `{m}`."),
                                   facts={"top_n": ntop, "n_groups": kk, "top_share": pct(topshare),
                                          "top_members": [str(v) for v in share.index[:ntop]]},
                                   chart=_bar(share.head(12) * 100, "%")))
            if s1 >= max(0.3, 1.8 / kk):
                rs = float(rows_share.get(top, np.nan))
                out.append(ins("contribution", [d, m], (s1 - 1 / kk) / (1 - 1 / kk), s1,
                               T(f"`{top}` đóng góp lớn nhất vào `{m}`: {pct(s1)} tổng (với {pct(rs)} số dòng), tiếp theo là `{share.index[1]}` ({pct(float(share.iloc[1]))}).",
                                 f"`{top}` is the largest contributor to `{m}`: {pct(s1)} of the total ({pct(rs)} of rows), followed by `{share.index[1]}` ({pct(float(share.iloc[1]))})."),
                               facts={"top": str(top), "share": pct(s1), "row_share": pct(rs),
                                      "second": str(share.index[1]), "second_share": pct(float(share.iloc[1]))},
                               chart={**_bar(share.head(12) * 100, "%"), "highlight": [str(top)]}))
    # high-cardinality dims: pareto on row counts / sum measures
    for d in ctx.highcard:
        for m in ctx.sum_measures:
            tot = df.groupby(d)[m].sum().sort_values(ascending=False)
            if tot.sum() <= 0:
                continue
            kk = len(tot); ntop = max(1, int(round(0.2 * kk)))
            ts = float(tot.iloc[:ntop].sum() / tot.sum())
            if ts >= 0.5:
                out.append(ins("pareto", [d, m], (ts - 0.2) / 0.8, ts,
                               T(f"20% `{d}` hàng đầu ({ntop}/{kk}) tạo ra {pct(ts)} tổng `{m}`.",
                                 f"The top 20% of `{d}` ({ntop}/{kk}) generate {pct(ts)} of total `{m}`."),
                               facts={"top_n": ntop, "n_groups": kk, "top_share": pct(ts)}))
    return out


# ======================= NUMERIC x NUMERIC =======================
def mine_correlations(ctx):
    out, redund = [], []
    ms = ctx.measures
    for i in range(len(ms)):
        for j in range(i + 1, len(ms)):
            a, b = ms[i], ms[j]
            if frozenset((a, b)) in ctx.trivial:
                continue
            r, p, n = st.corr_test(ctx.num(a), ctx.num(b), "spearman")
            if not np.isfinite(r) or p >= ALPHA or abs(r) < 0.3:
                continue
            rp, _, _ = st.corr_test(ctx.num(a), ctx.num(b), "pearson")
            if abs(r) >= 0.97:
                redund.append((a, b, r))
                continue
            lvl = ("rất mạnh", "very strong") if abs(r) >= 0.8 else ("mạnh", "strong") if abs(r) >= 0.6 else (
                "trung bình", "moderate") if abs(r) >= 0.4 else ("yếu–trung bình", "weak-to-moderate")
            dir_ = ("thuận", "positive") if r > 0 else ("nghịch", "negative")
            how = ("càng cao thì", "higher", "càng cao") if r > 0 else ("càng cao thì", "higher", "càng thấp")
            # quantify: mean of b in top vs bottom quartile of a
            xa, xb = ctx.num(a), ctx.num(b)
            mk = xa.notna() & xb.notna()
            xa_, xb_ = xa[mk], xb[mk]
            q25, q75 = float(xa_.quantile(0.25)), float(xa_.quantile(0.75))
            if q25 == q75:
                lo_m, hi_m = xa_ <= q25, xa_ > q25
                lo_t, hi_t = f"≤ {fmt(q25)}", f"> {fmt(q25)}"
            else:
                lo_m, hi_m = xa_ <= q25, xa_ >= q75
                lo_t, hi_t = f"≤ {fmt(q25)}", f"≥ {fmt(q75)}"
            top_b, bot_b = float(xb_[hi_m].mean()), float(xb_[lo_m].mean())
            out.append(ins("correlation", [a, b], abs(r), n / ctx.n,
                           T(f"`{a}` và `{b}` tương quan {dir_[0]} {lvl[0]} (Spearman ρ = {r:.2f}): khi `{a}` {hi_t}, `{b}` trung bình {fmt(top_b)}, so với {fmt(bot_b)} khi `{a}` {lo_t}.",
                             f"`{a}` and `{b}` have a {lvl[1]} {dir_[1]} correlation (Spearman ρ = {r:.2f}): when `{a}` {hi_t}, `{b}` averages {fmt(top_b)} vs. {fmt(bot_b)} when `{a}` {lo_t}."),
                           facts={"rho": f"{r:.2f}", "pearson": f"{rp:.2f}", "high_group_mean": fmt(top_b),
                                  "low_group_mean": fmt(bot_b), "high_threshold": hi_t, "low_threshold": lo_t}, p=p,
                           chart={"kind": "scatter", "x": a, "y": b}))
    return out, redund


# ======================= STRUCTURE (functional dependencies) =======================
def _purity(df, by, target):
    sub = df[by + [target]].dropna()
    if len(sub) < 20:
        return 0.0, 0
    vc = sub.groupby(by + [target], observed=True).size()
    top = vc.groupby(level=list(range(len(by)))).max()
    return float(top.sum() / len(sub)), int(len(top))


def mine_structure(ctx, max_cols=15):
    """Detect hierarchies (A -> B) and columns derived from two others (A1, A2 -> B).
    Relationships among such columns are definitional, not insights."""
    out, df = [], ctx.df
    cats = list(dict.fromkeys(c for c in ctx.dims if ctx.roles[c]["n_unique"] <= 60))[:max_cols]
    nun = {c: df[c].nunique() for c in cats}
    single = {}
    for b in cats:
        if nun[b] > 12:
            continue
        for a in cats:
            if a == b or nun[a] < nun[b]:
                continue
            pu, _ = _purity(df, [a], b)
            single[(a, b)] = pu
            if pu >= 0.995 and nun[a] > nun[b]:
                ctx.trivial.add(frozenset((a, b)))
                if ctx.roles[b]["role"] == "binary":
                    ctx.fd_secondary.add(b)  # a yes/no flag fully implied by a richer column adds nothing
                out.append(ins("hierarchy", [a, b], 0.4, 0.3,
                               T(f"`{b}` được xác định hoàn toàn bởi `{a}` (mỗi giá trị `{a}` chỉ thuộc một `{b}`) — quan hệ cấp bậc, không phải phát hiện.",
                                 f"`{b}` is fully determined by `{a}` (each `{a}` maps to one `{b}`) — a hierarchy, not a finding."),
                               facts={"purity": pct(pu)}))
    for b in cats:
        if nun[b] > 5:
            continue
        for i, a1 in enumerate(cats):
            for a2 in cats[i + 1:]:
                if b in (a1, a2) or nun[a1] * nun[a2] > max(20, ctx.n / 5):
                    continue
                if frozenset((a1, b)) in ctx.trivial or frozenset((a2, b)) in ctx.trivial:
                    continue
                if single.get((a1, b), 0) >= 0.98 or single.get((a2, b), 0) >= 0.98:
                    continue
                pu, k = _purity(df, [a1, a2], b)
                if pu >= 0.995:
                    ctx.trivial |= {frozenset((a1, b)), frozenset((a2, b))}
                    out.append(ins("derived_column", [b, a1, a2], 0.5, 0.3,
                                   T(f"`{b}` gần như được suy ra từ `{a1}` và `{a2}` (độ thuần {pct(pu)}) — khác biệt của `{b}` theo hai cột này là do định nghĩa.",
                                     f"`{b}` is essentially derived from `{a1}` and `{a2}` (purity {pct(pu)}) — its differences across them are definitional."),
                                   facts={"purity": pct(pu)}))
    return out


def mine_derived_measures(ctx):
    """Detect C ~ A x B (or A x B x (1-D)) among positive measures via log-linear fit; marks trivial pairs."""
    out = []
    ms = [m for m in ctx.cont if (ctx.num(m).dropna() > 0).mean() > 0.99][:12]
    logs = {m: np.log(ctx.num(m).where(ctx.num(m) > 0)) for m in ms}
    for c in ms:
        best = None
        for i, a in enumerate(ms):
            for b in ms[i + 1:]:
                if c in (a, b):
                    continue
                X = pd.concat([logs[a], logs[b], logs[c]], axis=1).dropna()
                if len(X) < 30:
                    continue
                A = np.column_stack([np.ones(len(X)), X.iloc[:, 0], X.iloc[:, 1]])
                beta, *_ = np.linalg.lstsq(A, X.iloc[:, 2].to_numpy(), rcond=None)
                pred = A @ beta
                r2 = 1 - ((X.iloc[:, 2] - pred) ** 2).sum() / ((X.iloc[:, 2] - X.iloc[:, 2].mean()) ** 2).sum()
                if r2 >= 0.97 and all(abs(v - 1) < 0.15 for v in beta[1:]) and (best is None or r2 > best[0]):
                    best = (r2, a, b)
        if best:
            r2, a, b = best
            ctx.trivial |= {frozenset((c, a)), frozenset((c, b))}
            out.append(ins("derived_measure", [c, a, b], 0.5, 0.3,
                           T(f"`{c}` gần như bằng `{a}` × `{b}` (R² log = {r2:.3f}) — tương quan giữa chúng là do công thức, không phải phát hiện.",
                             f"`{c}` is essentially `{a}` × `{b}` (log R² = {r2:.3f}) — their correlation is arithmetic, not a finding."),
                           facts={"r2": f"{r2:.3f}"}))
    return out


# ======================= CATEGORY x CATEGORY =======================
def mine_cat_cat(ctx):
    out, redund, df = [], [], ctx.df
    ds = list(dict.fromkeys(ctx.dims))
    for i in range(len(ds)):
        for j in range(i + 1, len(ds)):
            a, b = ds[i], ds[j]
            ct = pd.crosstab(df[a], df[b])
            if ct.shape[0] < 2 or ct.shape[1] < 2:
                continue
            v, p = st.cramers_v(ct.to_numpy())
            if v >= 0.95:
                if ct.shape[0] == ct.shape[1]:   # one-to-one mapping -> redundant twin
                    redund.append((a, b, v))
                continue                          # many-to-one -> hierarchy (see mine_structure)
            if v >= 0.85 and p < ALPHA:
                ctx.trivial.add(frozenset((a, b)))
                n_ = ct.to_numpy().sum()
                rows = ct.div(ct.sum(1), axis=0)
                ia = rows.max(1).idxmax(); ib = rows.loc[ia].idxmax()
                out.append(ins("coupled", [a, b], 0.5, 0.3,
                               T(f"`{a}` và `{b}` gần như xác định lẫn nhau (Cramér's V = {v:.2f}), ví dụ `{a}={ia}` → {pct(float(rows.loc[ia, ib]))} là `{b}={ib}` — nên phân tích như một chiều.",
                                 f"`{a}` and `{b}` nearly determine each other (Cramér's V = {v:.2f}), e.g. `{a}={ia}` → {pct(float(rows.loc[ia, ib]))} `{b}={ib}` — treat them as one dimension."),
                               facts={"cramers_v": f"{v:.2f}"}, p=p))
                continue
            if v < 0.2 or p >= ALPHA or frozenset((a, b)) in ctx.trivial:
                continue
            if a in ctx.binaries or b in ctx.binaries:
                continue  # binary rates per group are handled by group_diff
            n = ct.to_numpy().sum()
            pa, pb = ct.sum(1) / n, ct.sum(0) / n
            expc = np.outer(pa, pb) * n
            okc = ct >= max(10, 0.01 * n)
            d1 = (ct.div(ct.sum(1), axis=0) - pb).where(okc)            # P(b|a) - P(b)
            d2 = (ct.div(ct.sum(0), axis=1).sub(pa, axis=0)).where(okc)  # P(a|b) - P(a)
            if d1.stack().empty:
                continue
            c1, c2 = d1.stack().idxmax(), d2.stack().idxmax()
            if d2.loc[c2] > d1.loc[c1]:  # condition on column b instead: P(a=c2[0] | b=c2[1])
                a, b = b, a
                cond = float(ct.loc[c2[0], c2[1]] / ct[c2[1]].sum())
                ia, ib = c2[1], c2[0]
                base = float(pa[c2[0]])
                lv = cond / base
            else:
                ia, ib = c1
                cond = float(ct.loc[ia, ib] / ct.loc[ia].sum())
                base = float(pb[ib])
                lv = cond / base
            out.append(ins("association", [a, b], v, 1,
                           T(f"`{a}` và `{b}` liên hệ chặt (Cramér's V = {v:.2f}): trong nhóm `{a}={ia}`, {pct(cond)} có `{b}={ib}` so với {pct(base)} trên toàn bộ dữ liệu.",
                             f"`{a}` and `{b}` are associated (Cramér's V = {v:.2f}): among `{a}={ia}`, {pct(cond)} have `{b}={ib}` vs. {pct(base)} overall."),
                           facts={"cramers_v": f"{v:.2f}", "group": f"{a}={ia}", "outcome": f"{b}={ib}",
                                  "conditional": pct(cond), "baseline": pct(base), "lift": f"{lv:.1f}"}, p=p))
    return out, redund


# ======================= TIME SERIES =======================
def _freq(dates, derived=False):
    if derived:
        return "M"
    span = (dates.max() - dates.min()).days
    if span >= 3 * 365:
        return "M"
    if span >= 120:
        return "W"
    if span >= 14:
        return "D"
    return None


FNAME = {"M": ("tháng", "month"), "W": ("tuần", "week"), "D": ("ngày", "day")}


def _robust_values(ctx, col):
    """Winsorize extreme rows (same 3xIQR fence as outlier miner, log scale if skewed) for detection."""
    key = ("robust", col)
    if key in ctx._num:
        return ctx._num[key]
    x = ctx.num(col)
    v = x.dropna().to_numpy()
    out = x
    if len(v) >= 20 and not ctx.is_rate(col):
        if (v > 0).all() and st.skewness(v) > 1:
            lz = np.log(v); q1, q3 = np.percentile(lz, [25, 75]); hi = math.exp(q3 + 3 * (q3 - q1))
            out = x.clip(upper=hi)
        else:
            q1, q3 = np.percentile(v, [25, 75]); i = q3 - q1
            if i > 0:
                out = x.clip(q1 - 3 * i, q3 + 3 * i)
    ctx._num[key] = out
    return out


def _period_series(ctx, dcol, freq, value_col=None, agg="sum", mask=None, robust=False):
    df = ctx.df if mask is None else ctx.df[mask]
    d = df[dcol].dropna()
    key = d.dt.to_period(freq)
    if value_col is None:
        s = key.value_counts().sort_index()
    else:
        src = _robust_values(ctx, value_col) if robust else ctx.num(value_col)
        s = src[d.index].groupby(key).agg(agg).sort_index()
    if len(s) == 0:
        return s
    full = pd.period_range(s.index.min(), s.index.max(), freq=freq)
    s = s.reindex(full)
    if value_col is None or agg == "sum":
        s = s.fillna(0)
    return s


def _trim_edges(s, counts):
    """Drop partial first/last periods (row count < 50% of median)."""
    counts = counts.reindex(s.index).fillna(0)
    med = counts.median()
    if med <= 1:
        return s
    while len(s) > 6 and counts.loc[s.index[-1]] < 0.5 * med:
        s = s.iloc[:-1]
    while len(s) > 6 and counts.loc[s.index[0]] < 0.5 * med:
        s = s.iloc[1:]
    return s


def _plabel(p):
    if getattr(p, "freqstr", "").startswith("W"):
        return str(p.start_time.date())
    return str(p)


MONTH_VI = ["", "tháng 1", "tháng 2", "tháng 3", "tháng 4", "tháng 5", "tháng 6", "tháng 7", "tháng 8", "tháng 9",
            "tháng 10", "tháng 11", "tháng 12"]
MONTH_EN = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
            "November", "December"]
WD_VI = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]
WD_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _calendar_effects(ctx, dcol, col, agg, mask=None):
    """Month-of-year and weekday multiplicative indices estimated from the finest available series.
    Returns dict kind -> (index Series, p, eta2)."""
    res = {}
    dates = (ctx.df if mask is None else ctx.df[mask])[dcol].dropna()
    span = (dates.max() - dates.min()).days
    if agg == "mean" and col is not None:
        return _calendar_effects_rows(ctx, dcol, col, dates, span)
    derived = bool(ctx.roles[dcol].get("derived_from"))
    daily_ok = (not derived) and dates.dt.normalize().nunique() >= 0.5 * (span + 1) and span >= 56
    if daily_ok:
        s = _period_series(ctx, dcol, "D", col, agg, mask, robust=True)
        idx_dt = s.index.to_timestamp()
    else:
        s = _period_series(ctx, dcol, "M", col, agg, mask, robust=True)
        idx_dt = s.index.to_timestamp()
    s = s.dropna()
    idx_dt = s.index.to_timestamp()
    y = s.to_numpy(float)
    if len(y) < 24 or (y < 0).any() or y.mean() <= 0:
        return res
    t = np.arange(len(y), dtype=float)
    fit = np.polyval(np.polyfit(t, y, 1), t)
    if (fit <= 0).any():
        fit = np.full_like(y, y.mean())
    ratio = y / fit
    rk = pd.Series(ratio).rank().to_numpy()  # rank-ANOVA (~Kruskal-Wallis): robust to heavy tails
    if span >= 2 * 365 - 31 or (not daily_ok and len(y) >= 24):
        months = idx_dt.month.to_numpy()
        groups = [ratio[months == m] for m in range(1, 13)]
        if all(len(g) >= 2 for g in groups):
            F, p, eta2 = st.anova_oneway([rk[months == m] for m in range(1, 13)])
            ix = pd.Series([g.mean() for g in groups], index=range(1, 13))
            res["month"] = (ix / ix.mean(), p, eta2)
    if daily_ok:
        wd = idx_dt.weekday.to_numpy()
        groups = [ratio[wd == k] for k in range(7)]
        if all(len(g) >= 4 for g in groups):
            F, p, eta2 = st.anova_oneway([rk[wd == k] for k in range(7)])
            ix = pd.Series([g.mean() for g in groups], index=range(7))
            res["weekday"] = (ix / ix.mean(), p, eta2)
    return res


def _calendar_effects_rows(ctx, dcol, col, dates, span):
    """For averages/rates: compare row-level values across calendar groups (daily means are too noisy)."""
    res = {}
    y = ctx.num(col)[dates.index]
    ok = y.notna()
    y, d = y[ok].to_numpy(float), dates[ok]
    if len(y) < 100 or y.mean() == 0:
        return res
    rk = pd.Series(y).rank().to_numpy()
    derived = bool(ctx.roles[dcol].get("derived_from"))
    kinds = []
    if span >= 2 * 365 - 31:
        kinds.append(("month", d.dt.month.to_numpy(), range(1, 13)))
    if not derived and d.dt.normalize().nunique() >= 0.5 * (span + 1) and span >= 56:
        kinds.append(("weekday", d.dt.weekday.to_numpy(), range(7)))
    for kind, key, levels in kinds:
        groups = [y[key == k] for k in levels]
        if any(len(g) < 30 for g in groups):
            continue
        F, p, eta2 = st.anova_oneway([rk[key == k] for k in levels])
        ix = pd.Series([g.mean() for g in groups], index=list(levels))
        res[kind] = (ix / y.mean(), p, eta2)
    return res


def _deseason(s, month_idx):
    if month_idx is None:
        return s.to_numpy(float)
    months = np.array([p.start_time.month if hasattr(p, "start_time") else p.month for p in s.index])
    return s.to_numpy(float) / month_idx.loc[months].to_numpy()


def _fit_level_shift(y, min_seg=3):
    """y = a + b t + c*[t>=k]; search k over the central 70% (Andrews 15% trimming).
    p-value of sup-F approximated by pointwise p x 20 (matches Andrews' 1%/5% critical values for q=1)."""
    n = len(y)
    min_seg = max(min_seg, int(math.ceil(0.15 * n)))
    t = np.arange(n, dtype=float)
    X0 = np.column_stack([np.ones(n), t])
    beta0, *_ = np.linalg.lstsq(X0, y, rcond=None)
    sse0 = float(((y - X0 @ beta0) ** 2).sum())
    best = None
    for k in range(min_seg, n - min_seg + 1):
        X = np.column_stack([np.ones(n), t, (t >= k).astype(float)])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        sse = float(((y - X @ beta) ** 2).sum())
        if best is None or sse < best[1]:
            best = (k, sse, beta)
    if best is None or sse0 <= 0:
        return None
    k, sse1, beta = best
    df2 = n - 3
    if df2 <= 0 or sse1 <= 0:
        return None
    F = (sse0 - sse1) / (sse1 / df2)
    p = min(1.0, st.f_sf(F, 1, df2) * min(20, n - 2 * min_seg + 1))
    return k, float(beta[2]), p, (sse0 - sse1) / sse0


def _names(ctx, col, agg):
    if col is None:
        return "số dòng", "row count"
    if agg == "sum":
        return f"tổng `{col}`", f"total `{col}`"
    if ctx.is_rate(col):
        return f"tỉ lệ `{ctx.label(col)}`", f"`{ctx.label(col)}` rate"
    return f"`{col}` trung bình", f"average `{col}`"


def _cap(s):
    return s[0].upper() + s[1:]


def mine_time(ctx, max_segments_dims=4):
    out = []
    for dcol in ctx.dates[:2]:
        dates = ctx.df[dcol].dropna()
        if dates.nunique() < 8:
            continue
        freq = _freq(dates, bool(ctx.roles[dcol].get("derived_from")))
        if freq is None:
            continue
        counts = _period_series(ctx, dcol, freq)
        series_defs = []
        if counts.nunique() > 1:
            series_defs.append((None, "count"))
        series_defs += [(m, "sum") for m in ctx.sum_measures]
        series_defs += [(m, "mean") for m in ctx.cont + ctx.binaries if m not in ctx.sum_measures]
        fname = FNAME[freq]
        for col, agg in series_defs:
            s_raw = _trim_edges(_period_series(ctx, dcol, freq, col, agg), counts).dropna()
            s = _period_series(ctx, dcol, freq, col, agg, robust=True).reindex(s_raw.index)
            if len(s) < 8:
                continue
            nvi, nen = _names(ctx, col, agg)
            vf = (lambda v: pct(v)) if (col is not None and ctx.is_rate(col)) else fmt
            cols = [dcol] + ([col] if col else [])
            w_main = 1.0 if agg in ("sum", "count") else 0.8
            y_raw = s_raw.to_numpy(float)
            chart = {"kind": "line", "labels": [_plabel(p) for p in s_raw.index], "values": [float(v) for v in y_raw]}

            cal = _calendar_effects(ctx, dcol, col, agg)
            month_idx = None
            if "month" in cal:
                idx, p_s, eta2 = cal["month"]
                if p_s < ALPHA and (idx.max() - 1 >= 0.12 or 1 - idx.min() >= 0.12):
                    month_idx = idx
                    pk, tr = int(idx.idxmax()), int(idx.idxmin())
                    out.append(ins("seasonality", cols, min(1, 0.6 * (idx.max() - idx.min()) + 0.8 * math.sqrt(eta2)) * w_main, 1,
                                   T(f"{_cap(nvi)} có tính mùa vụ theo tháng: cao nhất vào {MONTH_VI[pk]} (cao hơn {pct(idx[pk] - 1, 0)} so với mức xu hướng), thấp nhất vào {MONTH_VI[tr]} ({pct(idx[tr] - 1, 0)}).",
                                     f"{_cap(nen)} is seasonal by month: peaks in {MONTH_EN[pk]} ({pct(idx[pk] - 1, 0)} above trend), lowest in {MONTH_EN[tr]} ({pct(idx[tr] - 1, 0)})."),
                                   facts={"peak_month": MONTH_EN[pk], "peak_uplift": pct(idx[pk] - 1, 0),
                                          "trough_month": MONTH_EN[tr], "trough_change": pct(idx[tr] - 1, 0)},
                                   p=p_s, chart={"kind": "bar", "labels": MONTH_EN[1:],
                                                 "values": [float(v) for v in idx.values * 100],
                                                 "highlight": [MONTH_EN[pk]]}))
            if "weekday" in cal:
                idx, p_s, eta2 = cal["weekday"]
                if p_s < ALPHA and (idx.max() - 1 >= 0.1 or 1 - idx.min() >= 0.1):
                    pk, tr = int(idx.idxmax()), int(idx.idxmin())
                    out.append(ins("seasonality", cols + ["weekday"], min(1, 0.6 * (idx.max() - idx.min()) + 0.8 * math.sqrt(eta2)) * w_main, 1,
                                   T(f"{_cap(nvi)} thay đổi theo ngày trong tuần: cao nhất vào {WD_VI[pk]} ({'+' if idx[pk] >= 1 else ''}{pct(idx[pk] - 1, 0)} so với trung bình), thấp nhất vào {WD_VI[tr]} ({pct(idx[tr] - 1, 0)}).",
                                     f"{_cap(nen)} varies by weekday: highest on {WD_EN[pk]} ({'+' if idx[pk] >= 1 else ''}{pct(idx[pk] - 1, 0)} vs. average), lowest on {WD_EN[tr]} ({pct(idx[tr] - 1, 0)})."),
                                   facts={"peak_day": WD_EN[pk], "peak_uplift": pct(idx[pk] - 1, 0),
                                          "low_day": WD_EN[tr], "low_change": pct(idx[tr] - 1, 0)}, p=p_s,
                                   chart={"kind": "bar", "labels": WD_EN, "values": [float(v) for v in idx.values * 100],
                                          "highlight": [WD_EN[pk]]}))

            y = _deseason(s, month_idx)
            t = np.arange(len(y))
            # trend
            z, p_t, sen = st.mann_kendall(y)
            b, a = np.polyfit(t, y, 1)
            start, end = a, a + b * (len(y) - 1)
            change = (end - start) / abs(start) if abs(start) > 1e-12 else np.nan
            if p_t < 0.01 and np.isfinite(change) and abs(change) >= 0.1 and np.sign(change) == np.sign(z):
                up = change > 0
                out.append(ins("trend", cols, (0.5 * min(1, abs(change)) + 0.5 * min(1, abs(z) / 8)) * w_main, 1,
                               T(f"{_cap(nvi)} có xu hướng {'tăng' if up else 'giảm'} rõ rệt theo {fname[0]}: đường xu hướng đi từ khoảng {vf(start)} ({_plabel(s.index[0])}) {'lên' if up else 'xuống'} {vf(end)} ({_plabel(s.index[-1])}), tức {'+' if up else ''}{pct(change, 0)}.",
                                 f"{_cap(nen)} shows a clear {'upward' if up else 'downward'} {fname[1]}ly trend: the trend line moves from about {vf(start)} ({_plabel(s.index[0])}) to {vf(end)} ({_plabel(s.index[-1])}), {'+' if up else ''}{pct(change, 0)}."),
                               facts={"start_period": _plabel(s.index[0]), "end_period": _plabel(s.index[-1]),
                                      "trend_start": vf(start), "trend_end": vf(end),
                                      "trend_change": ('+' if up else '') + pct(change, 0),
                                      "mann_kendall_z": f"{z:.1f}"}, p=p_t, chart=chart))
            # structural break
            if len(y) >= 10:
                r = _fit_level_shift(y)
                if r:
                    k, c, p_c, gain = r
                    level = float(np.mean(np.abs(y[:k])))
                    rel = c / level if level else np.nan
                    if p_c < ALPHA and np.isfinite(rel) and abs(rel) >= 0.2 and gain >= 0.15:
                        before, after = float(np.mean(y_raw[:k])), float(np.mean(y_raw[k:]))
                        out.append(ins("change_point", cols, min(1, abs(rel)) * w_main, 1,
                                       T(f"{_cap(nvi)} có điểm gãy tại {_plabel(s.index[k])}: mức nền {'tăng' if c > 0 else 'giảm'} đột ngột khoảng {pct(abs(rel), 0)} (trung bình mỗi {fname[0]} trước đó {vf(before)}, sau đó {vf(after)}).",
                                         f"{_cap(nen)} has a structural break at {_plabel(s.index[k])}: the level {'jumps up' if c > 0 else 'drops'} by about {pct(abs(rel), 0)} (per-{fname[1]} mean before {vf(before)}, after {vf(after)})."),
                                       facts={"break_period": _plabel(s.index[k]), "shift": pct(rel, 0),
                                              "mean_before": vf(before), "mean_after": vf(after)},
                                       p=p_c, chart={**chart, "marker": _plabel(s.index[k])}))
            # anomalous periods on raw values vs robust expectation
            if len(y) >= 12:
                fit = np.polyval(np.polyfit(t, y, 1), t)
                seas = y_raw / np.where(_deseason(s_raw, month_idx) == 0, 1, _deseason(s_raw, month_idx)) if month_idx is not None else np.ones(len(y))
                expected = fit * seas
                res = s.to_numpy(float) - expected  # robust series: single extreme rows are not "anomalous periods"
                mad = np.median(np.abs(res - np.median(res))) * 1.4826
                if mad > 0:
                    zz = (res - np.median(res)) / mad
                    for i in np.argsort(-np.abs(zz))[:2]:
                        if abs(zz[i]) >= 6 and abs(y_raw[i] / expected[i] - 1) >= 0.5 if expected[i] else False:
                            out.append(ins("anomaly_period", cols, min(1, abs(zz[i]) / 12) * w_main, 0.5,
                                           T(f"{_cap(nvi)} bất thường tại {_plabel(s.index[i])}: {vf(y_raw[i])} so với mức kỳ vọng khoảng {vf(expected[i])} (đã tính xu hướng và mùa vụ).",
                                             f"Unusual {nen} in {_plabel(s.index[i])}: {vf(y_raw[i])} vs. about {vf(expected[i])} expected (after trend and seasonality)."),
                                           facts={"period": _plabel(s.index[i]), "value": vf(y_raw[i]),
                                                  "expected": vf(expected[i]), "robust_z": f"{zz[i]:.1f}"},
                                           chart={**chart, "marker": _plabel(s.index[i])}))
        out += _segment_time(ctx, dcol, freq, counts, max_segments_dims)
    return out


def _segment_time(ctx, dcol, freq, counts, max_dims):
    """Find segments whose level shifted or whose trend diverges from the overall series."""
    out = []
    dims = [d for d in ctx.dims if not ctx.roles[d].get("ordinal") and 2 <= ctx.roles[d]["n_unique"] <= 12][:max_dims]
    targets = [(m, "sum") for m in ctx.sum_measures[:2]] or [(None, "count")]
    fname = FNAME[freq]
    for m, agg in targets:
        total_raw = _trim_edges(_period_series(ctx, dcol, freq, m, agg), counts).dropna()
        if len(total_raw) < 10:
            continue
        total_s = _period_series(ctx, dcol, freq, m, agg, robust=True).reindex(total_raw.index)
        total = total_s.to_numpy(float)
        cal = _calendar_effects(ctx, dcol, m, agg)  # overall seasonality (more stable than per segment)
        mi = cal["month"][0] if "month" in cal and cal["month"][1] < ALPHA else None
        ty = _deseason(total_s, mi)
        tt = np.arange(len(ty)); tb, ta = np.polyfit(tt, ty, 1)
        tot_ch = (tb * (len(ty) - 1)) / ta if ta > 0 else 0
        for d in dims:
            trend_cands = []
            for g in _groups(ctx, d)[:12]:
                mask = ctx.df[d] == g
                if mask.mean() < 0.03:
                    continue
                s = _period_series(ctx, dcol, freq, m, agg, mask=mask, robust=True).reindex(total_raw.index).fillna(0)
                if (s > 0).mean() < 0.8:
                    continue
                y = s.to_numpy(float)
                y_ds = _deseason(s, mi)
                r = _fit_level_shift(y_ds)
                if not r:
                    continue
                k, c, p_c, gain = r
                lvl = np.mean(y_ds[:k])
                rel = c / lvl if lvl else 0
                tot_rel = (total[k:].mean() - total[:k].mean()) / total[:k].mean() if total[:k].mean() else 0
                seg_rel = (y[k:].mean() - y[:k].mean()) / y[:k].mean() if y[:k].mean() else 0
                # trend divergence vs overall
                zt, pt, _ = st.mann_kendall(y_ds)
                tt = np.arange(len(y_ds))
                bb, aa = np.polyfit(tt, y_ds, 1)
                ch = (bb * (len(y_ds) - 1)) / aa if aa > 0 else 0
                trend_cands.append((pt, zt, ch, d, g, mask.mean(), s))
                if p_c < ALPHA and abs(rel) >= 0.25 and gain >= 0.1 and abs(seg_rel - tot_rel) >= 0.25:
                    wvi, wen = (f"`{m}`", f"`{m}`") if m else ("số dòng", "row count")
                    bp = _plabel(s.index[k])
                    out.append(ins("segment_change", [dcol, d] + ([m] if m else []), min(1, abs(rel)),
                                   float(mask.mean()),
                                   T(f"Nhóm `{d}={g}` có {wvi} {'tăng vọt' if c > 0 else 'sụt giảm'} từ {bp}: trung bình mỗi {fname[0]} {'+' if seg_rel > 0 else ''}{pct(seg_rel, 0)} so với giai đoạn trước, trong khi toàn bộ dữ liệu {'+' if tot_rel > 0 else ''}{pct(tot_rel, 0)}.",
                                     f"Segment `{d}={g}` saw {wen} {'surge' if c > 0 else 'fall'} from {bp}: per-{fname[1]} average {'+' if seg_rel > 0 else ''}{pct(seg_rel, 0)} vs. before, while the overall moved {'+' if tot_rel > 0 else ''}{pct(tot_rel, 0)}."),
                                   facts={"segment": f"{d}={g}", "break_period": bp,
                                          "segment_change": ('+' if seg_rel > 0 else '') + pct(seg_rel, 0),
                                          "overall_change": ('+' if tot_rel > 0 else '') + pct(tot_rel, 0)},
                                   p=p_c, chart={"kind": "line", "labels": [_plabel(p) for p in s.index],
                                                 "values": [float(v) for v in y], "marker": bp}))
            # segments trending against / far from the overall trend (Bonferroni over segments)
            ncand = max(1, len(trend_cands))
            for pt, zt, ch, dd, g, share, s in trend_cands:
                if pt * ncand < 0.01 and abs(ch - tot_ch) >= 0.3 and abs(ch) >= 0.15:
                    wvi, wen = (f"`{m}`", f"`{m}`") if m else ("số dòng", "row count")
                    up = ch > 0
                    out.append(ins("segment_trend", [dcol, dd] + ([m] if m else []),
                                   min(1, abs(ch - tot_ch)), float(share),
                                   T(f"Nhóm `{dd}={g}` có {wvi} {'tăng' if up else 'giảm'} {'+' if up else ''}{pct(ch, 0)} theo đường xu hướng trong kỳ, khác biệt so với toàn bộ dữ liệu ({'+' if tot_ch > 0 else ''}{pct(tot_ch, 0)}).",
                                     f"Segment `{dd}={g}` {wen} {'grew' if up else 'declined'} {'+' if up else ''}{pct(ch, 0)} along its trend line over the period, diverging from the overall ({'+' if tot_ch > 0 else ''}{pct(tot_ch, 0)})."),
                                   facts={"segment": f"{dd}={g}", "segment_trend": ('+' if up else '') + pct(ch, 0),
                                          "overall_trend": ('+' if tot_ch > 0 else '') + pct(tot_ch, 0)}, p=pt,
                                   chart={"kind": "line", "labels": [_plabel(p) for p in s.index],
                                          "values": [float(v) for v in s.to_numpy(float)]}))
    return out


# ======================= DRIVERS OF A TARGET =======================
TARGET_HINTS = r"(survived|churn|target|label|outcome|default|fraud|converted|returned|clicked|purchased|y$|class$|alive)"


def pick_target(ctx):
    if ctx.target:
        return ctx.target if ctx.target in ctx.roles else None
    cands = [c for c in ctx.binaries if re.search(TARGET_HINTS, c.lower()) and c not in ctx.secondary]
    if not cands:  # target hinted but redundant -> use its kept twin
        for c in ctx.binaries:
            if re.search(TARGET_HINTS, c.lower()):
                twin = [b for b in ctx.binaries if b != c and b not in ctx.secondary and frozenset((b, c)) in ctx.redundant_pairs]
                if twin:
                    return twin[0]
    return cands[0] if cands else None


def mine_drivers(ctx, redundant=()):
    tgt = pick_target(ctx)
    if not tgt:
        return []
    df, y = ctx.df, ctx.num(tgt) if ctx.roles[tgt]["role"] in ("binary", "measure") else None
    if y is None:
        return []
    red = {b for a, b, _ in redundant if a == tgt} | {a for a, b, _ in redundant if b == tgt}
    red |= ctx.secondary | {c for pr in ctx.trivial if tgt in pr for c in pr}
    scores = []
    for c in ctx.measures:
        if c == tgt or c in red:
            continue
        r, p, _ = st.corr_test(ctx.num(c), y, "spearman")
        if np.isfinite(r) and p < ALPHA:
            scores.append((abs(r), c, f"ρ={r:.2f}"))
    for d in dict.fromkeys(ctx.dims):
        if d == tgt or d in red:
            continue
        keep = _groups(ctx, d)
        gs = [y[df[d] == g].dropna().to_numpy() for g in keep]
        F, p, eta2 = st.anova_oneway(gs)
        if p < ALPHA:
            scores.append((math.sqrt(eta2), d, f"η={math.sqrt(eta2):.2f}"))
    scores.sort(reverse=True)
    seen, top = set(), []
    for sc in scores:
        if sc[1] not in seen:
            seen.add(sc[1]); top.append(sc)
    top = top[:5]
    if len(top) < 2:
        return []
    lst = ", ".join(f"`{c}` ({s})" for _, c, s in top)
    return [ins("drivers", [tgt] + [c for _, c, _ in top], top[0][0], 1,
                T(f"Các yếu tố liên quan mạnh nhất tới `{ctx.label(tgt)}` (theo thứ tự): {lst}.",
                  f"Strongest factors associated with `{ctx.label(tgt)}` (ranked): {lst}."),
                facts={"target": tgt, "drivers": [{"column": c, "strength": s} for _, c, s in top]},
                chart={"kind": "bar", "labels": [c for _, c, _ in top], "values": [float(v) for v, _, _ in top],
                       "unit": ""})]


def redundancy_insights(pairs, kind):
    out = []
    for a, b, v in pairs:
        lab = "ρ" if kind == "num" else "V"
        out.append(ins("redundancy", [a, b], 0.5, 0.3,
                       T(f"`{a}` và `{b}` gần như trùng thông tin ({lab} = {v:.2f}) — có thể giữ một cột.",
                         f"`{a}` and `{b}` carry nearly identical information ({lab} = {v:.2f}) — keep one."),
                       facts={"stat": f"{v:.2f}"}))
    return out
