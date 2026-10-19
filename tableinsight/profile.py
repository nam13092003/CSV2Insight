"""Load a CSV robustly and infer semantic column roles."""
import re
import warnings
import numpy as np
import pandas as pd

ADDITIVE_HINTS = r"(revenue|sales|amount|amt|total|sum|qty|quantity|units|count|volume|profit|cost|spend|income|" \
                 r"gmv|turnover|passengers|orders|visits|clicks|impressions|views|doanh|thu|so_luong|soluong|tien|chi_phi|chi_tieu|loi_nhuan|ban_ra)"
MEAN_HINTS = r"(price|rate|ratio|pct|percent|avg|mean|age|score|rating|satisf|discount|temp|margin|tuoi|gia|diem|ty_le)"
ID_HINTS = r"(^id$|_id$|^id_|uuid|code$|^ma_|^ma$|number$|^no$|phone|email|zip|postal)"
DATE_HINTS = r"(date|time|day|month|year|period|ngay|thang|nam|timestamp|created|updated|dt$)"
MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
     "November", "December"], 1)}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})


def read_csv_robust(path):
    last = None
    for enc in ("utf-8-sig", "utf-8", "cp1258", "latin-1"):
        try:
            df = pd.read_csv(path, sep=None, engine="python", encoding=enc)
            if df.shape[1] == 1 and ";" in str(df.columns[0]):
                df = pd.read_csv(path, sep=";", encoding=enc)
            return df
        except Exception as e:  # noqa
            last = e
    raise last


def _norm(s):
    return re.sub(r"[^a-z0-9]+", "_", str(s).strip().lower()).strip("_")


def is_text(s):
    return s.dtype == object or pd.api.types.is_string_dtype(s)


def _try_numeric(s):
    """Convert strings like '1,234.5', '$12', '45%' to numbers if >=95% parse."""
    if not is_text(s):
        return None
    x = s.dropna().astype(str).str.strip()
    if len(x) == 0:
        return None
    cleaned = x.str.replace(r"[\$€£₫%\s]", "", regex=True).str.replace(",", "", regex=False)
    num = pd.to_numeric(cleaned, errors="coerce")
    if num.notna().mean() >= 0.95:
        full = s.astype(str).str.strip().str.replace(r"[\$€£₫%\s]", "", regex=True).str.replace(",", "", regex=False)
        return pd.to_numeric(full, errors="coerce").where(s.notna())
    return None


def _try_datetime(s, name):
    if pd.api.types.is_datetime64_any_dtype(s):
        return s
    if is_text(s):
        x = s.dropna().astype(str)
        if len(x) == 0 or x.str.len().median() < 6:
            return None
        if not x.str.contains(r"\d", regex=True).mean() > 0.9:
            return None
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            best = None
            for kw in ({"format": "ISO8601"}, {"dayfirst": False}, {"dayfirst": True}):
                try:
                    d = pd.to_datetime(s, errors="coerce", **kw)
                except Exception:
                    continue
                ok = d.notna().sum() / max(1, s.notna().sum())
                if ok >= 0.9 and (best is None or ok > best[0]):
                    best = (ok, d)
            if best is not None:
                return best[1]
    return None


