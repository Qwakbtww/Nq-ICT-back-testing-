"""ICT v2 validation (PREREGISTRATION.md §10). Every check raises AssertionError on failure.

1. brute_force_check + mutation_check: independent minute-by-minute simulator vs the main engine.
2. lookahead_check: inputs known before use, for every setup and trade.
3. rule_check: 100 random setups per model re-verified from independently aggregated 5m bars.
4. truncation_check: setups re-derived from data cut at the arm time.
5. faithfulness_charts: 15 random trades per model as annotated PNGs.
"""
import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import core_v2 as V2

C = V2.C
TZ, TICK = C.TZ, C.TICK


def _ct(ts_ns):
    return pd.Timestamp(int(ts_ns), tz="UTC").tz_convert(TZ)


# ----------------------------------------------------------------------------- 1. brute force

def brute_force_trade(df1m, su, k_mult):
    """Independent re-simulation (entry + exit) of one setup; written without the engine's helpers."""
    ts = df1m.index.asi8
    O, H, L, Cl = (df1m[c].values for c in ("open", "high", "low", "close"))
    d, stop = su["dir"], su["stop"]
    i = int(np.searchsorted(ts, su["arm_time"]))
    if su["market"]:
        fill_i = i
        entry = O[i] + 0.25 * d
    else:
        entry = su["entry"]
        end = min(su["expiry_time"], su["win_end"])
        fill_i, cur_bucket, last_close = None, None, None
        while i < len(ts) and ts[i] < end:
            bucket = ts[i] - ts[i] % C.NS_5M
            if su["close_cancel"] is not None and cur_bucket is not None and bucket != cur_bucket:
                if (d == -1 and last_close > su["close_cancel"]) or (d == 1 and last_close < su["close_cancel"]):
                    return None
            if (H[i] >= entry + 0.25) if d == -1 else (L[i] <= entry - 0.25):
                fill_i = i
                break
            if H[i] >= su["cancel_hi"] or L[i] <= su["cancel_lo"]:
                return None
            cur_bucket, last_close = bucket, Cl[i]
            i += 1
        if fill_i is None:
            return None
    R = abs(entry - stop)
    raw = entry + d * k_mult * R                       # target rounded to the tick toward the entry
    q = raw / 0.25
    target = (np.ceil(q - 1e-9) if d == -1 else np.floor(q + 1e-9)) * 0.25
    t_fill = _ct(ts[fill_i])
    sess = (t_fill + pd.Timedelta(hours=7)).date()
    if su["win"] == "ASIA":
        cut = min(t_fill + pd.Timedelta(hours=3), pd.Timestamp(f"{t_fill.date()} 23:00", tz=TZ))
    else:
        cut = pd.Timestamp(f"{t_fill.date()} 14:55", tz=TZ)
    j = fill_i
    while True:
        if (H[j] >= stop) if d == -1 else (L[j] <= stop):
            px = stop if j == fill_i else (max(stop, O[j]) if d == -1 else min(stop, O[j]))
            px, reason = px - 0.25 * d, "stop"
            break
        if j != fill_i and ((L[j] <= target - 0.25) if d == -1 else (H[j] >= target + 0.25)):
            px, reason = target, "target"
            break
        nxt = j + 1
        if nxt >= len(ts) or _ct(ts[nxt]) >= cut or (_ct(ts[nxt]) + pd.Timedelta(hours=7)).date() != sess:
            px, reason = Cl[j] - 0.25 * d, "time"
            break
        j = nxt
    net = d * (px - entry) * 2.0 - 1.0
    return dict(k_fill=int(fill_i), entry=round(float(entry), 2), k_exit=int(j), exit_px=round(float(px), 2),
                exit_reason=reason, net=round(float(net), 2))


def _main_view(t):
    return dict(k_fill=t["k_fill"], entry=round(t["entry"], 2), k_exit=t["k_exit"], exit_px=round(t["exit_px"], 2),
                exit_reason=t["exit_reason"], net=round(t["net"], 2))


