"""Core of the ICT study: bars, causal features, setup detection and the 1m execution engine.

Every rule here implements PREREGISTRATION.md; section numbers (§) refer to that file.
Conventions:
  * timestamps are int64 nanoseconds since epoch (UTC), bars labeled by OPEN time;
    a bar is known only at open + bar length.
  * direction: +1 = long, -1 = short.
"""
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
TZ = "America/Chicago"
TICK = 0.25
PT_VALUE = 2.0          # $ per point, 1 MNQ contract
COMMISSION = 1.00       # $ round trip
NS_MIN = 60 * 10**9
NS_5M = 5 * NS_MIN
NS_H = 60 * NS_MIN

# window name -> (start "HH:MM", end "HH:MM", levels)
WINDOWS = {
    "NYAM": ("08:30", "11:00", ("PDH", "PDL", "ONH", "ONL")),
    "SBAM": ("09:00", "10:00", ("PDH", "PDL", "ONH", "ONL")),
    "SBPM": ("13:00", "14:00", ("PDH", "PDL", "ONH", "ONL")),
    "ASIA": ("17:00", "20:00", ("PDH", "PDL")),
}
HIGH_LEVELS = ("PDH", "ONH")     # priority order (§3 sweep labeling)
LOW_LEVELS = ("PDL", "ONL")


def hm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


# ----------------------------------------------------------------------------- data

def load_1m(path=None):
    """Adjusted 1m bars as a DataFrame indexed by UTC ns timestamps (explicit unit)."""
    path = path or os.path.join(HERE, "data", "mnq_1m_adj.parquet")
    df = pd.read_parquet(path)
    df.index = pd.DatetimeIndex(df.index).as_unit("ns")
    assert str(df.index.dtype) == "datetime64[ns, UTC]"
    assert df.index.is_monotonic_increasing and df.index.is_unique
    return df


def load_rolls(path=None):
    path = path or os.path.join(HERE, "data", "roll_log.csv")
    r = pd.read_csv(path)
    return pd.DatetimeIndex(pd.to_datetime(r["roll_ts_utc"], utc=True)).as_unit("ns").asi8


def _ct_fields(ts_ns):
    ct = pd.DatetimeIndex(ts_ns.astype("datetime64[ns]"), tz="UTC").tz_convert(TZ)
    tod = (ct.hour * 60 + ct.minute).to_numpy()
    date = ct.tz_localize(None).normalize().to_numpy().astype("datetime64[D]")
    sess = (ct + pd.Timedelta(hours=7)).tz_localize(None).normalize().to_numpy().astype("datetime64[D]")
    wd = ct.weekday.to_numpy()
    return tod, date, sess, wd


def ct_time_ns(date, hhmm):
    """CT wall-clock time on calendar date -> UTC ns (DST handled by tz database)."""
    return pd.Timestamp(f"{pd.Timestamp(date).date()} {hhmm}", tz=TZ).value


class Bars:
    """Plain numpy view of a bar series (1m, 5m or 1H)."""

    def __init__(self, df, length_ns):
        self.t = df.index.asi8.copy()              # open time, ns
        self.tc = self.t + length_ns              # close time (known time)
        self.o = df["open"].to_numpy(float)
        self.h = df["high"].to_numpy(float)
        self.l = df["low"].to_numpy(float)
        self.c = df["close"].to_numpy(float)
        self.tod, self.date, self.sess, self.wd = _ct_fields(self.t)
        self.n = len(self.t)


def resample(df1m, rule):
    """label=left, closed=left; only where 1m bars exist (partial bars kept)."""
    key = df1m.index.floor(rule)
    g = df1m.groupby(key)
    out = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(),
                        "low": g["low"].min(), "close": g["close"].last(),
                        "volume": g["volume"].sum()})
    out.index = pd.DatetimeIndex(out.index).as_unit("ns")
    return out


# ----------------------------------------------------------------------------- features

