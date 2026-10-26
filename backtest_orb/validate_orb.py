"""ORB validation (PREREGISTRATION.md §9). Every check raises AssertionError on failure.

The brute-force simulator and the rule check are written independently of orb_core: they slice the
1m DataFrame by CT wall-clock time with pandas and loop bar by bar.
"""
import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import orb_core as O

C = O.C
TZ = C.TZ
TK = 0.25


class CT:
    """CT wall-clock view of the 1m data, computed once."""

    def __init__(self, df1m):
        self.df = df1m
        ct = df1m.index.tz_convert(TZ)
        self.ts = df1m.index.asi8
        self.minute = (ct.hour * 60 + ct.minute).to_numpy()
        self.date = ct.tz_localize(None).normalize().to_numpy().astype("datetime64[D]")
        self.o, self.h, self.l, self.c = (df1m[k].to_numpy() for k in ("open", "high", "low", "close"))
        self.sess = (ct + pd.Timedelta(hours=7)).tz_localize(None).normalize().to_numpy().astype("datetime64[D]")


def _day_rows(X, date):
    return np.where(X.date == np.datetime64(date, "D"))[0]


def expected_day(X, date, N, stop_rule, exit_rule, sides):
    """Independent re-derivation of one (date, N, variant). Returns a dict or a skip string."""
    rows = _day_rows(X, date)
    mins = X.minute[rows]
    orr = rows[(mins >= 510) & (mins < 510 + N)]
    if len(orr) != N or X.minute[orr[0]] != 510:
        return "missing_or_bars"
    orh, orl = X.h[orr].max(), X.l[orr].min()
    TL, TS = orh + TK, orl - TK
    win = rows[(mins >= 510 + N) & (mins < 840)]                  # [OR end, 14:00)
    # day-level conflict: first bar touching either side
    for i in win:
        up, dn = X.h[i] >= TL + TK, X.l[i] <= TS - TK
        if up or dn:
            if up and dn:
                return "conflict"
            break
    if not sides:
        return "no_filter_direction"
    mid = (orh + orl) / 2
    stops = {1: orl if stop_rule == "S1" else np.floor(mid / TK + 1e-9) * TK,
             -1: orh if stop_rule == "S1" else np.ceil(mid / TK - 1e-9) * TK}
    placed = [d for d in sides if abs((TL + TK if d == 1 else TS - TK) - stops[d]) >= 8.0]
    if not placed:
        return "skip_R<8"
    fill_i = d = None
    for i in win:
        for dd in placed:
            if (dd == 1 and X.h[i] >= TL + TK) or (dd == -1 and X.l[i] <= TS - TK):
                fill_i, d = i, dd
                break
        if fill_i is not None:
            break
    if fill_i is None:
        return "no_trigger"
    T = TL if d == 1 else TS
    entry = (max(T, X.o[fill_i]) + TK) if d == 1 else (min(T, X.o[fill_i]) - TK)
    stop = stops[d]
    R = abs(entry - stop)
    if exit_rule == "E1":
        raw = entry + d * 2 * R
        target = np.floor(raw / TK + 1e-9) * TK if d == 1 else np.ceil(raw / TK - 1e-9) * TK
    else:
        target = None
    sess = X.sess[fill_i]
    j = fill_i
    while True:
        if (d == 1 and X.l[j] <= stop) or (d == -1 and X.h[j] >= stop):
            px = stop if j == fill_i else (min(stop, X.o[j]) if d == 1 else max(stop, X.o[j]))
            px, reason = px - d * TK, "stop"
            break
        if target is not None and j != fill_i and ((d == 1 and X.h[j] >= target + TK) or (d == -1 and X.l[j] <= target - TK)):
            px, reason = target, "target"
            break
        nxt = j + 1
        if nxt >= len(X.ts) or X.sess[nxt] != sess or X.date[nxt] != X.date[fill_i] or X.minute[nxt] >= 895:
            px, reason = X.c[j] - d * TK, "time"
            break
        j = nxt
    return dict(dir=int(d), k_fill=int(fill_i), entry=round(float(entry), 2), stop=round(float(stop), 2),
                R=round(float(R), 2), k_exit=int(j), exit_px=round(float(px), 2), exit_reason=reason,
                net=round(float(d * (px - entry) * 2 - 1), 2), orh=float(orh), orl=float(orl))


def _main_view(t):
    return dict(dir=t["dir"], k_fill=t["k_fill"], entry=round(t["entry"], 2), stop=round(t["stop"], 2), R=round(t["R"], 2),
                k_exit=t["k_exit"], exit_px=round(t["exit_px"], 2), exit_reason=t["exit_reason"], net=round(t["net"], 2),
                orh=t["orh"], orl=t["orl"])


def _sides_of(t):
    if t["filter"] == "F0":
        return (1, -1)
    return (1,) if t["ema_close"] > t["ema"] else (-1,)