def brute_force_check(df1m, trades, n=500, seed=20261027):
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(trades), size=min(n, len(trades)), replace=False)
    mism = [(trades[k]["label"], _main_view(trades[k]), brute_force_trade(df1m, trades[k], V2.EXITS[trades[k]["exit_rule"]]))
            for k in pick]
    mism = [x for x in mism if x[1] != x[2]]
    return len(pick), mism


def mutation_check(df1m, trades, n=500, seed=20261027):
    """Shift every main-engine exit price by 1 tick (and net accordingly); the check must flag it."""
    mutated = []
    for t in trades:
        x = dict(t)
        x["exit_px"] = t["exit_px"] + TICK
        x["net"] = t["net"] + t["dir"] * TICK * 2.0
        mutated.append(x)
    _, mism = brute_force_check(df1m, mutated, n=n, seed=seed)
    return len(mism)


# ----------------------------------------------------------------------------- 2. look-ahead

def lookahead_check(F, setups, trades):
    b = F.b5
    for su in setups:
        s, m = su["s"], su["m"]
        assert b.t[s] >= su["win_start"], "signal bar before window start"
        assert su["arm_time"] <= su["win_end"], "armed after window end"
        assert su["arm_time"] == b.tc[su["arm_bar"]]
        if su["model"] != "D":
            assert F.level_known(su["level"], s) <= b.t[s], "level used before known"
            assert su["ref"] < s and b.tc[su["ref"] + 3] <= b.t[m], "swing used before confirmed"
            assert su["ref"] >= s - V2.SWING_MAX_AGE, "swing older than 40 bars"
            side = -su["dir"]
            for k in range(su["r"] + 1, m):                    # no invalidation bar before the MSS
                assert not ((side == 1 and b.h[k] >= su["ext"] + TICK) or (side == -1 and b.l[k] <= su["ext"] - TICK))
            if su["model"] in ("A1", "A2"):
                assert su["arm_bar"] == m + 1, "FVG used before bar3 close"
            else:
                assert su["arm_bar"] == m
        else:
            assert b.tc[su["ref"] + 3] <= b.t[m] and su["ob"] < m and su["arm_bar"] == m
        assert su["atr_s"] == F.atr[su["arm_bar"]], "ATR_s not from the arm bar"
        if su["bias_k"] >= 0:
            assert F.bh.tc[su["bias_k"]] <= su["arm_time"], "1H bias from an incomplete bar"
    for t in trades:
        assert t["t_fill"] >= t["arm_time"], "fill before arm"
        assert t["t_fill"] < t["win_end"], "fill after window end"
        assert t["t_exit"] > t["t_fill"]
    return len(setups)


# ----------------------------------------------------------------------------- 3. rule check

def _bar5(df1m, t_open):
    x = df1m.loc[pd.Timestamp(int(t_open), tz="UTC"):pd.Timestamp(int(t_open) + C.NS_5M - 1, tz="UTC")]
    return x["open"].iloc[0], x["high"].max(), x["low"].min(), x["close"].iloc[-1]


def _indep_level(df1m, ct_min, ct_date, name, t_s):
    ct_s = _ct(t_s)
    if name in ("PDH", "PDL"):
        rth = (ct_min >= 510) & (ct_min < 900)
        d = ct_s.date() if ct_s.hour * 60 + ct_s.minute >= 900 else ct_s.date() - pd.Timedelta(days=1)
        d = np.datetime64(d)
        while not (rth & (ct_date == d)).any():
            d -= np.timedelta64(1, "D")
        sel = rth & (ct_date == d)
        return df1m["high"].values[sel].max() if name == "PDH" else df1m["low"].values[sel].min()
    start = pd.Timestamp(f"{(ct_s - pd.Timedelta(days=1)).date()} 17:00", tz=TZ)
    t830 = pd.Timestamp(f"{ct_s.date()} 08:30", tz=TZ)
    x = df1m.loc[start:t830 - pd.Timedelta(minutes=1)]
    return x["high"].max() if name == "ONH" else x["low"].min()


