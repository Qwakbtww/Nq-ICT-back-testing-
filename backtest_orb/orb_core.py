"""ORB core: opening range, EMA(200) filter, day-level conflict flag, stop entries and exits.

Implements backtest_orb/PREREGISTRATION.md (section numbers in comments). Reuses the data layer and
the validated 1m exit simulator from backtest_ict/ict_core.py, and tick helpers / the vectorised
exit engine from backtest_ict_v2/core_v2.py.
Conventions: int64 ns UTC timestamps, bars labeled by open time; direction +1 long / -1 short.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "backtest_ict"))
sys.path.insert(0, os.path.join(ROOT, "backtest_ict_v2"))
import ict_core as C   # noqa: E402
import core_v2 as V2   # noqa: E402

TICK, PT_VALUE, COMMISSION = C.TICK, C.PT_VALUE, C.COMMISSION
NS_MIN = C.NS_MIN
OR_LENGTHS = (5, 15, 30)
STOPS, EXITS_, FILTERS = ("S1", "S2"), ("E1", "E2"), ("F0", "F1")
MIN_R = 8.0
EMA_SPAN, EMA_WARMUP = 200, 200
WIN = "NYAM"                       # ict_core.exit_cutoff: RTH flat at the last 1m bar before 14:55 CT


class Market:
    """1m/5m bars, ATR (ict_core.Features) and the 5m EMA(200) on real bars only (§5)."""

    def __init__(self, df1m):
        self.F = F = C.Features(df1m)
        self.m1, self.b5 = F.m1, F.b5
        ema = pd.Series(F.b5.c).ewm(span=EMA_SPAN, adjust=False).mean().to_numpy().copy()
        ema[:EMA_WARMUP] = np.nan
        self.ema = ema
        # candidate days: dates with a 1m bar opening exactly at 08:30 CT (§2)
        k830 = np.where(self.m1.tod == C.hm("08:30"))[0]
        self.days = {self.m1.date[k]: int(k) for k in k830}


def day_info(M, date, N):
    """OR, trigger levels, EMA lock and conflict flag for one (date, N). Status != 'ok' -> skipped."""
    m1, b5 = M.m1, M.b5
    k0 = M.days[date]
    t830 = int(m1.t[k0])
    or_end = t830 + N * NS_MIN
    k_end_or = int(np.searchsorted(m1.t, or_end, "left"))
    info = dict(date=date, N=N, k_or0=k0, or_end=or_end, status="ok")
    if k_end_or - k0 != N:                                    # all N 1m bars must exist (§2)
        info["status"] = "missing_or_bars"
        return info
    orh, orl = float(m1.h[k0:k_end_or].max()), float(m1.l[k0:k_end_or].min())
    TL, TS = round(orh + TICK, 2), round(orl - TICK, 2)
    t1400 = C.ct_time_ns(date, "14:00")
    ks = k_end_or
    ke = int(np.searchsorted(m1.t, t1400, "left"))            # bars with open < 14:00
    ke = min(ke, int(np.searchsorted(m1.sess, m1.sess[k0], "right")))   # stay inside the session
    # EMA lock at the close of the last 5m bar inside the OR (§5)
    j = int(np.searchsorted(b5.t, or_end - 5 * NS_MIN, "left"))
    assert j < b5.n and b5.t[j] == or_end - 5 * NS_MIN and b5.tc[j] == or_end
    ema, ema_close = float(M.ema[j]), float(b5.c[j])
    atr = float(M.F.atr[j])
    info.update(orh=orh, orl=orl, TL=TL, TS=TS, k_start=ks, k_stop=ke, ema_bar=j, ema=ema,
                ema_close=ema_close, atr=atr)
    # day-level both-sides conflict on the first bar triggering either side (§3)
    hit_l = m1.h[ks:ke] >= TL + TICK
    hit_s = m1.l[ks:ke] <= TS - TICK
    any_hit = hit_l | hit_s
    if any_hit.any():
        f = int(np.argmax(any_hit))
        if hit_l[f] and hit_s[f]:
            info["status"] = "conflict"
    return info


def allowed_sides(info, flt):
    if flt == "F0":
        return (1, -1)
    if np.isnan(info["ema"]) or info["ema_close"] == info["ema"]:
        return ()
    return (1,) if info["ema_close"] > info["ema"] else (-1,)


def stop_price(info, d, stop_rule):
    if stop_rule == "S1":
        return info["orl"] if d == 1 else info["orh"]
    mid = (info["orh"] + info["orl"]) / 2
    return V2.floor_tick(mid) if d == 1 else V2.ceil_tick(mid)          # rounded outward (§4)


def simulate_day(M, info, stop_rule, exit_rule, flt):
    """One (date, N, variant). Returns (trade dict or None, outcome string)."""
    m1 = M.m1
    sides = allowed_sides(info, flt)
    if not sides:
        return None, "no_filter_direction"
    placed = []
    for d in sides:
        stop = stop_price(info, d, stop_rule)
        planned = info["TL"] + TICK if d == 1 else info["TS"] - TICK
        if abs(planned - stop) < MIN_R:
            continue
        placed.append((d, stop))
    if not placed:
        return None, "skip_R<8"
    ks, ke = info["k_start"], info["k_stop"]
    first = {}
    for d, stop in placed:
        hit = (m1.h[ks:ke] >= info["TL"] + TICK) if d == 1 else (m1.l[ks:ke] <= info["TS"] - TICK)
        if hit.any():
            first[d] = ks + int(np.argmax(hit))
    if not first:
        return None, "no_trigger"
    d = min(first, key=first.get)
    assert len(first) < 2 or first[1] != first[-1], "same-bar trigger on a non-conflict day"
    k0 = first[d]
    stop = dict(placed)[d]
    T = info["TL"] if d == 1 else info["TS"]
    base = max(T, m1.o[k0]) if d == 1 else min(T, m1.o[k0])
    entry = round(base + d * TICK, 2)
    R = round(abs(entry - stop), 2)
    target = V2.target_price(entry, d, R, 2.0) if exit_rule == "E1" else (np.inf if d == 1 else -np.inf)
    kx = C.exit_cutoff(M.F, WIN, k0)
    ke_, px, reason = C.simulate_exit(M.F, k0, kx, d, entry, stop, target, costs=True)
    _, px0, _ = C.simulate_exit(M.F, k0, kx, d, entry, stop, target, costs=False)
    net = d * (px - entry) * PT_VALUE - COMMISSION
    gross0 = d * (px0 - base) * PT_VALUE
    tr = dict(date=info["date"], N=info["N"], stop_rule=stop_rule, exit_rule=exit_rule, filter=flt, dir=d,
              orh=info["orh"], orl=info["orl"], TL=info["TL"], TS=info["TS"], or_end=info["or_end"],
              ema=info["ema"], ema_close=info["ema_close"], ema_bar=info["ema_bar"], atr=info["atr"],
              k_fill=int(k0), t_fill=int(m1.t[k0]), entry=entry, entry0=float(base), stop=float(stop), R=R,
              target=float(target), k_cut=int(kx), k_exit=int(ke_), t_exit=int(m1.t[ke_] + NS_MIN),
              exit_px=float(px), exit_reason=reason, net=float(net), net_R=float(net / (R * PT_VALUE)),
              gross0=float(gross0), gross0_R=float(gross0 / (R * PT_VALUE)))
    return tr, "filled"


def tests():
    out, tid = [], 0
    for N in OR_LENGTHS:
        for s in STOPS:
            for e in EXITS_:
                for f in FILTERS:
                    tid += 1
                    out.append(dict(test_id=tid, N=N, stop=s, exit=e, filter=f, label=f"N{N}-{s}-{e}-{f}"))
    assert len(out) == 24
    return out


def run_all(M, rolls):
    """All 24 tests. Returns (infos per N, runs per test, funnels per test)."""
    infos = {N: {d: day_info(M, d, N) for d in sorted(M.days)} for N in OR_LENGTHS}
    runs, funnels = {}, {}
    for t in tests():
        fu = dict(candidate_days=len(M.days), missing_or_bars=0, conflict=0, eligible=0,
                  no_filter_direction=0, **{"skip_R<8": 0}, no_trigger=0, filled=0, roll_excluded=0)
        tr_list = []
        for d, info in infos[t["N"]].items():
            if info["status"] != "ok":
                fu[info["status"]] += 1
                continue
            fu["eligible"] += 1
            tr, outcome = simulate_day(M, info, t["stop"], t["exit"], t["filter"])
            fu[outcome] += 1
            if tr is None:
                continue
            if ((rolls >= tr["or_end"]) & (rolls <= tr["t_exit"])).any():
                fu["roll_excluded"] += 1
                continue
            tr.update(test_id=t["test_id"], label=t["label"])
            tr_list.append(tr)
        runs[t["test_id"]], funnels[t["test_id"]] = tr_list, fu
    return infos, runs, funnels


def skip_R_by_year(infos):
    """Days with no order placed because planned R < 8, by N, stop rule and year (F0)."""
    rows = []
    for N, dd in infos.items():
        for date, info in dd.items():
            if info["status"] != "ok":
                continue
            for s in STOPS:
                Rl = abs(info["TL"] + TICK - stop_price(info, 1, s))
                Rs = abs(info["TS"] - TICK - stop_price(info, -1, s))
                rows.append(dict(N=N, stop=s, year=pd.Timestamp(date).year, skipped=int(Rl < MIN_R and Rs < MIN_R)))
    d = pd.DataFrame(rows)
    return d.groupby(["N", "stop", "year"])["skipped"].sum().unstack("year", fill_value=0)


# ----------------------------------------------------------------------------- controls (§7)

def mirror(M, trades):
    res = []
    for t in trades:
        d = -t["dir"]
        stop = t["entry"] - d * t["R"]
        target = V2.target_price(t["entry"], d, t["R"], 2.0) if t["exit_rule"] == "E1" else (np.inf if d == 1 else -np.inf)
        _, px, _ = C.simulate_exit(M.F, t["k_fill"], t["k_cut"], d, t["entry"], stop, target, costs=True)
        res.append((d * (px - t["entry"]) * PT_VALUE - COMMISSION) / (t["R"] * PT_VALUE))
    return np.array(res)


def drift_null(M, infos, trades, n_sims, rng):
    """Drift-matched random-timing null: mean net R per simulation."""
    if not trades:
        return np.array([])
    n = len(trades)
    years = np.array([pd.Timestamp(t["date"]).year for t in trades])
    p_long = {y: np.mean([t["dir"] == 1 for t, yy in zip(trades, years) if yy == y]) for y in np.unique(years)}
    pl = np.array([p_long[y] for y in years])
    lo = np.array([infos[t["N"]][t["date"]]["k_start"] for t in trades])
    hi = np.array([infos[t["N"]][t["date"]]["k_stop"] for t in trades])
    Rs = np.array([t["R"] for t in trades])
    k_mult = 2.0 if trades[0]["exit_rule"] == "E1" else 1e9          # E2: unreachable target
    k0 = lo[None, :] + np.floor(rng.random((n_sims, n)) * (hi - lo)[None, :]).astype(np.int64)
    dirs = np.where(rng.random((n_sims, n)) < pl[None, :], 1, -1)
    Rmat = np.broadcast_to(Rs, (n_sims, n))
    fk, fd, fR = k0.ravel(), dirs.ravel(), Rmat.ravel()
    out = np.empty(len(fk))
    order = np.argsort(fk, kind="stable")
    uniq, starts = np.unique(fk[order], return_index=True)
    ends = np.r_[starts[1:], len(order)]
    for u, a, z in zip(uniq, starts, ends):
        idx = order[a:z]
        out[idx] = V2._outcomes_at(M.F, WIN, int(u), M.m1.o[u], fd[idx], fR[idx], k_mult, True)
    return out.reshape(n_sims, n).mean(axis=1)


def drift_baseline(M, trades):
    """Always-long / always-short entries at the 08:35 1m open + 1 tick, the day's R, same exits."""
    res = {1: [], -1: []}
    for t in trades:
        k = int(np.searchsorted(M.m1.t, C.ct_time_ns(t["date"], "08:35"), "left"))
        if k >= M.m1.n or M.m1.t[k] != C.ct_time_ns(t["date"], "08:35"):
            continue
        kx = C.exit_cutoff(M.F, WIN, k)
        for d in (1, -1):
            entry = round(M.m1.o[k] + d * TICK, 2)
            stop = entry - d * t["R"]
            target = V2.target_price(entry, d, t["R"], 2.0) if t["exit_rule"] == "E1" else (np.inf if d == 1 else -np.inf)
            _, px, _ = C.simulate_exit(M.F, k, kx, d, entry, stop, target, costs=True)
            res[d].append((d * (px - entry) * PT_VALUE - COMMISSION) / (t["R"] * PT_VALUE))
    return (np.mean(res[1]) if res[1] else np.nan), (np.mean(res[-1]) if res[-1] else np.nan), len(res[1])
