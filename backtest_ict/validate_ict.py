"""Validation before results (PREREGISTRATION.md §10).

1. brute_force_check: an independent minute-by-minute simulator (plain Python loops over the
   1m DataFrame, CT times recomputed with pandas) vs the main engine on 500 random trades.
2. lookahead_check: every setup's inputs must be known at the time they are used.
3. rule_check: 100 random setups per model re-verified rule by rule from 1m data with
   independent hand-coded logic (own 5m aggregation, own levels, own swing/ATR checks).
4. truncation_check: setups re-derived from data truncated at the arm time must be identical.
5. faithfulness_charts: 15 random trades per model as annotated PNGs.
Each check raises AssertionError on failure; run_ict.py halts if any check fails.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import ict_core as C

TZ = C.TZ
TICK = C.TICK


# ----------------------------------------------------------------------------- 1. brute force

def _ct(ts_ns):
    return pd.Timestamp(int(ts_ns), tz="UTC").tz_convert(TZ)


def brute_force_trade(df1m, su, exit_rule):
    """Independent re-simulation of order + position for one setup. Returns a dict or None."""
    d, entry, stop, R = su["dir"], su["entry"], su["stop"], su["R"]
    dist = 2 * R if exit_rule == "X1" else 40.0
    target = entry + d * dist
    end = min(su["expiry_time"], su["win_end"])
    ts = df1m.index.asi8
    i = int(np.searchsorted(ts, su["arm_time"]))
    rows_o, rows_h = df1m["open"].values, df1m["high"].values
    rows_l, rows_c = df1m["low"].values, df1m["close"].values
    # ---- order phase
    fill_i = None
    cur_bucket, last_close = None, None
    while i < len(ts) and ts[i] < end:
        bucket = ts[i] - ts[i] % C.NS_5M
        if su["close_cancel"] is not None:
            # a completed 5m bar (after the arm bar) closing beyond the far edge cancels the order
            if cur_bucket is not None and bucket != cur_bucket and cur_bucket >= su["arm_time"]:
                if (d == -1 and last_close > su["close_cancel"]) or (d == 1 and last_close < su["close_cancel"]):
                    return None
            if cur_bucket is not None and bucket != cur_bucket and bucket - cur_bucket > C.NS_5M:
                pass  # missing 5m bars have no close; nothing to check
        hi, lo = rows_h[i], rows_l[i]
        filled = hi >= entry + TICK if d == -1 else lo <= entry - TICK
        cancel = hi >= su["cancel_hi"] or lo <= su["cancel_lo"]
        if filled:
            fill_i = i
            break
        if cancel:
            return None
        cur_bucket, last_close = bucket, rows_c[i]
        i += 1
    if fill_i is None:
        return None
    # ---- position phase: compute the time stop from wall-clock CT time
    t_fill = _ct(ts[fill_i])
    sess_fill = (t_fill + pd.Timedelta(hours=7)).date()
    if su["win"] == "ASIA":
        cut = min(t_fill + pd.Timedelta(hours=3),
                  pd.Timestamp(f"{t_fill.date()} 23:00", tz=TZ))
    else:
        cut = pd.Timestamp(f"{t_fill.date()} 14:55", tz=TZ)
    j = fill_i
    while True:
        tj = _ct(ts[j])
        hi, lo, op = rows_h[j], rows_l[j], rows_o[j]
        stop_hit = hi >= stop if d == -1 else lo <= stop
        tgt_hit = (lo <= target - TICK if d == -1 else hi >= target + TICK) and j != fill_i
        if stop_hit:
            px = stop if j == fill_i else (max(stop, op) if d == -1 else min(stop, op))
            px = px + TICK if d == -1 else px - TICK
            reason = "stop"
            break
        if tgt_hit:
            px, reason = target, "target"
            break
        nxt = j + 1
        last = (nxt >= len(ts) or _ct(ts[nxt]) >= cut or
                (_ct(ts[nxt]) + pd.Timedelta(hours=7)).date() != sess_fill)
        if last:
            px = rows_c[j] + TICK if d == -1 else rows_c[j] - TICK
            reason = "time"
            break
        j = nxt
    net = d * (px - entry) * 2.0 - 1.0
    return dict(k_fill=fill_i, k_exit=j, exit_px=round(px, 2), exit_reason=reason, net=round(net, 2))


def brute_force_check(df1m, trades, n=500, seed=20261026):
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(trades), size=min(n, len(trades)), replace=False)
    mism = []
    for k in pick:
        t = trades[k]
        bf = brute_force_trade(df1m, t, t["exit_rule"])
        main = dict(k_fill=t["k_fill"], k_exit=t["k_exit"], exit_px=round(t["exit_px"], 2),
                    exit_reason=t["exit_reason"], net=round(t["net"], 2))
        if bf != main:
            mism.append((t["test_id"], main, bf))
    return len(pick), mism


# ----------------------------------------------------------------------------- 2. look-ahead

def lookahead_check(F, setups, trades):
    b = F.b5
    n = 0
    for su in setups:
        s, m = su["s"], su["m"]
        assert b.t[s] >= su["win_start"], "signal bar before window start"
        assert su["arm_time"] <= su["win_end"], "armed after window end"
        if su["model"] in ("A", "B"):
            assert F.level_known(su["level"], s) <= b.t[s], "level used before known"
            assert su["arm_time"] == b.tc[m + 1], "FVG used before bar3 close"
            assert su["ref"] < s and b.tc[su["ref"] + 3] <= b.t[m], "swing used before confirmed"
        else:
            assert b.tc[su["ref"] + 3] <= b.t[m], "swing used before confirmed"
            assert su["arm_time"] == b.tc[m]
            assert su["ob"] < m
        if su["bias_k"] >= 0:
            assert F.bh.tc[su["bias_k"]] <= su["arm_time"], "1H bias used before bar close"
        n += 1
    for t in trades:
        assert t["t_fill"] >= t["arm_time"], "fill before arm"
        assert t["t_fill"] < t["win_end"], "fill after window end"
        assert t["t_exit"] > t["t_fill"]
    return n


# ----------------------------------------------------------------------------- 3. rule check

def _bar5(df1m, t_open):
    """Independent 5m aggregation of one bar from 1m data."""
    x = df1m.loc[pd.Timestamp(int(t_open), tz="UTC"):pd.Timestamp(int(t_open) + C.NS_5M - 1, tz="UTC")]
    return x["open"].iloc[0], x["high"].max(), x["low"].min(), x["close"].iloc[-1]


def _indep_level(df1m, ct_min, ct_date, name, t_s):
    """PDH/PDL/ONH/ONL as of the sweep bar's open, recomputed from 1m bars with CT clock rules.
    ct_min / ct_date: CT minute-of-day and CT date of every 1m bar (computed once by the caller)."""
    ct_s = _ct(t_s)
    if name in ("PDH", "PDL"):
        rth = (ct_min >= 510) & (ct_min < 900)                  # 08:30 <= t < 15:00
        # latest calendar date whose 15:00 CT close is <= the sweep bar open and that has RTH bars
        d = ct_s.date() if ct_s.hour * 60 + ct_s.minute >= 900 else ct_s.date() - pd.Timedelta(days=1)
        d = np.datetime64(d)
        while not (rth & (ct_date == d)).any():
            d -= np.timedelta64(1, "D")
        sel = rth & (ct_date == d)
        return df1m["high"].values[sel].max() if name == "PDH" else df1m["low"].values[sel].min()
    # overnight: from 17:00 CT on the previous calendar day to 08:29 CT of the sweep day
    start = pd.Timestamp(f"{(ct_s - pd.Timedelta(days=1)).date()} 17:00", tz=TZ)
    t830 = pd.Timestamp(f"{ct_s.date()} 08:30", tz=TZ)
    x = df1m.loc[start:t830 - pd.Timedelta(minutes=1)]
    return x["high"].max() if name == "ONH" else x["low"].min()


def rule_check(F, df1m, setups, n=100, seed=20261026):
    """Hand-coded verification of every rule on n random setups (status 'ok' or skipped)."""
    b = F.b5
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(setups), size=min(n, len(setups)), replace=False)
    sub = df1m  # full data; slices are by time
    ct = df1m.index.tz_convert(TZ)
    ct_min = (ct.hour * 60 + ct.minute).to_numpy()
    ct_date = ct.tz_localize(None).normalize().to_numpy().astype("datetime64[D]")
    cache = {}

    def O(i):
        if i not in cache:
            cache[i] = _bar5(sub, b.t[i])
        return cache[i]

    for k in pick:
        su = setups[k]
        s, m, d = su["s"], su["m"], su["dir"]
        # ATR recomputed by hand (Wilder) from our own 5m bars over the last 300 bars
        def atr_prev(i):
            lo_i = max(1, i - 300)
            trs = []
            for j in range(lo_i, i):
                _, h_, l_, _ = O(j)
                pc = O(j - 1)[3]
                trs.append(max(h_ - l_, abs(h_ - pc), abs(l_ - pc)))
            a = F.atr[lo_i - 1]                     # seed from engine 300 bars back (decays to ~1e-10)
            for tr in trs:
                a = a + (tr - a) / 14
            return a
        def is_disp(i, dd):
            o_, h_, l_, c_ = O(i)
            _, ph, pl, _ = O(i - 1)
            a = atr_prev(i)
            if dd == -1:
                return c_ < pl and c_ < o_ and (o_ - c_) >= a - 1e-6
            return c_ > ph and c_ > o_ and (c_ - o_) >= a - 1e-6
        def is_swing(p, hi):
            v = [O(j)[1 if hi else 2] for j in range(p - 3, p + 4)]
            return all(v[3] > x for j, x in enumerate(v) if j != 3) if hi else \
                all(v[3] < x for j, x in enumerate(v) if j != 3)
        assert su["win_start"] <= b.t[s] and su["arm_time"] <= su["win_end"]
        if su["model"] in ("A", "B"):
            side = -d                                   # +1 = high level swept
            L = _indep_level(sub, ct_min, ct_date, su["level"], b.t[s])
            assert abs(L - su["L"]) < 1e-9, f"level mismatch {su['level']} {L} {su['L']}"
            _, hs, ls, _ = O(s)
            cprev = O(s - 1)[3]
            if side == 1:
                assert cprev < L and hs >= L + TICK
                closes = [O(j)[3] for j in range(s, s + 3)]
                r = s + next(i for i, c_ in enumerate(closes) if c_ < L)
                ext = max(O(j)[1] for j in range(s, r + 1))
            else:
                assert cprev > L and ls <= L - TICK
                closes = [O(j)[3] for j in range(s, s + 3)]
                r = s + next(i for i, c_ in enumerate(closes) if c_ > L)
                ext = min(O(j)[2] for j in range(s, r + 1))
            assert r == su["r"] and abs(ext - su["ext"]) < 1e-9
            # MSS: m in window, displacement, beyond the reference swing which is the latest valid one
            assert s + 1 <= m <= s + 12 and m >= r
            assert is_disp(m, d)
            p = su["ref"]
            assert is_swing(p, hi=(side == -1)) and p < s and p + 3 <= m - 1
            for q in range(p + 1, min(s - 1, m - 4) + 1):       # no later valid pivot
                assert not is_swing(q, hi=(side == -1))
            cm = O(m)[3]
            assert (cm < O(p)[2]) if side == 1 else (cm > O(p)[1])
            for q in range(max(s + 1, r), m):                   # no earlier qualifying MSS bar
                pq = (F.last_sl if side == 1 else F.last_sh)[min(s - 1, q - 4)]
                if pq >= 0 and is_disp(q, d):
                    assert not ((O(q)[3] < O(pq)[2]) if side == 1 else (O(q)[3] > O(pq)[1]))
            b1, b3 = O(m - 1), O(m + 1)
            gap = (b1[2] - b3[1]) if side == 1 else (b3[2] - b1[1])
            assert gap >= 2.0 and abs(gap - su["gap"]) < 1e-9
            mid = ((b3[1] + b1[2]) / 2) if side == 1 else ((b1[1] + b3[2]) / 2)
            if su["model"] == "A":
                exp_entry = C.round_tick(mid, "sell" if d == -1 else "buy")
                assert abs(su["entry"] - exp_entry) < 1e-9
                assert abs(su["stop"] - (ext + 3 * side)) < 1e-9
            else:
                far = min(O(j)[2] for j in range(s, m + 1)) if side == 1 else max(O(j)[1] for j in range(s, m + 1))
                assert abs(far - su["far"]) < 1e-9
                lvl = far + 0.705 * (ext - far)
                assert abs(su["entry"] - C.round_tick(lvl, "sell" if d == -1 else "buy")) < 1e-9
                if su["status"] == "ok":
                    assert abs(ext - far) >= 20
        else:
            assert is_disp(m, d)
            p = su["ref"]
            assert is_swing(p, hi=(d == 1)) and p + 3 <= m - 1
            for q in range(p + 1, m - 3):
                assert not is_swing(q, hi=(d == 1))
            lvl = O(p)[2] if d == -1 else O(p)[1]
            cm = O(m)[3]
            assert (cm < lvl) if d == -1 else (cm > lvl)
            for q in range(p + 4, m):
                cq = O(q)[3]
                assert not ((cq < lvl) if d == -1 else (cq > lvl)), "BOS not the first break"
            bars = [(j, O(j)) for j in range(m - 5, m)]
            opp = [j for j, (o_, h_, l_, c_) in bars if ((c_ > o_) if d == -1 else (c_ < o_))]
            assert opp and opp[-1] == su["ob"]
            o_, h_, l_, c_ = O(su["ob"])
            assert abs(su["entry"] - C.round_tick((h_ + l_) / 2, "sell" if d == -1 else "buy")) < 1e-9
            assert abs(su["stop"] - ((h_ + 3) if d == -1 else (l_ - 3))) < 1e-9
        # stop-distance filter
        if su["status"] == "ok":
            assert 8 <= su["R"] <= 40
        elif su["status"] in ("skip_small", "skip_large"):
            assert su["R"] < 8 or su["R"] > 40
    return len(pick)


# ----------------------------------------------------------------------------- 4. truncation

def truncation_check(df1m, F, setups, n=20, seed=20261026, history_days=120):
    """Re-derive setups from data that ends at the arm time; the setup must be reproduced exactly."""
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(setups), size=min(n, len(setups)), replace=False)
    for k in pick:
        su = setups[k]
        t_end = pd.Timestamp(int(su["arm_time"]), tz="UTC")
        t0 = t_end - pd.Timedelta(days=history_days)
        cut = df1m.loc[t0:t_end - pd.Timedelta(minutes=1)]
        G = C.Features(cut)
        got = C.build_setups(G, su["model"], su["win"])
        match = [g for g in got if g["arm_time"] == su["arm_time"] and g["dir"] == su["dir"]
                 and G.b5.t[g["s"]] == F.b5.t[su["s"]] and G.b5.t[g["m"]] == F.b5.t[su["m"]]
                 and abs(g["entry"] - su["entry"]) < 1e-9 and abs(g["stop"] - su["stop"]) < 1e-9
                 and g["status"] == su["status"] and g["bias"] == su["bias"]]
        assert match, f"truncation mismatch for {su['model']} {su['win']} {t_end}"
    return len(pick)


# ----------------------------------------------------------------------------- 5. charts

def faithfulness_charts(F, trades_by_model, outdir, n=15, seed=20261026):
    os.makedirs(outdir, exist_ok=True)
    b, m1 = F.b5, F.m1
    rng = np.random.default_rng(seed)
    saved = 0
    for model, trades in trades_by_model.items():
        if not trades:
            continue
        pick = rng.choice(len(trades), size=min(n, len(trades)), replace=False)
        for q, k in enumerate(pick):
            t = trades[k]
            i_exit5 = int(np.searchsorted(b.t, m1.t[t["k_exit"]], "right") - 1)
            lo_i, hi_i = max(0, t["s"] - 25), min(b.n, i_exit5 + 6)
            fig, ax = plt.subplots(figsize=(13, 6.5))
            for i in range(lo_i, hi_i):
                col = "#1baf7a" if b.c[i] >= b.o[i] else "#e34948"
                ax.plot([i, i], [b.l[i], b.h[i]], color="#52514e", lw=0.8)
                ax.add_patch(plt.Rectangle((i - 0.35, min(b.o[i], b.c[i])), 0.7,
                                           max(abs(b.c[i] - b.o[i]), 0.05), color=col))
            x0, x1 = lo_i - 0.5, hi_i - 0.5
            if model in ("A", "B"):
                ax.axhline(t["L"], color="#6250d6", lw=1, ls="--", label=f"{t['level']} {t['L']:.2f}")
                ax.axvspan(t["s"] - 0.5, t["s"] + 0.5, color="#eda100", alpha=0.25, label="sweep bar")
                ax.axhline(b.l[t["ref"]] if t["dir"] == -1 else b.h[t["ref"]], color="#008300", lw=0.8,
                           ls=":", label="MSS reference swing")
            else:
                ax.axhline(b.l[t["ref"]] if t["dir"] == -1 else b.h[t["ref"]], color="#008300", lw=0.8,
                           ls=":", label="BOS reference swing")
                ax.add_patch(plt.Rectangle((t["ob"] - 0.5, t["ob_lo"]), x1 - t["ob"], t["ob_hi"] - t["ob_lo"],
                                           color="#e87ba4", alpha=0.25, label="order block"))
            ax.axvspan(t["m"] - 0.5, t["m"] + 0.5, color="#2a78d6", alpha=0.18,
                       label="MSS bar" if model != "D" else "BOS displacement bar")
            if model == "A":
                ax.add_patch(plt.Rectangle((t["m"] - 1.5, t["fvg_lo"]), x1 - t["m"] + 1.5,
                                           t["fvg_hi"] - t["fvg_lo"], color="#2a78d6", alpha=0.15, label="FVG"))
            if model == "B":
                ax.add_patch(plt.Rectangle((t["s"] - 0.5, min(t["far"] + 0.62 * (t["ext"] - t["far"]),
                                                              t["far"] + 0.79 * (t["ext"] - t["far"]))),
                                           x1 - t["s"], abs(0.17 * (t["ext"] - t["far"])),
                                           color="#2a78d6", alpha=0.15, label="OTE 62-79%"))
            i_fill = int(np.searchsorted(b.t, t["t_fill"], "right") - 1)
            ax.axhline(t["entry"], color="#0b0b0b", lw=1, label=f"entry {t['entry']:.2f}")
            ax.axhline(t["stop"], color="#e34948", lw=1, label=f"stop {t['stop']:.2f}")
            ax.axhline(t["target"], color="#1baf7a", lw=1, label=f"target {t['target']:.2f}")
            ax.scatter([i_fill], [t["entry"]], marker="o", s=60, color="#0b0b0b", zorder=5)
            ax.scatter([i_exit5], [t["exit_px"]], marker="X", s=80, color="#eb6834", zorder=5,
                       label=f"exit {t['exit_reason']} {t['exit_px']:.2f}")
            ax.set_xlim(x0, x1)
            ticks = list(range(lo_i, hi_i, 6))
            ax.set_xticks(ticks)
            ax.set_xticklabels([_ct(b.t[i]).strftime("%m-%d %H:%M") for i in ticks], rotation=30, fontsize=8)
            ax.grid(alpha=0.25, lw=0.5)
            side = "LONG" if t["dir"] == 1 else "SHORT"
            ax.set_title(f"Model {model} | {t['win']} {t['exit_rule']} | {side} | net ${t['net']:.2f} | "
                         f"{_ct(t['t_fill']).strftime('%Y-%m-%d %H:%M CT')} (5m bars, CT)", fontsize=10)
            ax.legend(fontsize=7, loc="best", ncol=2)
            fig.tight_layout()
            fig.savefig(os.path.join(outdir, f"model{model}_{q + 1:02d}.png"), dpi=90)
            plt.close(fig)
            saved += 1
    return saved
