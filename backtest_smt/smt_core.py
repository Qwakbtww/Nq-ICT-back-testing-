"""SMT + OB study core: day filters, overnight levels, sweep -> up-run -> CISD -> SMT signals, A0/A/B execution.

Implements SPEC_v1.md + SPEC_v1_CLARIFICATIONS.md (clarification numbers "#n" in comments).
Conventions: int64 ns UTC timestamps, bars labeled by open time and known at close; direction -1 short / +1 long.
All definitions are written for shorts in the spec; longs mirror them (overnight low).
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "backtest_ict"))
import ict_core as C  # noqa: E402  (Bars, resample, ct_time_ns, hm)

TICK, PT_VALUE, COMMISSION = 0.25, 2.0, 1.00
NS_MIN, NS_5M = C.NS_MIN, 5 * C.NS_MIN
STOP_BUFFER, TARGET_R, CISD_WINDOW, RUN_CAP, B_VALID = 2.0, 2.0, 12, 6, 12
R_MIN, R_MAX = 8.0, 40.0
SPLITS = {"train": ("2019-05-01", "2023-12-31"), "validation": ("2024-01-01", "2025-12-31"),
          "holdout": ("2026-01-01", "2026-10-23")}


def split_of(date):
    d = pd.Timestamp(date)
    for name, (a, b) in SPLITS.items():
        if pd.Timestamp(a) <= d <= pd.Timestamp(b):
            return name
    return None


class Instrument:
    """1m and 5m bars of one instrument (raw front month), with CT fields and session dates."""

    def __init__(self, df1m):
        df1m = df1m.copy()
        df1m.index = pd.DatetimeIndex(df1m.index).as_unit("ns")
        assert str(df1m.index.dtype) == "datetime64[ns, UTC]"
        self.m1 = C.Bars(df1m, NS_MIN)
        self.b5 = C.Bars(C.resample(df1m, "5min"), NS_5M)
        self.m1_start = np.searchsorted(self.m1.t, self.b5.t, "left")


def load_market():
    mnq = Instrument(pd.read_parquet(os.path.join(HERE, "data", "mnq_1m_raw.parquet")))
    mes = Instrument(pd.read_parquet(os.path.join(HERE, "data", "mes_1m_raw.parquet")))
    rolls = pd.to_datetime(pd.read_csv(os.path.join(HERE, "data", "rolls_smt.csv"))["roll_session_date"]).to_numpy().astype("datetime64[D]")
    cal = pd.read_csv(os.path.join(HERE, "calendar_skip_days.csv"))
    return mnq, mes, rolls, cal


# ----------------------------------------------------------------------------- days (#3, #6, #8)

def session_bounds(date):
    """[17:00 CT on the previous calendar day ... ) for trading date `date` (Monday -> Sunday 17:00)."""
    d = pd.Timestamp(date)
    return C.ct_time_ns(d - pd.Timedelta(days=1), "17:00")


def gap_ok(inst, date):
    """#8: no two consecutive 1m bars > 5 min apart between 17:00 (prior evening) and 11:30 CT; edges included."""
    t0 = session_bounds(date)
    t1 = C.ct_time_ns(date, "11:30")
    a = np.searchsorted(inst.m1.t, t0, "left")
    b = np.searchsorted(inst.m1.t, t1, "left")
    if b - a < 2:
        return False
    t = inst.m1.t[a:b]
    if t[0] - t0 > 5 * NS_MIN or t1 - NS_MIN - t[-1] > 4 * NS_MIN:       # first by 17:05, last at/after 11:25
        return False
    return bool((np.diff(t) <= 5 * NS_MIN).all())


def build_days(mnq, mes, rolls, cal):
    """Per trading date: status ('ok' or the skip reason) in a fixed order of checks."""
    dates = np.unique(mnq.m1.sess)                                          # session dates = trading dates
    skip_cal = set(pd.to_datetime(cal["date"]).to_numpy().astype("datetime64[D]"))
    pos = {d: i for i, d in enumerate(dates)}
    roll_excl = set()
    for r in rolls:                                                         # #6: roll day +-2 trading days
        if r in pos:
            i = pos[r]
            roll_excl.update(dates[max(0, i - 2): i + 3])
    out = {}
    for d in dates:
        if pd.Timestamp(d).weekday() >= 5:
            continue                                                        # no weekend trading dates
        if d in skip_cal:
            out[d] = "calendar"
        elif d in roll_excl:
            out[d] = "roll_window"
        elif not (gap_ok(mnq, d) and gap_ok(mes, d)):
            out[d] = "data_gap"
        else:
            out[d] = "ok"
    return out