def rule_check(F, df1m, setups, n=100, seed=20261027):
    b = F.b5
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(setups), size=min(n, len(setups)), replace=False)
    ct = df1m.index.tz_convert(TZ)
    ct_min = (ct.hour * 60 + ct.minute).to_numpy()
    ct_date = ct.tz_localize(None).normalize().to_numpy().astype("datetime64[D]")
    cache = {}

    def O(i):
        if i not in cache:
            cache[i] = _bar5(df1m, b.t[i])
        return cache[i]

    def atr_at(i):
        """Wilder ATR at the close of bar i, hand-rolled over 300 bars from a seed 300 bars back."""
        lo_i = max(1, i - 300)
        a = F.atr[lo_i - 1]
        for j in range(lo_i, i + 1):
            _, h_, l_, _ = O(j)
            pc = O(j - 1)[3]
            a = a + (max(h_ - l_, abs(h_ - pc), abs(l_ - pc)) - a) / 14
        return a

    def is_disp(i, dd):
        o_, h_, l_, c_ = O(i)
        _, ph, pl, _ = O(i - 1)
        a = atr_at(i - 1)
        if dd == -1:
            return c_ < pl and c_ < o_ and (o_ - c_) >= a - 1e-6
        return c_ > ph and c_ > o_ and (c_ - o_) >= a - 1e-6

    def is_swing(p, hi):
        v = [O(j)[1 if hi else 2] for j in range(p - 3, p + 4)]
        return all(v[3] > x for j, x in enumerate(v) if j != 3) if hi else all(v[3] < x for j, x in enumerate(v) if j != 3)

    def outward(x, d):
        q = x / 0.25
        return (np.ceil(q - 1e-9) if d == -1 else np.floor(q + 1e-9)) * 0.25

    for k in pick:
        su = setups[k]
        s, m, d = su["s"], su["m"], su["dir"]
        assert su["win_start"] <= b.t[s] and su["arm_time"] <= su["win_end"]
        a_s = atr_at(su["arm_bar"])
        assert abs(a_s - su["atr_s"]) < 1e-6, "ATR_s mismatch"
        if su["model"] != "D":
            side = -d
            Lv = _indep_level(df1m, ct_min, ct_date, su["level"], b.t[s])
            assert abs(Lv - su["L"]) < 1e-9, "level mismatch"
            cprev = O(s - 1)[3]
            closes = [O(j)[3] for j in range(s, s + 3)]
            if side == 1:
                assert cprev < Lv and O(s)[1] >= Lv + TICK
                r = s + next(i for i, c_ in enumerate(closes) if c_ < Lv)
                ext = max(O(j)[1] for j in range(s, r + 1))
            else:
                assert cprev > Lv and O(s)[2] <= Lv - TICK
                r = s + next(i for i, c_ in enumerate(closes) if c_ > Lv)
                ext = min(O(j)[2] for j in range(s, r + 1))
            assert r == su["r"] and abs(ext - su["ext"]) < 1e-9
            assert s + 1 <= m <= s + 12 and m >= r and is_disp(m, d)
            p = su["ref"]
            assert is_swing(p, hi=(side == -1)) and p < s and p + 3 <= m - 1 and p >= s - 40
            for q in range(p + 1, min(s - 1, m - 4) + 1):
                assert not is_swing(q, hi=(side == -1)), "not the most recent swing"
            assert (O(m)[3] < O(p)[2]) if side == 1 else (O(m)[3] > O(p)[1])
            for q in range(r + 1, m):
                assert not ((O(q)[1] >= ext + TICK) if side == 1 else (O(q)[2] <= ext - TICK)), "should be invalidated"
            stop = outward(ext + 0.1 * a_s * side, d)
            assert abs(su["stop"] - stop) < 1e-9, "stop mismatch"
            if su["model"] in ("A1", "A2"):
                b1, b3 = O(m - 1), O(m + 1)
                gap = (b1[2] - b3[1]) if side == 1 else (b3[2] - b1[1])
                assert gap >= 2.0 and abs(gap - su["gap"]) < 1e-9
                near = b3[1] if side == 1 else b3[2]
                if su["model"] == "A2":
                    assert su["entry"] == near
                elif su["status"] not in ("fill_outside_window",):
                    x = df1m.loc[pd.Timestamp(su["arm_time"], tz="UTC"):].iloc[0]
                    assert abs(su["entry"] - (x["open"] + 0.25 * d)) < 1e-9
            else:
                far = min(O(j)[2] for j in range(s, m + 1)) if side == 1 else max(O(j)[1] for j in range(s, m + 1))
                assert abs(far - su["far"]) < 1e-9
                assert abs(su["entry"] - C.round_tick(far + 0.705 * (ext - far), "sell" if d == -1 else "buy")) < 1e-9
                if su["status"] != "skip_leg":
                    assert abs(ext - far) >= 1.5 * a_s
                else:
                    assert abs(ext - far) < 1.5 * a_s
        else:
            assert is_disp(m, d)
            p = su["ref"]
            assert is_swing(p, hi=(d == 1)) and p + 3 <= m - 1
            for q in range(p + 1, m - 3):
                assert not is_swing(q, hi=(d == 1))
            lvl = O(p)[2] if d == -1 else O(p)[1]
            assert (O(m)[3] < lvl) if d == -1 else (O(m)[3] > lvl)
            for q in range(p + 4, m):
                assert not ((O(q)[3] < lvl) if d == -1 else (O(q)[3] > lvl)), "not the first break"
            opp = [j for j in range(m - 5, m) if ((O(j)[3] > O(j)[0]) if d == -1 else (O(j)[3] < O(j)[0]))]
            assert opp and opp[-1] == su["ob"]
            _, h_, l_, _ = O(su["ob"])
            assert abs(su["entry"] - C.round_tick((h_ + l_) / 2, "sell" if d == -1 else "buy")) < 1e-9
            assert abs(su["stop"] - outward((h_ if d == -1 else l_) + 0.1 * a_s * (-d), d)) < 1e-9
        if su["status"] in ("ok", "skip_small", "skip_large"):
            R = abs(su["entry"] - su["stop"])
            if su["status"] == "ok":
                assert 0.4 * a_s <= R <= 3.0 * a_s
            elif su["status"] == "skip_small":
                assert R < 0.4 * a_s
            else:
                assert R > 3.0 * a_s
    return len(pick)