def brute_force_check(X, trades, n=500, seed=20261028):
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(trades), size=min(n, len(trades)), replace=False)
    mism = []
    for k in pick:
        t = trades[k]
        exp = expected_day(X, t["date"], t["N"], t["stop_rule"], t["exit_rule"], _sides_of(t))
        if exp != _main_view(t):
            mism.append((t["label"], str(t["date"]), _main_view(t), exp))
    return len(pick), mism


def mutation_check(X, trades, n=500, seed=20261028):
    mutated = []
    for t in trades:
        x = dict(t)
        x["exit_px"] = t["exit_px"] + O.TICK
        x["net"] = t["net"] + t["dir"] * O.TICK * 2
        mutated.append(x)
    return len(brute_force_check(X, mutated, n, seed)[1])


def lookahead_check(M, infos, trades):
    m1, b5 = M.m1, M.b5
    on_grid = lambda p: abs(p * 4 - round(p * 4)) < 1e-9
    for t in trades:
        info = infos[t["N"]][t["date"]]
        assert info["status"] == "ok", "trade on a skipped/conflict day"
        assert t["or_end"] <= m1.t[t["k_fill"]], "fill before the OR was known"
        assert b5.tc[t["ema_bar"]] == t["or_end"] and b5.t[t["ema_bar"]] == t["or_end"] - 5 * O.NS_MIN, "EMA not locked at OR end"
        assert m1.t[t["k_fill"]] < C.ct_time_ns(t["date"], "14:00"), "fill at/after 14:00"
        assert m1.t[t["k_exit"]] < C.ct_time_ns(t["date"], "14:55"), "held past the 14:55 cutoff"
        assert m1.sess[t["k_exit"]] == m1.sess[t["k_fill"]], "held across a session"
        for p in (t["entry"], t["stop"], t["exit_px"]) + ((t["target"],) if np.isfinite(t["target"]) else ()):
            assert on_grid(p), f"price off the tick grid: {p}"
        assert t["R"] >= 8.0 - 1e-9
    return len(trades)


def rule_check(M, X, infos, n=100, seed=20261028):
    """100 random (date, N): OR, EMA lock and conflict recomputed independently; all 8 variants re-derived."""
    rng = np.random.default_rng(seed)
    keys = [(N, d) for N in O.OR_LENGTHS for d in infos[N]]
    pick = [keys[i] for i in rng.choice(len(keys), size=n, replace=False)]
    # every skipped (missing-OR or conflict) day is also re-derived independently
    pick += [(N, d) for N in O.OR_LENGTHS for d, i in infos[N].items() if i["status"] != "ok" and (N, d) not in pick]
    df = X.df
    for N, date in pick:
        info = infos[N][date]
        # independent EMA: own 5m aggregation of all 1m bars up to the OR end, own ewm
        or_end = pd.Timestamp(f"{pd.Timestamp(date).date()} 08:30", tz=TZ) + pd.Timedelta(minutes=N)
        if info["status"] != "missing_or_bars":
            hist = df.loc[:or_end.tz_convert("UTC") - pd.Timedelta(minutes=1)]
            key = hist.index.asi8 // C.NS_5M
            closes = hist["close"].groupby(key).last()
            ema = closes.ewm(span=200, adjust=False).mean()
            e_val = np.nan if len(closes) <= 200 else float(ema.iloc[-1])
            assert closes.index[-1] * C.NS_5M == or_end.value - 5 * C.NS_MIN
            assert (np.isnan(e_val) and np.isnan(info["ema"])) or abs(e_val - info["ema"]) < 1e-6, "EMA mismatch"
            assert abs(closes.iloc[-1] - info["ema_close"]) < 1e-9
        for s in O.STOPS:
            for e in O.EXITS_:
                for f in O.FILTERS:
                    if info["status"] != "ok":
                        exp = expected_day(X, date, N, s, e, (1, -1))
                        assert exp == info["status"], f"status mismatch {date} N{N}: {exp} vs {info['status']}"
                        continue
                    sides = O.allowed_sides(info, f)
                    exp = expected_day(X, date, N, s, e, sides)
                    tr, outcome = O.simulate_day(M, info, s, e, f)
                    if tr is None:
                        assert exp == outcome, f"outcome mismatch {date} N{N} {s}{e}{f}: {exp} vs {outcome}"
                    else:
                        assert isinstance(exp, dict) and exp == _main_view(tr), f"trade mismatch {date} N{N} {s}{e}{f}"
    return len(pick)