def overnight(inst, date):
    """Overnight high/low from 1m bars in [17:00 prior evening, 08:29] CT (#15)."""
    a = np.searchsorted(inst.m1.t, session_bounds(date), "left")
    b = np.searchsorted(inst.m1.t, C.ct_time_ns(date, "08:30"), "left")
    return float(inst.m1.h[a:b].max()), float(inst.m1.l[a:b].min())


# ----------------------------------------------------------------------------- signals

def side_signal(mnq, mes, date, d, onh, onl, mes_onh, mes_onl, params):
    """First sweep for one side (d=-1 short at the ON high, +1 long at the ON low) -> signal dict or reason."""
    b = mnq.b5
    cisd_win, run_cap = params["cisd_window"], params["run_cap"]
    w0, w1 = C.ct_time_ns(date, "08:30"), C.ct_time_ns(date, "11:00")
    i0 = int(np.searchsorted(b.t, w0, "left"))
    s = None
    i = i0
    while i < b.n and b.tc[i] <= w1:                                        # #9: sweep bar inside the window
        if d == -1 and b.o[i] <= onh and b.h[i] >= onh + TICK:              # #11: opens at/below the level
            s = i
            break
        if d == 1 and b.o[i] >= onl and b.l[i] <= onl - TICK:
            s = i
            break
        i += 1
    if s is None:
        return None, "no_sweep"
    # up-run (#13): consecutive "with-trend" bars ending at the sweep bar (bullish for shorts, bearish for longs)
    trend = (lambda j: b.c[j] > b.o[j]) if d == -1 else (lambda j: b.c[j] < b.o[j])
    end = s if trend(s) else s - 1
    j = end
    run = []
    while j >= 0 and len(run) < run_cap and trend(j):
        run.append(j)
        j -= 1
    if not run:
        return None, "empty_run"
    first, last = run[-1], run[0]
    D = float(b.o[first])
    # CISD (#12): first bar after the sweep within `cisd_win` bars closing beyond D; must close by 11:00
    k = None
    for q in range(s + 1, min(s + cisd_win + 1, b.n)):
        if (d == -1 and b.c[q] < D) or (d == 1 and b.c[q] > D):
            k = q
            break
    if k is None:
        return None, "no_cisd"
    if b.tc[k] > w1:
        return None, "cisd_after_11"
    ext = float(b.h[s:k + 1].max()) if d == -1 else float(b.l[s:k + 1].min())
    # SMT (#15): MES did not trade >= 1 tick beyond its own ON level from 08:30 through the CISD close
    a = np.searchsorted(mes.m1.t, w0, "left")
    z = np.searchsorted(mes.m1.t, b.tc[k], "left")
    smt = (not (mes.m1.h[a:z] >= mes_onh + TICK).any()) if d == -1 else (not (mes.m1.l[a:z] <= mes_onl - TICK).any())
    return dict(date=date, dir=d, level=onh if d == -1 else onl, s=s, run_first=first, ob=last, D=D, k=k,
                t_cisd=int(b.tc[k]), ext=ext, smt=bool(smt),
                ob_lo=float(min(b.o[last], b.c[last])), ob_hi=float(max(b.o[last], b.c[last]))), "signal"


def day_signals(mnq, mes, date, params):
    onh, onl = overnight(mnq, date)
    mes_onh, mes_onl = overnight(mes, date)
    sigs, reasons = [], {}
    for d in (-1, 1):
        sg, why = side_signal(mnq, mes, date, d, onh, onl, mes_onh, mes_onl, params)
        reasons[d] = why
        if sg is not None:
            sg.update(onh=onh, onl=onl, mes_onh=mes_onh, mes_onl=mes_onl)
            sigs.append(sg)
    return sigs, reasons


# ----------------------------------------------------------------------------- execution (#16-#19)

def ceil_tick(x):
    return round(float(np.ceil(x / TICK - 1e-9)) * TICK, 2)


def floor_tick(x):
    return round(float(np.floor(x / TICK + 1e-9)) * TICK, 2)


def round_limit(x, d):
    """Nearest tick; exact ties to the less favorable side (sell -> down, buy -> up) (#17)."""
    q = x / TICK
    f = np.floor(q + 1e-9)
    if abs(q - f - 0.5) < 1e-9:
        q = f if d == -1 else f + 1
    else:
        q = np.round(q)
    return round(float(q) * TICK, 2)


