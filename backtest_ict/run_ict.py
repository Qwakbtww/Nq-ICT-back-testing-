"""Main script: verify the pre-registration hash, validate, run the 40 pre-registered tests,
controls, statistics and Monte Carlo, and write all outputs to ./backtest_ict.

Usage:  python3 run_ict.py            (from the backtest_ict folder)
"""
import hashlib
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import ict_core as C
import validate_ict as V

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = HERE
BASE_SEED = 20261026
N_NULL, N_BOOT, N_PERM, N_MC = 1000, 10000, 10000, 2000
BLUE, ORANGE, GRAY, INK, INK2 = "#2a78d6", "#eb6834", "#a3a29c", "#0b0b0b", "#52514e"


# ----------------------------------------------------------------------------- pre-registration

def verify_prereg():
    want = open(os.path.join(HERE, "PREREGISTRATION.sha256")).read().split()[0]
    got = hashlib.sha256(open(os.path.join(HERE, "PREREGISTRATION.md"), "rb").read()).hexdigest()
    if got != want:
        sys.exit(f"PREREGISTRATION.md hash mismatch ({got} != {want}); refusing to run.")
    print("pre-registration hash OK:", got)
    return got


# ----------------------------------------------------------------------------- test list

def test_list():
    tests = []
    tid = 0
    for bias in (False, True):
        for model, wins in (("A", ("NYAM", "SBAM", "SBPM", "ASIA")), ("B", ("NYAM", "ASIA")), ("D", ("NYAM", "ASIA"))):
            for win in wins:
                for ex in ("X1", "X2"):
                    tid += 1
                    tests.append(dict(test_id=tid, family="bias" if bias else "primary", model=model,
                                      win=win, exit=ex, bias=bias))
    for win in ("NYAM", "SBAM", "SBPM", "ASIA"):
        for ex in ("X1", "X2"):
            tid += 1
            tests.append(dict(test_id=tid, family="confluence", model="A", win=win, exit=ex, bias=False))
    assert len(tests) == 40
    return tests


def label(t):
    tag = {"primary": "", "bias": "+bias", "confluence": " conf"}[t["family"]]
    return f"{t['model']}-{t['win']}-{t['exit']}{tag}"


# ----------------------------------------------------------------------------- statistics

def max_dd(x):
    eq = np.concatenate([[0.0], np.cumsum(x)])
    return float((np.maximum.accumulate(eq) - eq).max())


def longest_loss_streak(x):
    best = cur = 0
    for v in x:
        cur = cur + 1 if v < 0 else 0
        best = max(best, cur)
    return best


def summarize(net, R_net, rng):
    n = len(net)
    if n == 0:
        return dict(n=0)
    wins, losses = net[net > 0], net[net <= 0]
    aw = wins.mean() if len(wins) else 0.0
    al = losses.mean() if len(losses) else 0.0
    be = abs(al) / (aw + abs(al)) if (aw + abs(al)) > 0 else np.nan
    pf = wins.sum() / abs(losses.sum()) if losses.sum() != 0 else np.inf
    if n >= 2 and net.std() > 0:
        p = float(stats.ttest_1samp(net, 0.0, alternative="greater").pvalue)
    else:
        p = 1.0
    boot = rng.choice(net, size=(N_BOOT, n), replace=True).mean(axis=1)
    return dict(n=n, win_rate=len(wins) / n, be_win_rate=be, avg_win=aw, avg_loss=al,
                exp_usd=net.mean(), exp_R=R_net.mean(), pf=pf, max_dd=max_dd(net),
                max_loss_streak=longest_loss_streak(net), p_t=p,
                ci_lo=float(np.percentile(boot, 2.5)), ci_hi=float(np.percentile(boot, 97.5)))


def holm(p):
    p = np.asarray(p)
    order = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    run = 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (m - rank) * p[i]))
        adj[i] = run
    return adj


def bh(p):
    p = np.asarray(p)
    m = len(p)
    order = np.argsort(p)
    adj = np.empty(m)
    prev = 1.0
    for rank in range(m - 1, -1, -1):
        i = order[rank]
        prev = min(prev, p[i] * m / (rank + 1))
        adj[i] = prev
    return adj


# ----------------------------------------------------------------------------- controls