class Features:
    """All causal features. Each value carries (implicitly or explicitly) the time it becomes known."""

    def __init__(self, df1m):
        self.m1 = Bars(df1m, NS_MIN)
        df5 = resample(df1m, "5min")
        dfh = resample(df1m, "1h")
        self.b5 = b = Bars(df5, NS_5M)
        self.bh = Bars(dfh, NS_H)
        n = b.n
        # 1m index range of each 5m bar
        self.m1_start = np.searchsorted(self.m1.t, b.t, "left")
        self.m1_end = np.searchsorted(self.m1.t, b.tc, "left")

        # ATR(14), Wilder; atr_prev[i] = ATR at the close of bar i-1 (§2)
        prev_c = np.r_[np.nan, b.c[:-1]]
        tr = np.nanmax(np.vstack([b.h - b.l, np.abs(b.h - prev_c), np.abs(b.l - prev_c)]), axis=0)
        atr = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().to_numpy().copy()
        atr[:13] = np.nan
        self.atr = atr
        self.atr_prev = np.r_[np.nan, atr[:-1]]

        # swings: strict fractal N=3, confirmed at close of p+3 (§3)
        h, l = b.h, b.l
        sh = np.zeros(n, bool)
        sl = np.zeros(n, bool)
        for p in range(3, n - 3):
            if h[p] > h[p - 3:p].max() and h[p] > h[p + 1:p + 4].max():
                sh[p] = True
            if l[p] < l[p - 3:p].min() and l[p] < l[p + 1:p + 4].min():
                sl[p] = True
        self.swing_hi, self.swing_lo = sh, sl
        idx = np.arange(n)
        self.last_sh = np.maximum.accumulate(np.where(sh, idx, -1))   # latest pivot index <= i
        self.last_sl = np.maximum.accumulate(np.where(sl, idx, -1))

        # displacement (§3): body in signal direction >= ATR(prev), close beyond prior extreme
        body = b.c - b.o
        prev_l = np.r_[np.nan, l[:-1]]
        prev_h = np.r_[np.nan, h[:-1]]
        with np.errstate(invalid="ignore"):
            self.disp_bear = (b.c < prev_l) & (body < 0) & (-body >= self.atr_prev)
            self.disp_bull = (b.c > prev_h) & (body > 0) & (body >= self.atr_prev)

        self._levels()
        self._bias()

    def _levels(self):
        b = self.b5
        rth = (b.tod >= hm("08:30")) & (b.tod < hm("15:00"))
        d = pd.DataFrame({"date": b.date[rth], "h": b.h[rth], "l": b.l[rth]})
        g = d.groupby("date").agg(h=("h", "max"), l=("l", "min"))
        self.rth_dates = g.index.to_numpy()
        self.rth_hi = g["h"].to_numpy()
        self.rth_lo = g["l"].to_numpy()
        self.rth_end = np.array([ct_time_ns(x, "15:00") for x in self.rth_dates], dtype=np.int64)
        # PDH/PDL for bar i: most recent RTH session with end <= bar open (§2)
        k = np.searchsorted(self.rth_end, b.t, "right") - 1
        ok = k >= 0
        self.pd_idx = k
        self.PDH = np.where(ok, self.rth_hi[np.maximum(k, 0)], np.nan)
        self.PDL = np.where(ok, self.rth_lo[np.maximum(k, 0)], np.nan)
        self.PD_known = np.where(ok, self.rth_end[np.maximum(k, 0)], np.iinfo(np.int64).max)

        # ONH/ONL: bars of session S with CT open time < 08:30 on date S; usable from 08:30 (§2)
        sess_u = np.unique(b.sess)
        s0830 = {s: ct_time_ns(s, "08:30") for s in sess_u}
        t0830 = np.array([s0830[s] for s in b.sess], dtype=np.int64)
        is_on = b.t < t0830
        d = pd.DataFrame({"sess": b.sess[is_on], "h": b.h[is_on], "l": b.l[is_on]})
        g = d.groupby("sess").agg(h=("h", "max"), l=("l", "min"))
        onh = pd.Series(g["h"]).reindex(b.sess).to_numpy()
        onl = pd.Series(g["l"]).reindex(b.sess).to_numpy()
        usable = (b.t >= t0830) & (b.date == b.sess)
        self.ONH = np.where(usable, onh, np.nan)
        self.ONL = np.where(usable, onl, np.nan)
        self.ON_known = t0830

    def _bias(self):
        c = pd.Series(self.bh.c)
        e9 = c.ewm(span=9, adjust=False).mean().to_numpy()
        e21 = c.ewm(span=21, adjust=False).mean().to_numpy()
        e50 = c.ewm(span=50, adjust=False).mean().to_numpy()
        bias = np.where((e9 > e21) & (e21 > e50), 1, np.where((e9 < e21) & (e21 < e50), -1, 0))
        bias = bias.copy()
        bias[:50] = 0                                   # warm-up (§2)
        self.h_bias = bias

    def bias_at(self, t_ns):
        """Bias from completed 1H bars only (close <= t). Returns (bias, index of the 1H bar used)."""
        k = np.searchsorted(self.bh.tc, t_ns, "right") - 1
        return (int(self.h_bias[k]) if k >= 0 else 0), int(k)

    def level(self, name, i):
        return {"PDH": self.PDH, "PDL": self.PDL, "ONH": self.ONH, "ONL": self.ONL}[name][i]

    def level_known(self, name, i):
        return self.PD_known[i] if name in ("PDH", "PDL") else self.ON_known[i]