def simulate_position(mnq, date, d, k0, entry, stop, target):
    """1m simulation from fill bar k0 until stop / target / forced exit at the 11:29 bar close (#10, #18, #19)."""
    m = mnq.m1
    kx = int(np.searchsorted(m.t, C.ct_time_ns(date, "11:30"), "left")) - 1     # last 1m bar with open < 11:30
    for k in range(k0, kx + 1):
        hit_stop = (m.h[k] >= stop) if d == -1 else (m.l[k] <= stop)
        if hit_stop:
            gapped = k > k0 and ((m.o[k] > stop) if d == -1 else (m.o[k] < stop))
            px = m.o[k] if gapped else stop - d * TICK
            return k, float(px), "stop"
        if k > k0 and ((m.l[k] <= target - TICK) if d == -1 else (m.h[k] >= target + TICK)):
            return k, float(target), "target"
    return kx, float(m.c[kx] - d * TICK), "forced_exit"


def execute(mnq, sg, test, params):
    """One signal for test A0 / A (market) or B (limit). Returns (trade dict or None, outcome)."""
    m, b = mnq.m1, mnq.b5
    d, date = sg["dir"], sg["date"]
    stop = round(sg["ext"] - d * params["stop_buffer"], 2)
    t_end_exit = C.ct_time_ns(date, "11:29")                       # fills must occur before the 11:29 bar (#10)
    if test in ("A0", "A"):
        k0 = int(np.searchsorted(m.t, sg["t_cisd"], "left"))       # open of the bar after the CISD
        if k0 >= m.n or m.t[k0] >= t_end_exit:
            return None, "no_entry_bar"
        entry = round(m.o[k0] + d * TICK, 2)                       # 1 tick worse
        R = round((stop - entry) * (-d), 2)
        if not (R_MIN <= R <= R_MAX):
            return None, "skip_R"
    else:
        entry = round_limit((sg["ob_lo"] + sg["ob_hi"]) / 2, d)
        R = round((stop - entry) * (-d), 2)
        if not (R_MIN <= R <= R_MAX):
            return None, "skip_R"
        kb = min(sg["k"] + B_VALID, b.n - 1)
        t_valid = min(int(b.tc[kb]), t_end_exit)
        a = int(np.searchsorted(m.t, sg["t_cisd"], "left"))
        z = int(np.searchsorted(m.t, t_valid, "left"))
        fill = (m.h[a:z] >= entry + TICK) if d == -1 else (m.l[a:z] <= entry - TICK)
        if not fill.any():
            return None, "limit_unfilled"
        k0 = a + int(np.argmax(fill))
    raw_t = entry + d * params["target_r"] * R
    target = ceil_tick(raw_t) if d == -1 else floor_tick(raw_t)
    ke, px, reason = simulate_position(mnq, date, d, k0, entry, stop, target)
    pts = d * (px - entry)
    net = pts * PT_VALUE - COMMISSION
    return dict(date=pd.Timestamp(date).date(), split=split_of(date), test=test, dir=d, smt=sg["smt"],
                t_cisd=sg["t_cisd"], k_fill=k0, t_fill=int(m.t[k0]), entry=entry, stop=stop, R=R, target=target,
                k_exit=ke, t_exit=int(m.t[ke] + NS_MIN), exit_px=px, exit_reason=reason, pts=pts, net=net,
                net_R=net / (R * PT_VALUE), level=sg["level"], ext=sg["ext"], D=sg["D"],
                ob_lo=sg["ob_lo"], ob_hi=sg["ob_hi"], onh=sg["onh"], onl=sg["onl"]), "filled"


DEFAULT_PARAMS = dict(stop_buffer=STOP_BUFFER, target_r=TARGET_R, cisd_window=CISD_WINDOW, run_cap=RUN_CAP)


def run_tests(mnq, mes, days, params=DEFAULT_PARAMS, splits=("train", "validation")):
    """A0, A, B over the requested splits. One trade per day per test: the first valid signal (#16)."""
    trades, funnel = {t: [] for t in ("A0", "A", "B")}, {t: {} for t in ("A0", "A", "B")}
    same_bar = 0
    for date, status in days.items():
        sp = split_of(date)
        if sp not in splits:
            continue
        for t in funnel:
            funnel[t].setdefault(sp, {})
            funnel[t][sp][status] = funnel[t][sp].get(status, 0) + 1
        if status != "ok":
            continue
        sigs, _ = day_signals(mnq, mes, date, params)
        sigs.sort(key=lambda x: x["t_cisd"])
        if len(sigs) == 2 and sigs[0]["t_cisd"] == sigs[1]["t_cisd"]:
            same_bar += 1                                                 # counted; spec has no tie-break
            continue
        for test in ("A0", "A", "B"):
            cand = [x for x in sigs if test == "A0" or x["smt"]]
            if not cand:
                key = "no_signal"
            else:
                tr, key = execute(mnq, cand[0], test, params)
                if tr is not None:
                    trades[test].append(tr)
            funnel[test][sp][key] = funnel[test][sp].get(key, 0) + 1
    return trades, funnel, same_bar