def truncation_check(df1m, M, infos, runs, n=20, seed=20261028, history_days=30):
    rng = np.random.default_rng(seed)
    allt = [t for v in runs.values() for t in v]
    pick = [allt[i] for i in rng.choice(len(allt), size=n, replace=False)]
    for t in pick:
        # (a) data cut at the OR end: OR, EMA lock and filter decision
        end = pd.Timestamp(t["or_end"], tz="UTC")
        cut = df1m.loc[end - pd.Timedelta(days=history_days):end - pd.Timedelta(minutes=1)]
        Mc = O.Market(cut)
        assert t["date"] in Mc.days
        k0 = Mc.days[t["date"]]
        or_rows = slice(k0, k0 + t["N"])
        assert Mc.m1.h[or_rows].max() == t["orh"] and Mc.m1.l[or_rows].min() == t["orl"]
        j = int(np.searchsorted(Mc.b5.t, t["or_end"] - 5 * O.NS_MIN))
        assert Mc.b5.tc[j] == t["or_end"] and abs(Mc.ema[j] - t["ema"]) < 1e-6 and Mc.b5.c[j] == t["ema_close"]
        # (b) data cut at the fill bar's close: trigger bar and fill identical
        fill_end = pd.Timestamp(t["t_fill"], tz="UTC")
        cut2 = df1m.loc[end - pd.Timedelta(days=history_days):fill_end]
        M2 = O.Market(cut2)
        info2 = O.day_info(M2, t["date"], t["N"])
        tr2, _ = O.simulate_day(M2, info2, t["stop_rule"], t["exit_rule"], t["filter"])
        assert tr2 is not None and tr2["t_fill"] == t["t_fill"] and tr2["entry"] == t["entry"] \
            and tr2["stop"] == t["stop"] and tr2["dir"] == t["dir"], "truncation mismatch at fill"
    return len(pick)


def faithfulness_charts(M, runs, outdir, n=30, seed=20261028):
    os.makedirs(outdir, exist_ok=True)
    m1 = M.m1
    rng = np.random.default_rng(seed)
    allt = [t for v in runs.values() for t in v]
    seen, saved = set(), 0
    for i in rng.permutation(len(allt)):
        t = allt[i]
        if t["date"] in seen:
            continue
        seen.add(t["date"])
        k_a = int(np.searchsorted(m1.t, C.ct_time_ns(t["date"], "08:15")))
        k_b = min(m1.n, t["k_exit"] + 15)
        fig, ax = plt.subplots(figsize=(14, 6.5))
        xs = np.arange(k_a, k_b)
        for k in xs:
            col = "#1baf7a" if m1.c[k] >= m1.o[k] else "#e34948"
            ax.plot([k, k], [m1.l[k], m1.h[k]], color="#52514e", lw=0.6)
            ax.add_patch(plt.Rectangle((k - 0.35, min(m1.o[k], m1.c[k])), 0.7, max(abs(m1.c[k] - m1.o[k]), 0.05), color=col))
        k0 = M.days[t["date"]]
        ax.add_patch(plt.Rectangle((k0 - 0.5, t["orl"]), t["N"], t["orh"] - t["orl"], color="#2a78d6", alpha=0.18,
                                   label=f"OR {t['N']}m [{t['orl']:.2f}, {t['orh']:.2f}]"))
        ax.axhline(t["TL"], color="#2a78d6", lw=0.8, ls="--", label=f"long trigger {t['TL']:.2f}")
        ax.axhline(t["TS"], color="#6250d6", lw=0.8, ls="--", label=f"short trigger {t['TS']:.2f}")
        ax.axhline(t["entry"], color="#0b0b0b", lw=1, label=f"entry {t['entry']:.2f}")
        ax.axhline(t["stop"], color="#e34948", lw=1, label=f"stop {t['stop']:.2f} (R={t['R']:.2f})")
        if np.isfinite(t["target"]):
            ax.axhline(t["target"], color="#1baf7a", lw=1, label=f"target {t['target']:.2f}")
        ax.axvline(int(np.searchsorted(m1.t, C.ct_time_ns(t["date"], "14:00"))) - 0.5, color="#a3a29c", lw=0.8, ls=":",
                   label="14:00 trigger cutoff")
        ax.scatter([t["k_fill"]], [t["entry"]], s=60, color="#0b0b0b", zorder=5)
        ax.scatter([t["k_exit"]], [t["exit_px"]], marker="X", s=80, color="#eb6834", zorder=5,
                   label=f"exit {t['exit_reason']} {t['exit_px']:.2f}")
        ticks = list(range(k_a, k_b, 30))
        ax.set_xticks(ticks)
        ax.set_xticklabels([pd.Timestamp(int(m1.t[k]), tz="UTC").tz_convert(TZ).strftime("%H:%M") for k in ticks], fontsize=8)
        ax.set_xlim(k_a - 1, k_b)
        ax.grid(alpha=0.25, lw=0.5)
        f_txt = "" if t["filter"] == "F0" else f" | EMA200 {t['ema']:.2f} vs close {t['ema_close']:.2f}"
        ax.set_title(f"{t['label']} | {pd.Timestamp(t['date']).date()} | {'LONG' if t['dir'] == 1 else 'SHORT'} | "
                     f"net {t['net_R']:+.2f}R{f_txt} (1m bars, CT)", fontsize=10)
        ax.legend(fontsize=7, loc="best", ncol=2)
        fig.tight_layout()
        fig.savefig(os.path.join(outdir, f"day_{saved + 1:02d}_{pd.Timestamp(t['date']).date()}_{t['label']}.png"), dpi=85)
        plt.close(fig)
        saved += 1
        if saved >= n:
            break
    return saved