# ----------------------------------------------------------------------------- windows

def window_days(F, win):
    """dict day -> (first 5m idx with open >= start, idx end (exclusive, open < end), start_ns, end_ns)."""
    start, end, _ = WINDOWS[win]
    b = F.b5
    sel = np.where((b.tod >= hm(start)) & (b.tod < hm(end)))[0]
    out = {}
    if len(sel) == 0:
        return out
    dates = b.date[sel]
    for d in np.unique(dates):
        ii = sel[dates == d]
        out[d] = (int(ii[0]), int(ii[-1]) + 1, ct_time_ns(d, start), ct_time_ns(d, end))
    return out


def round_tick(x, side):
    """Nearest tick; exact ties toward the less favorable side (sell -> down, buy -> up)."""
    q = x / TICK
    f = np.floor(q + 1e-9)
    frac = q - f
    if abs(frac - 0.5) < 1e-9:
        q = f if side == "sell" else f + 1
    else:
        q = np.round(q)
    return round(float(q) * TICK, 2)


# ----------------------------------------------------------------------------- signals (§3)

def find_signals(F, win):
    """sweep -> MSS -> FVG signals inside a window. Deduplicated on (direction, MSS bar)."""
    b = F.b5
    _, _, levels = WINDOWS[win]
    sigs = {}
    for day, (i0, i1, ws, we) in window_days(F, win).items():
        for s in range(max(i0, 1), i1):
            for side in (+1, -1):                       # +1 = high sweep (short), -1 = low sweep (long)
                names = [x for x in (HIGH_LEVELS if side == 1 else LOW_LEVELS) if x in levels]
                found = None
                for name in names:
                    L = F.level(name, s)
                    if np.isnan(L):
                        continue
                    if side == 1:
                        if not (b.c[s - 1] < L and b.h[s] >= L + TICK):
                            continue
                        r = next((k for k in range(s, min(s + 3, b.n)) if b.c[k] < L), None)
                    else:
                        if not (b.c[s - 1] > L and b.l[s] <= L - TICK):
                            continue
                        r = next((k for k in range(s, min(s + 3, b.n)) if b.c[k] > L), None)
                    if r is None:
                        continue
                    found = (name, L, r)
                    break
                if found is None:
                    continue
                name, L, r = found
                ext = b.h[s:r + 1].max() if side == 1 else b.l[s:r + 1].min()
                # MSS: first displacement bar m in [s+1, s+12], m >= r, closing beyond the most recent
                # swing (pivot < s, confirmed by close of m-1)
                m = None
                ref = -1
                for k in range(max(s + 1, r), min(s + 13, b.n - 1)):
                    p = (F.last_sl if side == 1 else F.last_sh)[min(s - 1, k - 4)]
                    if p < 0:
                        continue
                    if side == 1 and F.disp_bear[k] and b.c[k] < b.l[p]:
                        m, ref = k, p
                        break
                    if side == -1 and F.disp_bull[k] and b.c[k] > b.h[p]:
                        m, ref = k, p
                        break
                if m is None or m + 1 >= b.n:
                    continue
                if b.tc[m + 1] > we:                      # arm time must be inside the window
                    continue
                # FVG centered on the MSS bar
                if side == 1:
                    gap = b.l[m - 1] - b.h[m + 1]
                    zone = (b.h[m + 1], b.l[m - 1])
                else:
                    gap = b.l[m + 1] - b.h[m - 1]
                    zone = (b.h[m - 1], b.l[m + 1])
                if not gap >= 2.0:
                    continue
                key = (side, m)
                if key in sigs:
                    continue
                if side == 1:
                    far = b.l[s:m + 1].min()
                else:
                    far = b.h[s:m + 1].max()
                mid = (zone[0] + zone[1]) / 2
                leg = abs(ext - far)
                rconf = ((mid - far) / (ext - far)) if leg > 0 else np.nan
                sigs[key] = dict(win=win, day=day, dir=-side, level=name, L=L, s=s, r=r, ext=ext,
                                 m=m, ref=ref, fvg_lo=zone[0], fvg_hi=zone[1], fvg_mid=mid, gap=gap,
                                 far=far, leg=leg, rconf=rconf, win_start=ws, win_end=we)
    return sorted(sigs.values(), key=lambda x: (x["m"], x["s"], x["dir"]))