def random_direction_null(F, win, trades, days, rng):
    """§8: random entries in the same window & 30-min bucket, random direction, resampled R."""
    b = F.b5
    if not trades:
        return np.array([])
    start, end, _ = C.WINDOWS[win]
    ws, we = C.hm(start), C.hm(end)
    # candidate 5m bars per (day, bucket)
    day_list = sorted(days.keys())
    cand = {}
    for d in day_list:
        i0, i1, _, _ = days[d]
        for i in range(i0, i1):
            bk = (b.tod[i] // 30) * 30
            cand.setdefault((d, bk), []).append(i)
    buckets = [(int(F.m1.tod[t["k_fill"]]) // 30) * 30 for t in trades]
    Rs = np.array([t["R"] for t in trades])
    rule = trades[0]["exit_rule"]
    n = len(trades)
    means = np.empty(N_NULL)
    for sim in range(N_NULL):
        tot = 0.0
        for j in range(n):
            bk = buckets[j]
            while True:
                d = day_list[rng.integers(len(day_list))]
                lst = cand.get((d, bk))
                if lst:
                    break
            i5 = lst[rng.integers(len(lst))]
            k0 = int(F.m1_start[i5])
            entry = F.m1.o[k0]
            dr = 1 if rng.random() < 0.5 else -1
            R = Rs[rng.integers(n)]
            stop = entry - dr * R
            target = C.target_price(entry, dr, R, rule)
            kx = C.exit_cutoff(F, win, k0)
            _, px, _ = C.simulate_exit(F, k0, kx, dr, entry, stop, target, costs=True)
            tot += dr * (px - entry) * C.PT_VALUE - C.COMMISSION
        means[sim] = tot / n
    return means


def mirror(F, trades):
    out = []
    for t in trades:
        d = -t["dir"]
        stop = t["entry"] - d * t["R"]
        target = C.target_price(t["entry"], d, t["R"], t["exit_rule"])
        _, px, _ = C.simulate_exit(F, t["k_fill"], t["k_cut"], d, t["entry"], stop, target, costs=True)
        out.append(d * (px - t["entry"]) * C.PT_VALUE - C.COMMISSION)
    return np.array(out)


def monte_carlo(net, rng):
    res = {}
    for horizon, thr in ((50, 292.0), (100, 500.0)):
        n = len(net)
        if n == 0:
            res[f"p_dd{int(thr)}_{horizon}"] = np.nan
            continue
        flagged = n < horizon
        if flagged:
            paths = rng.choice(net, size=(N_MC, horizon), replace=True)
        else:
            paths = np.array([rng.permutation(net)[:horizon] for _ in range(N_MC)])
        eq = np.concatenate([np.zeros((N_MC, 1)), np.cumsum(paths, axis=1)], axis=1)
        dd = (np.maximum.accumulate(eq, axis=1) - eq).max(axis=1)
        res[f"p_dd{int(thr)}_{horizon}"] = float((dd > thr).mean())
        res[f"mc_resampled_{horizon}"] = flagged
    return res


# ----------------------------------------------------------------------------- main

def main():
    t_start = time.time()
    sha = verify_prereg()
    df1m = C.load_1m()
    rolls = C.load_rolls()
    F = C.Features(df1m)
    first, last = df1m.index.min(), df1m.index.max()
    cutoff = first + 0.70 * (last - first)
    print(f"data {first} -> {last}; IS/OOS cutoff {cutoff}")

    # ---------------- setups and runs
    sigs = {w: C.find_signals(F, w) for w in C.WINDOWS}
    setups = {}
    for w in C.WINDOWS:
        setups[("A", w)] = C.build_setups(F, "A", w, sigs[w])
        if w in ("NYAM", "ASIA"):
            setups[("B", w)] = C.build_setups(F, "B", w, sigs[w])
            setups[("D", w)] = C.build_setups(F, "D", w)
    tests = test_list()
    runs, funnels = {}, []
    for t in tests:
        if t["family"] == "confluence":
            continue
        tr, fu = C.run_test(F, setups[(t["model"], t["win"])], t["win"], t["exit"], rolls, bias_filter=t["bias"])
        for x in tr:
            x["test_id"], x["exit_rule"] = t["test_id"], t["exit"]
        runs[t["test_id"]] = tr
        funnels.append(dict(test_id=t["test_id"], label=label(t), signals=len(sigs[t["win"]]) if t["model"] != "D" else np.nan, **fu))
    all_trades = [x for tr in runs.values() for x in tr]
    print(f"runs done: {len(all_trades)} trades across 32 tests ({time.time() - t_start:.0f}s)")

    # ---------------- validation (halts on failure)
    val = {}
    n_bf, mism = V.brute_force_check(df1m, all_trades, n=500, seed=BASE_SEED)
    val["brute_force_trades"], val["brute_force_mismatches"] = n_bf, len(mism)
    if mism:
        print(mism[:5])
        sys.exit(f"brute-force simulator mismatches: {len(mism)} / {n_bf}; halting.")
    all_setups = [s for v in setups.values() for s in v]
    val["lookahead_setups_checked"] = V.lookahead_check(F, all_setups, all_trades)
    for model in ("A", "B", "D"):
        su = [s for (mm, w), v in setups.items() if mm == model for s in v]
        val[f"rule_check_{model}"] = V.rule_check(F, df1m, su, n=100, seed=BASE_SEED)
        val[f"truncation_check_{model}"] = V.truncation_check(df1m, F, su, n=20, seed=BASE_SEED)
    by_model = {m: [x for t in tests if t["family"] == "primary" and t["model"] == m for x in runs[t["test_id"]]]
                for m in "ABD"}
    val["charts_check_saved"] = V.faithfulness_charts(F, by_model, os.path.join(OUT, "charts_check"),
                                                      n=15, seed=BASE_SEED)
    print("validation passed:", val, f"({time.time() - t_start:.0f}s)")

    # ---------------- per-test statistics and controls
    rows = []
    null_store, mirror_store = {}, {}
    for t in tests:
        tid = t["test_id"]
        rng = np.random.default_rng(BASE_SEED + 1000 * tid)
        row = dict(test_id=tid, family=t["family"], label=label(t), model=t["model"], win=t["win"], exit=t["exit"])
        if t["family"] == "confluence":
            base = next(x for x in tests if x["family"] == "primary" and x["model"] == "A"
                        and x["win"] == t["win"] and x["exit"] == t["exit"])
            tr = runs[base["test_id"]]
            net = np.array([x["net"] for x in tr])
            rc = np.array([x["rconf"] for x in tr])
            inz = (rc >= 0.62) & (rc <= 0.79)
            row.update(n=len(tr), n_in=int(inz.sum()), n_out=int((~inz).sum()))
            if inz.sum() == 0 or (~inz).sum() == 0:
                row.update(exp_in=np.nan, exp_out=np.nan, diff=np.nan, p_raw=1.0, note="not computable")
            else:
                diff = net[inz].mean() - net[~inz].mean()
                cnt = 0
                for _ in range(N_PERM):
                    pm = rng.permutation(inz)
                    cnt += abs(net[pm].mean() - net[~pm].mean()) >= abs(diff) - 1e-12
                row.update(exp_in=net[inz].mean(), exp_out=net[~inz].mean(), diff=diff,
                           p_raw=(cnt + 1) / (N_PERM + 1), note="")
            rows.append(row)
            continue
        tr = runs[tid]
        net = np.array([x["net"] for x in tr])
        Rn = np.array([x["net_R"] for x in tr])
        s = summarize(net, Rn, rng)
        row.update(s)
        row["p_raw"] = s.get("p_t", 1.0)
        row["exp_usd_zero_cost"] = float(np.mean([x["gross0"] for x in tr])) if tr else np.nan
        tf = pd.to_datetime([x["t_fill"] for x in tr], utc=True) if tr else pd.DatetimeIndex([], tz="UTC")
        is_ = np.asarray(tf < cutoff)
        row["n_is"], row["n_oos"] = int(is_.sum()), int((~is_).sum())
        row["exp_is"] = net[is_].mean() if is_.any() else np.nan
        row["exp_oos"] = net[~is_].mean() if (~is_).any() else np.nan
        yrs = pd.Series(net, index=tf.tz_convert(C.TZ).year if tr else []).groupby(level=0).sum()
        row["years_positive"] = int((yrs > 0).sum())
        row["years_traded"] = int(len(yrs))
        nul = random_direction_null(F, t["win"], tr, C.window_days(F, t["win"]), rng)
        null_store[tid] = nul
        row["null_p95"] = float(np.percentile(nul, 95)) if len(nul) else np.nan
        row["null_pctile"] = float((nul < s["exp_usd"]).mean() * 100) if len(nul) else np.nan
        mir = mirror(F, tr)
        mirror_store[tid] = mir
        row["exp_mirror"] = mir.mean() if len(mir) else np.nan
        row.update(monte_carlo(net, rng))
        rows.append(row)
        print(f"  test {tid:2d} {label(t):22s} n={s.get('n', 0):4d} exp={s.get('exp_usd', np.nan):8.2f} "
              f"null%={row['null_pctile']:.1f} ({time.time() - t_start:.0f}s)")
    res = pd.DataFrame(rows)
    res["p_holm"] = holm(res["p_raw"].values)
    res["p_bh"] = bh(res["p_raw"].values)

    def verdict(r):
        if r["family"] == "confluence":
            return "difference significant" if r["p_holm"] < 0.10 else "no evidence of a difference"
        if r.get("n", 0) == 0:
            return "no trades"
        fails = []
        if not (r["exp_is"] > 0 and r["exp_oos"] > 0):
            fails.append("IS/OOS")
        if r["n"] < 200:
            fails.append("underpowered")
        if r["years_positive"] < 4:
            fails.append("years")
        if not r["exp_usd"] > r["null_p95"]:
            fails.append("null")
        if not r["exp_usd"] > r["exp_mirror"]:
            fails.append("mirror")
        if not r["p_holm"] < 0.10:
            fails.append("p_holm")
        if not fails:
            return "CANDIDATE EDGE"
        return ("underpowered; " if "underpowered" in fails else "") + "no evidence of an edge (fails: " + ",".join(fails) + ")"
    res["verdict"] = res.apply(verdict, axis=1)

    # ---------------- write outputs
    res.to_csv(os.path.join(OUT, "results_tests.csv"), index=False)
    pd.DataFrame(funnels).to_csv(os.path.join(OUT, "funnel_counts.csv"), index=False)
    tdf = pd.DataFrame(all_trades)
    for col in ("arm_time", "t_fill", "t_exit", "win_start", "win_end", "expiry_time"):
        tdf[col] = pd.to_datetime(tdf[col], utc=True).dt.tz_convert(C.TZ)
    tdf["direction"] = np.where(tdf["dir"] == 1, "long", "short")
    tdf["label"] = tdf["test_id"].map({t["test_id"]: label(t) for t in tests})
    tdf["sample"] = np.where(pd.to_datetime(tdf["t_fill"]).dt.tz_convert("UTC") < cutoff, "IS", "OOS")
    keep = ["test_id", "label", "model", "win", "exit_rule", "day", "direction", "level", "arm_time", "t_fill",
            "t_exit", "entry", "stop", "target", "R", "exit_px", "exit_reason", "pts", "net", "net_R", "gross0",
            "bias", "rconf", "leg", "gap", "sample"]
    tdf[keep].to_csv(os.path.join(OUT, "trades_ict.csv"), index=False)
    descriptive_splits(F, tdf, tests, df1m)
    charts(res, runs, null_store, tests, cutoff)
    json.dump(dict(prereg_sha256=sha, validation=val, data_first=str(first), data_last=str(last),
                   is_oos_cutoff=str(cutoff), n_tests=len(tests),
                   expected_false_positives_at_0_05=0.05 * len(tests),
                   raw_p_below_0_05=int((res["p_raw"] < 0.05).sum()),
                   runtime_s=round(time.time() - t_start)),
              open(os.path.join(OUT, "run_summary.json"), "w"), indent=2, default=str)
    write_tables(res, pd.DataFrame(funnels), val)
    print(f"done in {time.time() - t_start:.0f}s")


# ----------------------------------------------------------------------------- descriptive

def descriptive_splits(F, tdf, tests, df1m):
    """Descriptive only (§7): never used for selection."""
    prim = tdf[tdf["test_id"].isin([t["test_id"] for t in tests if t["family"] == "primary"])].copy()
    ft = pd.to_datetime(prim["t_fill"])
    prim["year"] = ft.dt.year
    prim["month"] = ft.dt.month
    prim["weekday"] = ft.dt.day_name()
    prim["bucket30"] = (ft.dt.hour * 60 + (ft.dt.minute // 30) * 30).map(lambda m: f"{m // 60:02d}:{m % 60:02d}")
    # prior completed RTH range tercile (terciles over the full sample)
    rng_rth = F.rth_hi - F.rth_lo
    k = np.searchsorted(F.rth_end, pd.to_datetime(prim["t_fill"]).dt.tz_convert("UTC").astype("int64").values, "right") - 1
    prim["prior_range"] = rng_rth[k]
    q = np.quantile(rng_rth, [1 / 3, 2 / 3])
    prim["range_tercile"] = np.where(prim["prior_range"] <= q[0], "low", np.where(prim["prior_range"] <= q[1], "mid", "high"))
    out = []
    for split in ("direction", "level", "year", "month", "weekday", "bucket30", "range_tercile"):
        g = prim.groupby(["label", split])["net"].agg(["count", "mean", "sum"]).reset_index()
        g.insert(0, "split", split)
        g = g.rename(columns={split: "value"})
        g["value"] = g["value"].astype(str)
        out.append(g)
    pd.concat(out).to_csv(os.path.join(OUT, "descriptive_splits.csv"), index=False)


# ----------------------------------------------------------------------------- charts

def _style(ax):
    ax.grid(alpha=0.3, lw=0.5)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(labelsize=7, colors=INK2)


def charts(res, runs, null_store, tests, cutoff):
    os.makedirs(os.path.join(OUT, "charts"), exist_ok=True)
    std = [t for t in tests if t["family"] != "confluence"]
    for fam in ("primary", "bias"):
        tt = [t for t in std if t["family"] == fam]
        # equity curves
        fig, axes = plt.subplots(4, 4, figsize=(16, 12))
        for ax, t in zip(axes.flat, tt):
            tr = runs[t["test_id"]]
            if tr:
                eq = np.cumsum([x["net"] for x in tr])
                ax.plot(pd.to_datetime([x["t_fill"] for x in tr], utc=True), eq, color=BLUE, lw=1.5)
                ax.axvline(cutoff, color=GRAY, lw=1, ls="--")
            ax.axhline(0, color=INK2, lw=0.6)
            ax.set_title(f"{label(t)}  (n={len(tr)})", fontsize=9, color=INK)
            _style(ax)
        fig.suptitle(f"Equity curves, net $ after costs, 1 MNQ — {fam} tests (dashed line = IS/OOS cutoff)", color=INK)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "charts", f"equity_{fam}.png"), dpi=90)
        plt.close(fig)
        # null histograms
        fig, axes = plt.subplots(4, 4, figsize=(16, 12))
        for ax, t in zip(axes.flat, tt):
            nul = null_store.get(t["test_id"], np.array([]))
            r = res[res["test_id"] == t["test_id"]].iloc[0]
            if len(nul):
                ax.hist(nul, bins=40, color=GRAY, edgecolor="white", linewidth=0.5)
                ax.axvline(r["exp_usd"], color=BLUE, lw=2, label="real")
                ax.axvline(r["null_p95"], color=ORANGE, lw=1.2, ls="--", label="null 95th pct")
            ax.set_title(f"{label(t)}  real at {r['null_pctile']:.0f}th pct", fontsize=9, color=INK)
            _style(ax)
        axes.flat[0].legend(fontsize=7)
        fig.suptitle(f"Random-direction null (1000 sims): mean net $ per trade — {fam} tests", color=INK)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "charts", f"null_{fam}.png"), dpi=90)
        plt.close(fig)
        # yearly bars
        fig, axes = plt.subplots(4, 4, figsize=(16, 12))
        for ax, t in zip(axes.flat, tt):
            tr = runs[t["test_id"]]
            if tr:
                s = pd.Series([x["net"] for x in tr],
                              index=pd.to_datetime([x["t_fill"] for x in tr], utc=True).tz_convert(C.TZ).year)
                y = s.groupby(level=0).sum()
                ax.bar(y.index.astype(str), y.values, color=[BLUE if v > 0 else ORANGE for v in y.values], width=0.7)
            ax.axhline(0, color=INK2, lw=0.6)
            ax.set_title(label(t), fontsize=9, color=INK)
            _style(ax)
        fig.suptitle(f"Net $ by calendar year (blue = positive, orange = negative) — {fam} tests", color=INK)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "charts", f"yearly_{fam}.png"), dpi=90)
        plt.close(fig)


