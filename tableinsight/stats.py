"""Small statistics toolkit (numpy only, no scipy dependency)."""
import math
import numpy as np


# ---------- special functions (Numerical Recipes style) ----------
def _betacf(a, b, x, itmax=300, eps=3e-14):
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d; d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1.0 + aa / c; c = c if abs(c) > 1e-300 else 1e-300
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d; d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1.0 + aa / c; c = c if abs(c) > 1e-300 else 1e-300
        de = d * c
        h *= de
        if abs(de - 1.0) < eps:
            break
    return h


def betai(a, b, x):
    """Regularized incomplete beta I_x(a,b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    bt = math.exp(lbt)
    if x < (a + 1) / (a + b + 2):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1 - x) / b


def gammaincc(a, x):
    """Regularized upper incomplete gamma Q(a,x)."""
    if x <= 0:
        return 1.0
    if x < a + 1:  # series for P
        ap, s, d = a, 1.0 / a, 1.0 / a
        for _ in range(1000):
            ap += 1; d *= x / ap; s += d
            if abs(d) < abs(s) * 1e-15:
                break
        return max(0.0, 1.0 - s * math.exp(-x + a * math.log(x) - math.lgamma(a)))
    b = x + 1 - a; c = 1e300; d = 1 / b; h = d
    for i in range(1, 1000):
        an = -i * (i - a); b += 2
        d = an * d + b; d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c; c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d; de = d * c; h *= de
        if abs(de - 1) < 1e-15:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def norm_sf(z):
    return 0.5 * math.erfc(z / math.sqrt(2))


def t_sf2(t, df):
    """Two-sided p-value for Student t."""
    if df <= 0 or not np.isfinite(t):
        return 0.0 if np.isfinite(df) and abs(t) == np.inf else 1.0
    return betai(df / 2.0, 0.5, df / (df + t * t))


def f_sf(F, d1, d2):
    if F <= 0 or d1 <= 0 or d2 <= 0:
        return 1.0
    return betai(d2 / 2.0, d1 / 2.0, d2 / (d2 + d1 * F))


def chi2_sf(x, k):
    return gammaincc(k / 2.0, x / 2.0)


# ---------- tests ----------
def rankdata(a):
    s = pd_rank(a)
    return s


def pd_rank(a):
    import pandas as pd
    return pd.Series(a).rank(method="average").to_numpy()


def corr_test(x, y, method="spearman"):
    x = np.asarray(x, float); y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    n = len(x)
    if n < 8 or np.std(x) == 0 or np.std(y) == 0:
        return np.nan, 1.0, n
    if method == "spearman":
        x, y = pd_rank(x), pd_rank(y)
    r = float(np.corrcoef(x, y)[0, 1])
    r = max(min(r, 0.999999), -0.999999)
    t = r * math.sqrt((n - 2) / (1 - r * r))
    return r, t_sf2(t, n - 2), n


def anova_oneway(groups):
    """Returns F, p, eta^2."""
    groups = [np.asarray(g, float)[np.isfinite(g)] for g in groups]
    groups = [g for g in groups if len(g) > 1]
    k = len(groups)
    if k < 2:
        return np.nan, 1.0, 0.0
    allv = np.concatenate(groups)
    n = len(allv); gm = allv.mean()
    ssb = sum(len(g) * (g.mean() - gm) ** 2 for g in groups)
    ssw = sum(((g - g.mean()) ** 2).sum() for g in groups)
    sst = ssb + ssw
    if ssw == 0:
        return np.inf, 0.0, 1.0 if sst > 0 else 0.0
    F = (ssb / (k - 1)) / (ssw / (n - k))
    return F, f_sf(F, k - 1, n - k), ssb / sst if sst > 0 else 0.0


def welch_t(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if len(a) < 2 or len(b) < 2:
        return 0.0, 1.0
    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
    if va + vb == 0:
        return (np.inf, 0.0) if a.mean() != b.mean() else (0.0, 1.0)
    t = (a.mean() - b.mean()) / math.sqrt(va + vb)
    df = (va + vb) ** 2 / ((va ** 2) / (len(a) - 1) + (vb ** 2) / (len(b) - 1) + 1e-300)
    return t, t_sf2(t, df)


def cramers_v(ct):
    """ct: 2D numpy contingency table. Returns V (bias corrected), chi2 p-value."""
    ct = np.asarray(ct, float)
    ct = ct[ct.sum(1) > 0][:, ct.sum(0) > 0]
    if ct.shape[0] < 2 or ct.shape[1] < 2:
        return 0.0, 1.0
    n = ct.sum()
    exp = np.outer(ct.sum(1), ct.sum(0)) / n
    chi2 = float(((ct - exp) ** 2 / exp).sum())
    r, k = ct.shape
    p = chi2_sf(chi2, (r - 1) * (k - 1))
    phi2 = chi2 / n
    phi2c = max(0.0, phi2 - (k - 1) * (r - 1) / (n - 1))
    rc = r - (r - 1) ** 2 / (n - 1); kc = k - (k - 1) ** 2 / (n - 1)
    denom = min(kc - 1, rc - 1)
    v = math.sqrt(phi2c / denom) if denom > 0 else 0.0
    return min(v, 1.0), p


def mann_kendall(y):
    """Returns (S-based z, p two-sided, Sen's slope per step)."""
    y = np.asarray(y, float); y = y[np.isfinite(y)]
    n = len(y)
    if n < 6:
        return 0.0, 1.0, 0.0
    d = np.sign(y[None, :] - y[:, None])
    s = np.triu(d, 1).sum()
    _, counts = np.unique(y, return_counts=True)
    var = (n * (n - 1) * (2 * n + 5) - (counts * (counts - 1) * (2 * counts + 5)).sum()) / 18.0
    z = 0.0 if s == 0 else (s - np.sign(s)) / math.sqrt(var)
    i, j = np.triu_indices(n, 1)
    sen = float(np.median((y[j] - y[i]) / (j - i)))
    return z, 2 * norm_sf(abs(z)), sen


def skewness(x):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    if len(x) < 8 or x.std() == 0:
        return 0.0
    return float(((x - x.mean()) ** 3).mean() / x.std() ** 3)


def gini(x):
    x = np.sort(np.asarray(x, float)); x = x[np.isfinite(x)]
    if len(x) == 0 or x.sum() <= 0 or (x < 0).any():
        return np.nan
    n = len(x)
    return float((2 * np.arange(1, n + 1) - n - 1).dot(x) / (n * x.sum()))


def best_mean_shift(y, min_seg=3):
    """Single change point by max reduction in SSE. Returns (idx, before_mean, after_mean, p)."""
    y = np.asarray(y, float)
    n = len(y)
    if n < 2 * min_seg + 1:
        return None
    best, bi = None, None
    c = np.cumsum(y); c2 = np.cumsum(y * y); tot = c[-1]; tot2 = c2[-1]
    for i in range(min_seg, n - min_seg + 1):
        n1, n2 = i, n - i
        s1, s2 = c[i - 1], tot - c[i - 1]
        sse = (c2[i - 1] - s1 * s1 / n1) + ((tot2 - c2[i - 1]) - s2 * s2 / n2)
        if best is None or sse < best:
            best, bi = sse, i
    a, b = y[:bi], y[bi:]
    _, p = welch_t(a, b)
    return bi, float(a.mean()), float(b.mean()), p