def _finish(F, su, entry, stop, expiry_bar, arm_bar):
    b = F.b5
    d = su["dir"]
    su.update(entry=entry, stop=stop, R=abs(entry - stop), arm_bar=arm_bar,
              arm_time=int(b.tc[arm_bar]),
              expiry_time=int(min(b.tc[min(expiry_bar, b.n - 1)], su["win_end"])))
    su["bias"], su["bias_k"] = F.bias_at(su["arm_time"])
    if (d == -1 and b.c[arm_bar] >= entry) or (d == 1 and b.c[arm_bar] <= entry):
        su["status"] = "stale"
    elif su["R"] < 8:
        su["status"] = "skip_small"
    elif su["R"] > 40:
        su["status"] = "skip_large"
    return su


def setups_A(F, sigs):
    out = []
    for g in sigs:
        su = dict(g, model="A", status="ok")
        d = su["dir"]
        entry = round_tick(g["fvg_mid"], "sell" if d == -1 else "buy")
        stop = g["ext"] + 3 if d == -1 else g["ext"] - 3
        su["cancel_hi"] = g["ext"] + TICK if d == -1 else np.inf      # beyond the sweep extreme
        su["cancel_lo"] = -np.inf if d == -1 else g["ext"] - TICK
        su["close_cancel"] = None
        out.append(_finish(F, su, entry, stop, g["m"] + 1 + 12, g["m"] + 1))
    return out


def setups_B(F, sigs):
    b = F.b5
    out = []
    for g in sigs:
        su = dict(g, model="B", status="ok")
        d = su["dir"]
        H, far = g["ext"], g["far"]
        if d == -1:
            entry = round_tick(far + 0.705 * (H - far), "sell")
            stop = H + 3
            su["cancel_hi"], su["cancel_lo"] = H + TICK, far - TICK
        else:
            entry = round_tick(far - 0.705 * (far - H), "buy")
            stop = H - 3
            su["cancel_hi"], su["cancel_lo"] = far + TICK, H - TICK
        su["close_cancel"] = None
        m = g["m"]
        _finish(F, su, entry, stop, m + 12, m + 1)
        if g["leg"] < 20:
            su["status"] = "skip_leg"
        elif b.h[m + 1] >= su["cancel_hi"] or b.l[m + 1] <= su["cancel_lo"]:
            su["status"] = "cancel_prearm"                         # invalidated during bar m+1
        out.append(su)
    return out