# ----------------------------------------------------------------------------- tables

def _f(x, fmt="{:.2f}"):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    return fmt.format(x)


def write_tables(res, fun, val):
    L = []
    L.append("### Results, all 32 standalone tests (net of costs; p = one-sided t-test)\n")
    L.append("| # | Test | n | IS/OOS n | Win% | BE win% | Avg win | Avg loss | Exp $ | Exp R | Exp $ 0-cost | PF | Max DD $ | "
             "Loss streak | p raw | p Holm | p BH | 95% CI $ | Exp IS | Exp OOS | Yrs + | Null pct | Mirror exp $ | Verdict |")
    L.append("|" + "---|" * 24)
    for _, r in res[res["family"] != "confluence"].iterrows():
        if r.get("n", 0) == 0 or np.isnan(r.get("n", np.nan)):
            L.append(f"| {r.test_id} | {r.label} | 0 |" + " – |" * 20 + f" {r.verdict} |")
            continue
        L.append(f"| {r.test_id} | {r.label} | {int(r.n)} | {int(r.n_is)}/{int(r.n_oos)} | {_f(100 * r.win_rate, '{:.1f}')} | "
                 f"{_f(100 * r.be_win_rate, '{:.1f}')} | {_f(r.avg_win)} | {_f(r.avg_loss)} | {_f(r.exp_usd)} | {_f(r.exp_R, '{:.3f}')} | "
                 f"{_f(r.exp_usd_zero_cost)} | {_f(r.pf)} | {_f(r.max_dd, '{:.0f}')} | {int(r.max_loss_streak)} | {_f(r.p_raw, '{:.3f}')} | "
                 f"{_f(r.p_holm, '{:.3f}')} | {_f(r.p_bh, '{:.3f}')} | [{_f(r.ci_lo)}, {_f(r.ci_hi)}] | {_f(r.exp_is)} | {_f(r.exp_oos)} | "
                 f"{int(r.years_positive)}/{int(r.years_traded)} | {_f(r.null_pctile, '{:.1f}')} | {_f(r.exp_mirror)} | {r.verdict} |")
    L.append("\n### Confluence tests (Model A; FVG midpoint inside vs outside the 62–79% retracement; two-sided permutation)\n")
    L.append("| # | Test | n in | n out | Exp $ in | Exp $ out | Difference | p raw | p Holm | p BH | Verdict |")
    L.append("|" + "---|" * 11)
    for _, r in res[res["family"] == "confluence"].iterrows():
        L.append(f"| {r.test_id} | {r.label} | {int(r.n_in)} | {int(r.n_out)} | {_f(r.exp_in)} | {_f(r.exp_out)} | {_f(r['diff'])} | "
                 f"{_f(r.p_raw, '{:.3f}')} | {_f(r.p_holm, '{:.3f}')} | {_f(r.p_bh, '{:.3f}')} | {r.verdict} |")
    L.append("\n### Monte Carlo (2000 orderings, fresh account; * = fewer trades than the horizon, resampled with replacement)\n")
    L.append("| # | Test | n | P(DD > $292 in 50 trades) | P(DD > $500 in 100 trades) |")
    L.append("|---|---|---|---|---|")
    for _, r in res[res["family"] != "confluence"].iterrows():
        if not r.get("n", 0):
            continue
        L.append(f"| {r.test_id} | {r.label} | {int(r.n)} | {_f(100 * r.p_dd292_50, '{:.1f}')}%{'*' if r.mc_resampled_50 else ''} | "
                 f"{_f(100 * r.p_dd500_100, '{:.1f}')}%{'*' if r.mc_resampled_100 else ''} |")
    L.append("\n### Signal → fill funnel (per test)\n")
    cols = ["signals", "setups", "stale", "skip_small", "skip_large", "skip_leg", "cancel_prearm", "bias_reject",
            "ignored_busy", "ignored_losscap", "armed", "cancelled", "expired", "filled", "roll_excluded"]
    L.append("| # | Test | " + " | ".join(cols) + " |")
    L.append("|" + "---|" * (len(cols) + 2))
    for _, r in fun.iterrows():
        L.append(f"| {r.test_id} | {r.label} | " + " | ".join(_f(r[c], "{:.0f}") for c in cols) + " |")
    L.append("\n### Validation\n")
    for k, v in val.items():
        L.append(f"- {k}: {v}")
    open(os.path.join(OUT, "results_tables.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