# ----------------------------------------------------------------------------- 4. truncation

def truncation_check(df1m, F, setups, n=20, seed=20261027, history_days=120):
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(setups), size=min(n, len(setups)), replace=False)
    for k in pick:
        su = setups[k]
        t_end = pd.Timestamp(int(su["arm_time"]), tz="UTC")
        cut = df1m.loc[t_end - pd.Timedelta(days=history_days):t_end - pd.Timedelta(minutes=1)]
        if su["model"] == "A1":                       # A1 also needs the entry bar (first 1m bar after arm)
            cut = df1m.loc[t_end - pd.Timedelta(days=history_days):t_end + pd.Timedelta(minutes=0)]
            nxt = df1m.loc[t_end:].iloc[:1]
            cut = pd.concat([cut[cut.index < t_end], nxt])
        G = C.Features(cut)
        got = V2.build_setups(G, su["model"], su["win"])
        ok = [g for g in got if g["arm_time"] == su["arm_time"] and g["dir"] == su["dir"]
              and G.b5.t[g["s"]] == F.b5.t[su["s"]] and G.b5.t[g["m"]] == F.b5.t[su["m"]]
              and g["status"] == su["status"] and g["bias"] == su["bias"]
              and abs(g["stop"] - su["stop"]) < 1e-9 and abs(g["atr_s"] - su["atr_s"]) < 1e-6
              and (g["entry"] == su["entry"] or (np.isnan(g["entry"]) and np.isnan(su["entry"])))]
        assert ok, f"truncation mismatch {su['model']} {su['win']} {t_end}"
    return len(pick)


# ----------------------------------------------------------------------------- 5. charts

