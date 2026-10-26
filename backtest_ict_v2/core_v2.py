"""ICT v2 core: signals, setups (A1, A2, B, D) and the sequential test simulator.

Implements backtest_ict_v2/PREREGISTRATION.md (section numbers in comments). Data layer, causal
features (levels, swings, displacement, ATR, 1H bias) and the 1m exit simulator are imported
from backtest_ict/ict_core.py, which passed the study-1 validation.
Conventions: int64 ns UTC timestamps, bars labeled by open time; direction +1 long / -1 short.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backtest_ict"))
import ict_core as C  # noqa: E402

TICK, PT_VALUE, COMMISSION = C.TICK, C.PT_VALUE, C.COMMISSION
TESTED_WINDOWS = ("NYAM", "ASIA")
DESCRIPTIVE_WINDOWS = ("SBPM",)            # descriptive-only simulation (§5)
MODELS = ("A1", "A2", "B", "D")
EXITS = {"X1": 1.5, "X2": 3.0}
BUFFER_ATR, R_MIN_ATR, R_MAX_ATR, LEG_MIN_ATR = 0.1, 0.4, 3.0, 1.5
SWING_MAX_AGE, MSS_WINDOW, A2_VALID, B_VALID, D_VALID = 40, 12, 12, 24, 24


def ceil_tick(x):
    return round(float(np.ceil(x / TICK - 1e-9)) * TICK, 2)


def floor_tick(x):
    return round(float(np.floor(x / TICK + 1e-9)) * TICK, 2)


def stop_beyond(point, atr, d):
    """Structure point plus a 0.1 x ATR buffer, rounded outward (away from the entry) (§4)."""
    return ceil_tick(point + BUFFER_ATR * atr) if d == -1 else floor_tick(point - BUFFER_ATR * atr)


def target_price(entry, d, R, k):
    """entry + d*k*R rounded to the tick toward the entry (§6)."""
    x = entry + d * k * R
    return ceil_tick(x) if d == -1 else floor_tick(x)


# ----------------------------------------------------------------------------- signals (§3)

def find_signals(F, win):
    """sweep -> MSS signals with the v2 swing-age and sweep-invalidation rules."""
    b = F.b5
    _, _, levels = C.WINDOWS[win]
    sigs, counts = {}, dict(sweeps=0, invalidated=0, swing_too_old=0, no_mss=0)
    for day, (i0, i1, ws, we) in C.window_days(F, win).items():
        for s in range(max(i0, 1), i1):
            for side in (+1, -1):                          # +1 = high level swept -> short
                names = [x for x in (C.HIGH_LEVELS if side == 1 else C.LOW_LEVELS) if x in levels]
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
                    if r is not None:
                        found = (name, L, r)
                        break
                if found is None:
                    continue
                counts["sweeps"] += 1
                name, L, r = found
                ext = b.h[s:r + 1].max() if side == 1 else b.l[s:r + 1].min()
                m, ref, why = None, -1, "no_mss"
                for k in range(max(s + 1, r), min(s + MSS_WINDOW + 1, b.n)):
                    p = (F.last_sl if side == 1 else F.last_sh)[min(s - 1, k - 4)]
                    is_mss = False
                    if p >= 0 and p >= s - SWING_MAX_AGE:
                        if side == 1 and F.disp_bear[k] and b.c[k] < b.l[p]:
                            is_mss = True
                        if side == -1 and F.disp_bull[k] and b.c[k] > b.h[p]:
                            is_mss = True
                    elif p >= 0 and ((side == 1 and F.disp_bear[k] and b.c[k] < b.l[p]) or
                                     (side == -1 and F.disp_bull[k] and b.c[k] > b.h[p])):
                        why = "swing_too_old"                # would qualify but swing older than 40 bars
                    if is_mss:
                        m, ref = k, p
                        break
                    if k > r and ((side == 1 and b.h[k] >= ext + TICK) or (side == -1 and b.l[k] <= ext - TICK)):
                        why = "invalidated"
                        break
                if m is None:
                    counts[why] += 1
                    continue
                key = (side, m)
                if key in sigs:
                    continue
                far = b.l[s:m + 1].min() if side == 1 else b.h[s:m + 1].max()
                sig = dict(win=win, day=day, dir=-side, level=name, L=L, s=s, r=r, ext=ext, m=m,
                           ref=int(ref), far=far, win_start=ws, win_end=we, has_fvg=False,
                           fvg_lo=np.nan, fvg_hi=np.nan, near=np.nan, gap=np.nan)
                if m + 1 < b.n:
                    if side == 1:
                        gap = b.l[m - 1] - b.h[m + 1]
                        lo, hi, near = b.h[m + 1], b.l[m - 1], b.h[m + 1]
                    else:
                        gap = b.l[m + 1] - b.h[m - 1]
                        lo, hi, near = b.h[m - 1], b.l[m + 1], b.l[m + 1]
                    if gap >= 2.0:
                        sig.update(has_fvg=True, fvg_lo=lo, fvg_hi=hi, near=near, gap=gap)
                sigs[key] = sig
    return sorted(sigs.values(), key=lambda x: (x["m"], x["s"], x["dir"])), counts


# ----------------------------------------------------------------------------- setups (§4)

def _base(F, su, arm_bar, expiry_bar):
    b = F.b5
    su["arm_bar"] = arm_bar
    su["arm_time"] = int(b.tc[arm_bar])
    su["expiry_time"] = int(min(b.tc[min(expiry_bar, b.n - 1)], su["win_end"])) if expiry_bar is not None else su["win_end"]
    su["atr_s"] = float(F.atr[arm_bar])
    su["bias"], su["bias_k"] = F.bias_at(su["arm_time"])
    su.setdefault("status", "ok")
    return su


def _risk(su):
    """Stale and risk filter (§4). Leaves an earlier non-ok status untouched."""
    if su["status"] != "ok":
        return su
    su["R"] = round(abs(su["entry"] - su["stop"]), 2)
    if su["R"] < R_MIN_ATR * su["atr_s"]:
        su["status"] = "skip_small"
    elif su["R"] > R_MAX_ATR * su["atr_s"]:
        su["status"] = "skip_large"
    return su


def setups_A1(F, sigs):
    b, m1 = F.b5, F.m1
    out = []
    for g in sigs:
        if not g["has_fvg"] or b.tc[g["m"] + 1] > g["win_end"]:
            continue
        su = _base(F, dict(g, model="A1", market=True, close_cancel=None,
                           cancel_hi=np.inf, cancel_lo=-np.inf), g["m"] + 1, None)
        d = su["dir"]
        su["stop"] = stop_beyond(g["ext"], su["atr_s"], d)
        k0 = int(np.searchsorted(m1.t, su["arm_time"], "left"))
        su["k_entry"] = k0
        if k0 >= m1.n or m1.t[k0] >= su["win_end"]:
            su.update(status="fill_outside_window", entry=np.nan, R=np.nan)
        else:
            su["entry0"] = float(m1.o[k0])                        # zero-cost entry
            su["entry"] = round(m1.o[k0] + d * TICK, 2)           # 1 tick adverse
            if (d == 1 and su["entry"] <= su["stop"]) or (d == -1 and su["entry"] >= su["stop"]):
                su.update(status="gap_through_stop", R=np.nan)
        out.append(_risk(su))
    return out


def setups_A2(F, sigs):
    b = F.b5
    out = []
    for g in sigs:
        if not g["has_fvg"] or b.tc[g["m"] + 1] > g["win_end"]:
            continue
        su = _base(F, dict(g, model="A2", market=False, close_cancel=None), g["m"] + 1, g["m"] + A2_VALID)
        d = su["dir"]
        su["entry"] = g["near"]
        su["stop"] = stop_beyond(g["ext"], su["atr_s"], d)
        su["cancel_hi"] = g["ext"] + TICK if d == -1 else np.inf
        su["cancel_lo"] = -np.inf if d == -1 else g["ext"] - TICK
        c = b.c[su["arm_bar"]]
        if (d == -1 and c >= su["entry"]) or (d == 1 and c <= su["entry"]):
            su["status"] = "stale"
        out.append(_risk(su))
    return out


def setups_B(F, sigs):
    b = F.b5
    out = []
    for g in sigs:
        if b.tc[g["m"]] > g["win_end"]:
            continue
        su = _base(F, dict(g, model="B", market=False, close_cancel=None), g["m"], g["m"] + B_VALID)
        d = su["dir"]
        H, far = g["ext"], g["far"]
        su["leg"] = abs(H - far)
        if d == -1:
            su["entry"] = C.round_tick(far + 0.705 * (H - far), "sell")
            su["cancel_hi"], su["cancel_lo"] = H + TICK, -np.inf
        else:
            su["entry"] = C.round_tick(far - 0.705 * (far - H), "buy")
            su["cancel_hi"], su["cancel_lo"] = np.inf, H - TICK
        su["stop"] = stop_beyond(H, su["atr_s"], d)
        c = b.c[su["arm_bar"]]
        if su["leg"] < LEG_MIN_ATR * su["atr_s"]:
            su["status"] = "skip_leg"
        elif (d == -1 and c >= su["entry"]) or (d == 1 and c <= su["entry"]):
            su["status"] = "stale"
        out.append(_risk(su))
    return out


def setups_D(F, win):
    b = F.b5
    out = []
    for day, (i0, i1, ws, we) in C.window_days(F, win).items():
        for dbar in range(max(i0, 5), i1):
            if b.tc[dbar] > we:
                continue
            for d in (-1, 1):
                disp = F.disp_bear if d == -1 else F.disp_bull
                if not disp[dbar]:
                    continue
                p = (F.last_sl if d == -1 else F.last_sh)[dbar - 4]
                if p < 0:
                    continue
                lvl = b.l[p] if d == -1 else b.h[p]
                if d == -1 and not (b.c[dbar] < lvl and not (b.c[p + 4:dbar] < lvl).any()):
                    continue
                if d == 1 and not (b.c[dbar] > lvl and not (b.c[p + 4:dbar] > lvl).any()):
                    continue
                cand = [j for j in range(dbar - 5, dbar) if (b.c[j] > b.o[j] if d == -1 else b.c[j] < b.o[j])]
                if not cand:
                    continue
                j = cand[-1]
                zlo, zhi = b.l[j], b.h[j]
                su = dict(win=win, day=day, dir=d, model="D", market=False, level="BOS", L=np.nan, s=dbar,
                          r=dbar, ext=np.nan, m=dbar, ref=int(p), ob=j, ob_lo=zlo, ob_hi=zhi, far=np.nan,
                          has_fvg=False, fvg_lo=np.nan, fvg_hi=np.nan, near=np.nan, gap=np.nan,
                          win_start=ws, win_end=we, cancel_hi=np.inf, cancel_lo=-np.inf)
                _base(F, su, dbar, dbar + D_VALID)
                su["entry"] = C.round_tick((zlo + zhi) / 2, "sell" if d == -1 else "buy")
                edge = zhi if d == -1 else zlo
                su["close_cancel"] = edge
                su["stop"] = stop_beyond(edge, su["atr_s"], d)
                c = b.c[dbar]
                if (d == -1 and c >= su["entry"]) or (d == 1 and c <= su["entry"]):
                    su["status"] = "stale"
                out.append(_risk(su))
    return sorted(out, key=lambda x: (x["arm_time"], x["s"], x["dir"]))


def build_setups(F, model, win, sigs=None):
    if model == "D":
        return setups_D(F, win)
    if sigs is None:
        sigs, _ = find_signals(F, win)
    return {"A1": setups_A1, "A2": setups_A2, "B": setups_B}[model](F, sigs)


# ----------------------------------------------------------------------------- simulation (§6)

STATUSES = ("stale", "skip_small", "skip_large", "skip_leg", "fill_outside_window", "gap_through_stop")


def run_test(F, setups, win, exit_rule, rolls, bias_filter=False):
    m = F.m1
    k_mult = EXITS[exit_rule]
    funnel = dict(setups=0, valid=0, bias_reject=0, ignored_busy=0, ignored_losscap=0, armed=0,
                  cancelled=0, expired=0, filled=0, roll_excluded=0, **{s: 0 for s in STATUSES})
    trades, busy_until, losses = [], -1, {}
    for su in setups:
        funnel["setups"] += 1
        if su["status"] != "ok":
            funnel[su["status"]] += 1
            continue
        funnel["valid"] += 1
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
        if su["market"]:
            k0 = su["k_entry"]
        else:
            k0, end, outcome = C.simulate_order(F, su)
            if k0 is None:
                funnel[outcome] += 1
                busy_until = end
                continue
        funnel["filled"] += 1
        d, entry, stop, R = su["dir"], su["entry"], su["stop"], su["R"]
        target = target_price(entry, d, R, k_mult)
        kx = C.exit_cutoff(F, win, k0)
        ke, px, reason = C.simulate_exit(F, k0, kx, d, entry, stop, target, costs=True)
        _, px0, _ = C.simulate_exit(F, k0, kx, d, entry, stop, target, costs=False)
        entry0 = su.get("entry0", entry) if su["market"] else entry
        net = d * (px - entry) * PT_VALUE - COMMISSION
        gross0 = d * (px0 - entry0) * PT_VALUE
        t_exit = int(m.t[ke] + C.NS_MIN)
        busy_until = t_exit
        if net < 0:
            losses[su["day"]] = losses.get(su["day"], 0) + 1
        if ((rolls >= su["arm_time"]) & (rolls <= t_exit)).any():
            funnel["roll_excluded"] += 1
            continue
        tr = {k: v for k, v in su.items() if not isinstance(v, (list, dict))}
        tr.update(exit_rule=exit_rule, k_fill=int(k0), k_exit=int(ke), k_cut=int(kx), t_fill=int(m.t[k0]),
                  t_exit=t_exit, target=target, exit_px=float(px), exit_reason=reason,
                  net=float(net), net_R=float(net / (R * PT_VALUE)), gross0=float(gross0),
                  gross0_R=float(gross0 / (R * PT_VALUE)), R_atr=float(R / su["atr_s"]))
        trades.append(tr)
    return trades, funnel


# ----------------------------------------------------------------------------- controls (§8)

def null_candidates(F, win):
    """Per 30-min bucket: list over dates of arrays of 5m bar indices inside the window."""
    b = F.b5
    cand = {}
    for day, (i0, i1, _, _) in C.window_days(F, win).items():
        per = {}
        for i in range(i0, i1):
            if i < 1 or np.isnan(F.atr[i - 1]):
                continue
            per.setdefault((b.tod[i] // 30) * 30, []).append(i)
        for bk, lst in per.items():
            cand.setdefault(bk, []).append(np.array(lst))
    return cand


def _outcomes_at(F, win, k0, e_base, dirs, Rs, k_mult, slip_entry):
    """Vectorised exits for many (direction, R) draws entering at 1m bar k0 (open e_base).
    Same rules as ict_core.simulate_exit (stop first, no target in the fill bar, gap rule)."""
    m = F.m1
    kx = C.exit_cutoff(F, win, k0)
    h, l, o = m.h[k0:kx + 1], m.l[k0:kx + 1], m.o[k0:kx + 1]
    up = np.maximum.accumulate(h - e_base)                 # how far above the base open price went
    dn = np.maximum.accumulate(e_base - l)
    dn_t = np.maximum.accumulate(np.r_[-np.inf, (e_base - l)[1:]])   # target not in the fill bar
    up_t = np.maximum.accumulate(np.r_[-np.inf, (h - e_base)[1:]])
    net_R = np.empty(len(dirs))
    L = kx - k0 + 1
    for d in (-1, 1):
        sel = dirs == d
        if not sel.any():
            continue
        R = Rs[sel]
        entry = e_base + (d * TICK if slip_entry else 0.0)
        stop = entry - d * R
        tgt_raw = entry + d * k_mult * R
        target = np.ceil(tgt_raw / TICK - 1e-9) * TICK if d == -1 else np.floor(tgt_raw / TICK + 1e-9) * TICK
        if d == -1:
            ks = np.searchsorted(up, stop - e_base - 1e-9, "left")          # first h >= stop
            kt = np.searchsorted(dn_t, e_base - target + TICK - 1e-9, "left")  # first l <= target - tick
        else:
            ks = np.searchsorted(dn, e_base - stop - 1e-9, "left")
            kt = np.searchsorted(up_t, target + TICK - e_base - 1e-9, "left")
        px = np.where(ks < L, 0.0, np.nan)
        stop_first = (ks < L) & (ks <= kt)
        tgt = (kt < L) & ~stop_first
        o_at = o[np.minimum(ks, L - 1)]
        gap_px = np.maximum(stop, o_at) if d == -1 else np.minimum(stop, o_at)
        stop_px = np.where(ks == 0, stop, gap_px) - d * TICK
        time_px = m.c[kx] - d * TICK
        px = np.where(stop_first, stop_px, np.where(tgt, target, time_px))
        net = d * (px - entry) * PT_VALUE - COMMISSION
        net_R[sel] = net / (R * PT_VALUE)
    return net_R


def random_direction_null(F, win, trades, model, n_sims, rng):
    """§8 null: mean net R per simulation (array of n_sims)."""
    if not trades:
        return np.array([])
    cand = null_candidates(F, win)
    n = len(trades)
    buckets = np.array([(int(F.m1.tod[t["k_fill"]]) // 30) * 30 for t in trades])
    mults = np.array([t["R_atr"] for t in trades])
    slip = model == "A1"
    k_mult = EXITS[trades[0]["exit_rule"]]
    draws_i5 = np.empty((n_sims, n), dtype=np.int64)
    for j in range(n):
        lst = cand[buckets[j]]
        di = rng.integers(len(lst), size=n_sims)
        draws_i5[:, j] = [lst[q][rng.integers(len(lst[q]))] for q in di]
    dirs = np.where(rng.random((n_sims, n)) < 0.5, 1, -1)
    mm = mults[rng.integers(n, size=(n_sims, n))]
    flat_i5, flat_d, flat_m = draws_i5.ravel(), dirs.ravel(), mm.ravel()
    atr = F.atr[flat_i5 - 1]
    Rs = np.maximum(TICK, np.ceil(flat_m * atr / TICK - 1e-9) * TICK)
    out = np.empty(len(flat_i5))
    order = np.argsort(flat_i5, kind="stable")
    uniq, starts = np.unique(flat_i5[order], return_index=True)
    ends = np.r_[starts[1:], len(order)]
    for u, a, z in zip(uniq, starts, ends):
        idx = order[a:z]
        k0 = int(F.m1_start[u])
        out[idx] = _outcomes_at(F, win, k0, F.m1.o[k0], flat_d[idx], Rs[idx], k_mult, slip)
    return out.reshape(n_sims, n).mean(axis=1)


def mirror(F, trades):
    res = []
    for t in trades:
        d = -t["dir"]
        stop = t["entry"] - d * t["R"]
        target = target_price(t["entry"], d, t["R"], EXITS[t["exit_rule"]])
        _, px, _ = C.simulate_exit(F, t["k_fill"], t["k_cut"], d, t["entry"], stop, target, costs=True)
        res.append((d * (px - t["entry"]) * PT_VALUE - COMMISSION) / (t["R"] * PT_VALUE))
    return np.array(res)