def setups_D(F, win):
    b = F.b5
    out = []
    for day, (i0, i1, ws, we) in window_days(F, win).items():
        for dbar in range(max(i0, 5), i1):
            if b.tc[dbar] > we:
                continue
            for d in (-1, 1):
                if d == -1:
                    if not F.disp_bear[dbar]:
                        continue
                    p = F.last_sl[dbar - 4]
                    if p < 0 or not b.c[dbar] < b.l[p]:
                        continue
                    if (b.c[p + 4:dbar] < b.l[p]).any():          # already broken -> not the first BOS
                        continue
                    cand = [j for j in range(dbar - 5, dbar) if b.c[j] > b.o[j]]
                else:
                    if not F.disp_bull[dbar]:
                        continue
                    p = F.last_sh[dbar - 4]
                    if p < 0 or not b.c[dbar] > b.h[p]:
                        continue
                    if (b.c[p + 4:dbar] > b.h[p]).any():
                        continue
                    cand = [j for j in range(dbar - 5, dbar) if b.c[j] < b.o[j]]
                if not cand:
                    continue
                j = cand[-1]
                zlo, zhi = b.l[j], b.h[j]
                mid = (zlo + zhi) / 2
                su = dict(win=win, day=day, dir=d, model="D", status="ok", level="BOS", L=np.nan,
                          s=dbar, r=dbar, ext=np.nan, m=dbar, ref=int(p), ob=j, ob_lo=zlo, ob_hi=zhi,
                          fvg_lo=np.nan, fvg_hi=np.nan, fvg_mid=np.nan, gap=np.nan, far=np.nan,
                          leg=np.nan, rconf=np.nan, win_start=ws, win_end=we,
                          cancel_hi=np.inf, cancel_lo=-np.inf)
                if d == -1:
                    entry, stop = round_tick(mid, "sell"), zhi + 3
                    su["close_cancel"] = zhi                        # a 5m close above -> cancel
                else:
                    entry, stop = round_tick(mid, "buy"), zlo - 3
                    su["close_cancel"] = zlo
                out.append(_finish(F, su, entry, stop, dbar + 24, dbar))
    return sorted(out, key=lambda x: (x["arm_time"], x["s"], x["dir"]))


def build_setups(F, model, win, sigs=None):
    if model == "D":
        return setups_D(F, win)
    sigs = sigs if sigs is not None else find_signals(F, win)
    return setups_A(F, sigs) if model == "A" else setups_B(F, sigs)


# ----------------------------------------------------------------------------- execution (§6)

def exit_cutoff(F, win, k0):
    """Index of the last 1m bar allowed for a position filled on 1m bar k0."""
    m = F.m1
    if win == "ASIA":
        cut = min(m.t[k0] + 3 * NS_H, ct_time_ns(m.date[k0], "23:00"))
    else:
        cut = ct_time_ns(m.date[k0], "14:55")
    kx = np.searchsorted(m.t, cut, "left") - 1
    # never across the daily halt: stay inside the fill's session
    same = np.searchsorted(m.sess, m.sess[k0], "right") - 1
    return int(min(kx, same))


def simulate_exit(F, k0, kx, d, entry, stop, target, costs=True):
    """Exit of a position entered on 1m bar k0 (fill bar). Returns (k_exit, price, reason)."""
    m = F.m1
    sl = slice(k0, kx + 1)
    tk = TICK if costs else 0.0
    if d == -1:
        stop_hit = m.h[sl] >= stop
        tgt_hit = m.l[sl] <= target - TICK
    else:
        stop_hit = m.l[sl] <= stop
        tgt_hit = m.h[sl] >= target + TICK
    tgt_hit[0] = False                                        # no target credit in the fill bar
    ks = int(np.argmax(stop_hit)) if stop_hit.any() else None
    kt = int(np.argmax(tgt_hit)) if tgt_hit.any() else None
    if ks is not None and (kt is None or ks <= kt):           # stop first on ties
        k = k0 + ks
        if ks == 0:
            px = stop                                        # gap rule only after the fill bar
        else:
            px = max(stop, m.o[k]) if d == -1 else min(stop, m.o[k])
        return k, px - d * tk, "stop"
    if kt is not None:
        return k0 + kt, target, "target"
    return kx, m.c[kx] - d * tk, "time"


def target_price(entry, d, R, exit_rule):
    dist = 2 * R if exit_rule == "X1" else 40.0
    return round(entry + d * dist, 2)