def faithfulness_charts(F, trades_by_model, outdir, n=15, seed=20261027):
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
                ax.add_patch(plt.Rectangle((i - 0.35, min(b.o[i], b.c[i])), 0.7, max(abs(b.c[i] - b.o[i]), 0.05), color=col))
            x1 = hi_i - 0.5
            ref_px = b.l[t["ref"]] if t["dir"] == -1 else b.h[t["ref"]]
            if model != "D":
                ax.axhline(t["L"], color="#6250d6", lw=1, ls="--", label=f"{t['level']} {t['L']:.2f}")
                ax.axvspan(t["s"] - 0.5, t["s"] + 0.5, color="#eda100", alpha=0.25, label="sweep bar")
                ax.axhline(t["ext"], color="#eda100", lw=0.8, label=f"sweep extreme {t['ext']:.2f}")
                ax.plot([t["ref"], t["m"]], [ref_px, ref_px], color="#008300", lw=1.2, ls=":",
                        label=f"MSS swing ({t['s'] - t['ref']} bars before sweep)")
                ax.axvspan(t["m"] - 0.5, t["m"] + 0.5, color="#2a78d6", alpha=0.18, label="MSS bar")
            else:
                ax.plot([t["ref"], t["m"]], [ref_px, ref_px], color="#008300", lw=1.2, ls=":", label="BOS swing")
                ax.axvspan(t["m"] - 0.5, t["m"] + 0.5, color="#2a78d6", alpha=0.18, label="BOS bar")
                ax.add_patch(plt.Rectangle((t["ob"] - 0.5, t["ob_lo"]), x1 - t["ob"], t["ob_hi"] - t["ob_lo"],
                                           color="#e87ba4", alpha=0.25, label="order block"))
            if model in ("A1", "A2"):
                ax.add_patch(plt.Rectangle((t["m"] - 1.5, t["fvg_lo"]), x1 - t["m"] + 1.5, t["fvg_hi"] - t["fvg_lo"],
                                           color="#2a78d6", alpha=0.15, label="FVG"))
            if model == "B":
                lo_, hi_ = sorted([t["far"], t["ext"]])
                ax.plot([t["s"], t["m"]], [t["ext"], t["far"]], color="#6250d6", lw=1, label="leg")
                ax.axhline(t["far"] + 0.705 * (t["ext"] - t["far"]), color="#6250d6", lw=0.6, ls="-.", label="70.5%")
            i_fill = int(np.searchsorted(b.t, t["t_fill"], "right") - 1)
            ax.axhline(t["entry"], color="#0b0b0b", lw=1, label=f"entry {t['entry']:.2f}")
            ax.axhline(t["stop"], color="#e34948", lw=1, label=f"stop {t['stop']:.2f} (R={t['R']:.2f}, {t['R_atr']:.2f} ATR)")
            ax.axhline(t["target"], color="#1baf7a", lw=1, label=f"target {t['target']:.2f}")
            ax.scatter([i_fill], [t["entry"]], marker="o", s=60, color="#0b0b0b", zorder=5)
            ax.scatter([i_exit5], [t["exit_px"]], marker="X", s=80, color="#eb6834", zorder=5,
                       label=f"exit {t['exit_reason']} {t['exit_px']:.2f}")
            ax.set_xlim(lo_i - 0.5, x1)
            ticks = list(range(lo_i, hi_i, 6))
            ax.set_xticks(ticks)
            ax.set_xticklabels([_ct(b.t[i]).strftime("%m-%d %H:%M") for i in ticks], rotation=30, fontsize=8)
            ax.grid(alpha=0.25, lw=0.5)
            ax.set_title(f"Model {model} | {t['win']} {t['exit_rule']} | {'LONG' if t['dir'] == 1 else 'SHORT'} | "
                         f"net {t['net_R']:+.2f}R | {_ct(t['t_fill']).strftime('%Y-%m-%d %H:%M CT')} (5m, CT)", fontsize=10)
            ax.legend(fontsize=7, loc="best", ncol=2)
            fig.tight_layout()
            fig.savefig(os.path.join(outdir, f"model{model}_{q + 1:02d}.png"), dpi=90)
            plt.close(fig)
            saved += 1
    return saved