def infer_roles(df, overrides=None):
    """Return (clean_df, roles) where roles[col] = dict(role=..., agg=..., ...).
    roles: id | datetime | dimension | measure | binary | text | constant | empty
    """
    overrides = overrides or {}
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    n = len(df)
    roles = {}

    # derived date from year + month columns (e.g. flights)
    lower = {_norm(c): c for c in df.columns}
    if "year" in lower and "month" in lower and not any(
            re.search(r"date|time", _norm(c)) for c in df.columns):
        yc, mc = lower["year"], lower["month"]
        mm = df[mc]
        if is_text(mm):
            mm = mm.astype(str).str.strip().str.lower().map(lambda v: MONTHS.get(v, MONTHS.get(v[:3], np.nan)))
        mm = pd.to_numeric(mm, errors="coerce")
        yy = pd.to_numeric(df[yc], errors="coerce")
        if mm.between(1, 12).mean() > 0.95 and yy.between(1800, 2200).mean() > 0.95:
            df["_period"] = pd.to_datetime(dict(year=yy, month=mm, day=1), errors="coerce")
            roles["_period"] = {"role": "datetime", "derived_from": [yc, mc]}

    for c in list(df.columns):
        if c in roles:
            continue
        s = df[c]
        nc = _norm(c)
        nn = s.notna().sum()
        nun = s.nunique(dropna=True)
        info = {"missing_pct": float(1 - nn / n) if n else 0.0, "n_unique": int(nun)}
        if nn == 0:
            roles[c] = {"role": "empty", **info}; continue
        if nun == 1:
            roles[c] = {"role": "constant", **info}; continue

        if s.dtype == bool or (is_text(s) and set(s.dropna().astype(str).str.lower().unique()) <= {"true", "false"}):
            df[c] = s.map(lambda v: v if isinstance(v, bool) else (str(v).lower() == "true") if pd.notna(v) else np.nan)
            roles[c] = {"role": "binary", **info}; continue

        conv = _try_numeric(s)
        if conv is not None:
            df[c] = s = conv
        d = None
        if not pd.api.types.is_numeric_dtype(s):
            d = _try_datetime(s, c)
        if d is not None:
            df[c] = d
            roles[c] = {"role": "datetime", **info}; continue

        if pd.api.types.is_numeric_dtype(s):
            vals = s.dropna()
            is_int = bool((vals == vals.round()).all())
            if nun == 2:
                roles[c] = {"role": "binary", **info}; continue
            if is_int and (re.search(ID_HINTS, nc) or (nun / nn > 0.98 and vals.is_monotonic_increasing)):
                roles[c] = {"role": "id", **info}; continue
            if re.search(r"(^|_)(year|nam)$", nc) and vals.between(1800, 2200).all():
                roles[c] = {"role": "dimension", "ordinal": True, "is_year": True, **info}; continue
            if is_int and nun <= 12 and nun / nn < 0.05:
                # low-cardinality integer: ordinal dimension AND measure (e.g. pclass, size, rating)
                roles[c] = {"role": "measure", "also_dimension": True, "ordinal": True, **info}
            else:
                roles[c] = {"role": "measure", **info}
            if re.search(ADDITIVE_HINTS, nc) and not re.search(MEAN_HINTS, nc) and (vals >= 0).all():
                roles[c]["agg"] = "sum"
            else:
                roles[c]["agg"] = "mean"
            continue

        # object / string
        x = s.dropna().astype(str)
        avg_len = x.str.len().mean()
        ratio = nun / nn
        if re.search(ID_HINTS, nc) and ratio > 0.5 or ratio > 0.95 and nn > 50:
            roles[c] = {"role": "id" if avg_len < 25 and not x.str.contains(" ").mean() > 0.5 else "text", **info}
        elif nun == 2:
            roles[c] = {"role": "binary", **info}
        elif avg_len > 40 and ratio > 0.3:
            roles[c] = {"role": "text", **info}
        elif nun <= max(60, int(0.05 * nn)) or ratio < 0.5:
            roles[c] = {"role": "dimension", **info}
        else:
            roles[c] = {"role": "text", **info}

    # binary columns are usable as both dimension and rate measure
    for c, r in roles.items():
        if r["role"] == "binary":
            s = df[c]
            vals = sorted(s.dropna().unique(), key=lambda v: str(v))
            if not pd.api.types.is_numeric_dtype(s) or set(map(float, vals)) - {0.0, 1.0}:
                # map to 0/1 with "positive" class = minority or yes/true-like
                pos_words = {"yes", "y", "true", "1", "male", "survived", "churn", "fraud", "positive"}
                pos = next((v for v in vals if str(v).lower() in pos_words), None)
                if pos is None:
                    pos = s.value_counts().idxmin()
                r["positive"] = str(pos)
                r["levels"] = [str(v) for v in vals]
            else:
                r["positive"] = "1"
            r["agg"] = "mean"

    for c, o in overrides.items():
        if c in roles and isinstance(o, dict):
            roles[c].update({k: v for k, v in o.items() if k in ("role", "agg", "desc")})
    return df, roles


def binary_as_float(s, role):
    if pd.api.types.is_numeric_dtype(s) and role.get("positive") == "1":
        return s.astype(float)
    pos = role.get("positive")
    return s.map(lambda v: np.nan if pd.isna(v) else float(str(v) == pos))


def summarize_columns(df, roles):
    out = []
    for c, r in roles.items():
        s = df[c]
        e = {"column": c, **{k: v for k, v in r.items()}}
        if r["role"] in ("measure",):
            v = s.dropna()
            e.update(min=float(v.min()), max=float(v.max()), mean=float(v.mean()), median=float(v.median()))
        elif r["role"] in ("dimension", "binary"):
            vc = s.value_counts().head(5)
            e["top_values"] = {str(k): int(v) for k, v in vc.items()}
        elif r["role"] == "datetime":
            v = s.dropna()
            e.update(min=str(v.min().date()), max=str(v.max().date()))
        out.append(e)
    return out