def simulate_order(F, su):
    """Pending limit order. Returns (fill 1m index or None, end time ns, outcome)."""
    m, b = F.m1, F.b5
    d, entry = su["dir"], su["entry"]
    end = min(su["expiry_time"], su["win_end"])
    outcome_end = "expired"
    if su["close_cancel"] is not None:                         # Model D: cancel at a 5m close beyond the edge
        for j in range(su["arm_bar"] + 1, b.n):
            if b.tc[j] > end:
                break
            if (d == -1 and b.c[j] > su["close_cancel"]) or (d == 1 and b.c[j] < su["close_cancel"]):
                end = int(b.tc[j])
                outcome_end = "cancelled"
                break
    k_a = np.searchsorted(m.t, su["arm_time"], "left")
    k_b = np.searchsorted(m.t, end, "left")                   # 1m bars with open < end
    if k_b <= k_a:
        return None, end, outcome_end
    h, l = m.h[k_a:k_b], m.l[k_a:k_b]
    fill = (h >= entry + TICK) if d == -1 else (l <= entry - TICK)
    canc = (h >= su["cancel_hi"]) | (l <= su["cancel_lo"])
    kf = int(np.argmax(fill)) if fill.any() else None
    kc = int(np.argmax(canc)) if canc.any() else None
    if kf is not None and (kc is None or kf <= kc):           # fill first if same 1m bar
        return k_a + kf, None, "filled"
    if kc is not None:
        return None, int(m.t[k_a + kc] + NS_MIN), "cancelled"
    return None, end, outcome_end


def run_test(F, setups, win, exit_rule, rolls, bias_filter=False):
    """Sequential simulation of one test with the occupancy and loss-cap rules (§6)."""
    m = F.m1
    trades, funnel = [], dict(setups=0, ok=0, stale=0, skip_small=0, skip_large=0, skip_leg=0,
                              cancel_prearm=0, bias_reject=0, ignored_busy=0, ignored_losscap=0,
                              armed=0, cancelled=0, expired=0, filled=0, roll_excluded=0)
    busy_until = -1
    losses = {}
    for su in setups:
        funnel["setups"] += 1
        if su["status"] != "ok":
            funnel[su["status"]] += 1
            continue
        funnel["ok"] += 1
        if bias_filter and su["bias"] != su["dir"]:
            funnel["bias_reject"] += 1
            continue
        if su["arm_time"] < busy_until:
            funnel["ignored_busy"] += 1
            continue
        if losses.get(su["day"], 0) >= 2:
            funnel["ignored_losscap"] += 1
            continue
        funnel["armed"] += 1
        k0, end, outcome = simulate_order(F, su)
        if k0 is None:
            funnel[outcome] += 1
            busy_until = end
            continue
        funnel["filled"] += 1
        d, entry, stop = su["dir"], su["entry"], su["stop"]
        target = target_price(entry, d, su["R"], exit_rule)
        kx = exit_cutoff(F, win, k0)
        ke, px, reason = simulate_exit(F, k0, kx, d, entry, stop, target, costs=True)
        _, px0, reason0 = simulate_exit(F, k0, kx, d, entry, stop, target, costs=False)
        pts = d * (px - entry)
        net = pts * PT_VALUE - COMMISSION
        gross0 = d * (px0 - entry) * PT_VALUE
        t_fill, t_exit = int(m.t[k0]), int(m.t[ke] + NS_MIN)
        busy_until = t_exit
        if net < 0:
            losses[su["day"]] = losses.get(su["day"], 0) + 1
        spans_roll = bool(((rolls >= su["arm_time"]) & (rolls <= t_exit)).any())
        if spans_roll:
            funnel["roll_excluded"] += 1
            continue
        tr = {k: v for k, v in su.items() if not isinstance(v, (list, dict))}
        tr.update(k_fill=k0, k_exit=ke, k_cut=kx, t_fill=t_fill, t_exit=t_exit, target=target,
                  exit_px=px, exit_reason=reason, pts=pts, net=net, net_R=net / (su["R"] * PT_VALUE),
                  gross0=gross0, exit_reason0=reason0)
        trades.append(tr)
    return trades, funnel
