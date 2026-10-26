"""ICT v2 main script. Verifies the pre-registration hash, runs the automated validation gate
(nothing about P&L is computed or printed before it passes), then the 32 tests, controls,
statistics, Monte Carlo, descriptive splits, charts and tables.

Usage:  python3 run_v2.py          (from backtest_ict_v2/)
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

import core_v2 as V2
import validate_v2 as VAL

C = V2.C
HERE = os.path.dirname(os.path.abspath(__file__))
BASE_SEED = 20261027
N_NULL, N_BOOT, N_MC = 1000, 10000, 2000
Z_ALPHA, Z_POWER = 1.6449, 0.8416
BLUE, ORANGE, GRAY, INK, INK2 = "#2a78d6", "#eb6834", "#a3a29c", "#0b0b0b", "#52514e"


def verify_prereg():
    want = open(os.path.join(HERE, "PREREGISTRATION.sha256")).read().split()[0]
    got = hashlib.sha256(open(os.path.join(HERE, "PREREGISTRATION.md"), "rb").read()).hexdigest()
    if got != want:
        sys.exit(f"PREREGISTRATION.md hash mismatch ({got} != {want}); refusing to run.")
    print("pre-registration hash OK:", got)
    return got


def test_list():
    tests, tid = [], 0
    for bias in (False, True):
        for model in V2.MODELS:
            for win in V2.TESTED_WINDOWS:
                for ex in V2.EXITS:
                    tid += 1
                    tests.append(dict(test_id=tid, model=model, win=win, exit=ex, bias=bias,
                                      family="bias" if bias else "primary",
                                      label=f"{model}-{win}-{ex}{'+bias' if bias else ''}"))
    assert len(tests) == 32
    return tests


def build_all(F, windows):
    sigs, sig_counts, setups = {}, {}, {}
    for w in windows:
        sigs[w], sig_counts[w] = V2.find_signals(F, w)
        for model in V2.MODELS:
            setups[(model, w)] = V2.build_setups(F, model, w, sigs[w])
    return sigs, sig_counts, setups


def run_all(F, tests, setups, rolls):
    runs, funnels = {}, {}
    for t in tests:
        tr, fu = V2.run_test(F, setups[(t["model"], t["win"])], t["win"], t["exit"], rolls, bias_filter=t["bias"])
        for x in tr:
            x["test_id"], x["label"] = t["test_id"], t["label"]
        runs[t["test_id"]], funnels[t["test_id"]] = tr, fu
    return runs, funnels


# ----------------------------------------------------------------------------- statistics (§9)

def max_dd(x):
    eq = np.concatenate([[0.0], np.cumsum(x)])
    return float((np.maximum.accumulate(eq) - eq).max())


def loss_streak(x):
    best = cur = 0
    for v in x:
        cur = cur + 1 if v < 0 else 0
        best = max(best, cur)
    return best


def summarize(tr, rng=None):
    """Per-test metrics (§9). R metrics on net R; $ metrics on net $."""
    n = len(tr)
    if n == 0:
        return dict(n=0)
    R = np.array([x["net_R"] for x in tr])
    usd = np.array([x["net"] for x in tr])
    win = R > 0
    aw, al = (R[win].mean() if win.any() else 0.0), (R[~win].mean() if (~win).any() else 0.0)
    sd = R.std(ddof=1) if n > 1 else np.nan
    p = float(stats.ttest_1samp(R, 0.0, alternative="greater").pvalue) if n > 1 and sd > 0 else 1.0
    out = dict(n=n, win_rate=win.mean(), be_win_rate=abs(al) / (aw + abs(al)) if (aw + abs(al)) > 0 else np.nan,
               avg_win_R=aw, avg_loss_R=al,
               avg_win_usd=usd[usd > 0].mean() if (usd > 0).any() else 0.0,
               avg_loss_usd=usd[usd <= 0].mean() if (usd <= 0).any() else 0.0,
               exp_R=R.mean(), exp_usd=usd.mean(),
               exp_R_zero_cost=np.mean([x["gross0_R"] for x in tr]),
               pf=usd[usd > 0].sum() / abs(usd[usd <= 0].sum()) if (usd <= 0).any() and usd[usd <= 0].sum() != 0 else np.inf,
               max_dd_usd=max_dd(usd), max_dd_R=max_dd(R), loss_streak=loss_streak(R), sd_R=sd, p_raw=p,
               mde_R=(Z_ALPHA + Z_POWER) * sd / np.sqrt(n) if n > 1 else np.nan)
    if rng is not None:
        boot = rng.choice(R, size=(N_BOOT, n), replace=True).mean(axis=1)
        out["ci_lo"], out["ci_hi"] = float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))
    return out


def holm(p):
    p = np.asarray(p, float)
    order, m = np.argsort(p), len(p)
    adj, run = np.empty(m), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (m - rank) * p[i]))
        adj[i] = run
    return adj


def bh(p):
    p = np.asarray(p, float)
    m, order = len(p), np.argsort(p)
    adj, prev = np.empty(m), 1.0
    for rank in range(m - 1, -1, -1):
        i = order[rank]
        prev = min(prev, p[i] * m / (rank + 1))
        adj[i] = prev
    return adj


def monte_carlo(usd, rng):
    res = {}
    for horizon, thr in ((50, 292.0), (100, 500.0)):
        n = len(usd)
        if n == 0:
            res[f"p_dd{int(thr)}_{horizon}"], res[f"mc_resampled_{horizon}"] = np.nan, False
            continue
        flag = n < horizon
        paths = rng.choice(usd, size=(N_MC, horizon), replace=True) if flag else \
            np.array([rng.permutation(usd)[:horizon] for _ in range(N_MC)])
        eq = np.concatenate([np.zeros((N_MC, 1)), np.cumsum(paths, axis=1)], axis=1)
        dd = (np.maximum.accumulate(eq, axis=1) - eq).max(axis=1)
        res[f"p_dd{int(thr)}_{horizon}"], res[f"mc_resampled_{horizon}"] = float((dd > thr).mean()), flag
    return res


def verdict(r):
    if not r.get("n"):
        return "no trades"
    fails = []
    if not (r["exp_R_is"] > 0 and r["exp_R_oos"] > 0):
        fails.append("IS/OOS")
    if r["n"] < 200:
        fails.append("underpowered")
    if r["years_positive"] < 4:
        fails.append("years")
    if not r["exp_R"] > r["null_p95"]:
        fails.append("null")
    if not r["exp_R"] > r["mirror_R"]:
        fails.append("mirror")
    if not r["p_holm"] < 0.10:
        fails.append("p_holm")
    if not fails:
        return "CANDIDATE EDGE (lead only; see honesty clause)"
    return ("underpowered; " if "underpowered" in fails else "") + "no evidence of an edge (fails: " + ",".join(fails) + ")"


# ----------------------------------------------------------------------------- main

def main():
    t0 = time.time()
    sha = verify_prereg()
    df1m, rolls = C.load_1m(), C.load_rolls()
    F = C.Features(df1m)
    first, last = df1m.index.min(), df1m.index.max()
    cutoff = first + 0.70 * (last - first)
    cut_ns = cutoff.value
    print(f"data {first} -> {last}; IS/OOS cutoff {cutoff}")

    sigs, sig_counts, setups = build_all(F, V2.TESTED_WINDOWS + V2.DESCRIPTIVE_WINDOWS)
    tests = test_list()
    runs, funnels = run_all(F, tests, setups, rolls)
    all_trades = [x for tr in runs.values() for x in tr]
    print(f"runs done: {len(all_trades)} trades in 32 tests ({time.time() - t0:.0f}s)")

    # ---------------- validation gate: nothing about P&L before this passes
    val = {}
    n_bf, mism = VAL.brute_force_check(df1m, all_trades, n=500, seed=BASE_SEED)
    val["brute_force_trades"], val["brute_force_mismatches"] = n_bf, len(mism)
    if mism:
        print("first mismatches (fills/exits only):", [(a, {k: v for k, v in b.items() if k != "net"}) for a, b, _ in mism[:3]])
        sys.exit(f"brute-force mismatches {len(mism)}/{n_bf}; halting.")
    val["mutation_detected"] = VAL.mutation_check(df1m, all_trades, n=500, seed=BASE_SEED)
    if val["mutation_detected"] == 0:
        sys.exit("mutation test not detected; the brute-force check has no teeth. Halting.")
    test_setups = [s for (mdl, w), v in setups.items() if w in V2.TESTED_WINDOWS for s in v]
    val["lookahead_setups_checked"] = VAL.lookahead_check(F, test_setups, all_trades)
    for model in V2.MODELS:
        su = [s for (mdl, w), v in setups.items() if mdl == model and w in V2.TESTED_WINDOWS for s in v]
        val[f"rule_check_{model}"] = VAL.rule_check(F, df1m, su, n=100, seed=BASE_SEED)
        val[f"truncation_check_{model}"] = VAL.truncation_check(df1m, F, su, n=20, seed=BASE_SEED)
    print("automated validation passed:", val, f"({time.time() - t0:.0f}s)")
    by_model = {m: [x for t in tests if t["family"] == "primary" and t["model"] == m for x in runs[t["test_id"]]]
                for m in V2.MODELS}
    val["charts_check_saved"] = VAL.faithfulness_charts(F, by_model, os.path.join(HERE, "charts_check"), n=15, seed=BASE_SEED)

    # ---------------- per-test statistics and controls
    rows = []
    null_store = {}
    for t in tests:
        tid, tr = t["test_id"], runs[t["test_id"]]
        rng = np.random.default_rng(BASE_SEED + 1000 * tid)
        fu = funnels[tid]
        row = dict(test_id=tid, label=t["label"], family=t["family"], model=t["model"], win=t["win"], exit=t["exit"])
        row.update(summarize(tr, rng))
        row["fill_ratio"] = fu["filled"] / fu["valid"] if fu["valid"] else np.nan
        row["low_fill_flag"] = bool(row["fill_ratio"] < 0.30) if fu["valid"] else True
        if tr:
            R = np.array([x["net_R"] for x in tr])
            tf = np.array([x["t_fill"] for x in tr])
            is_ = tf < cut_ns
            row["n_is"], row["n_oos"] = int(is_.sum()), int((~is_).sum())
            row["exp_R_is"] = R[is_].mean() if is_.any() else np.nan
            row["exp_R_oos"] = R[~is_].mean() if (~is_).any() else np.nan
            k = len(R) // 3
            blocks = [R[:k], R[k:2 * k], R[2 * k:]] if k > 0 else [R, np.array([]), np.array([])]
            for bi, blk in enumerate(blocks, 1):
                row[f"block{bi}_R"] = blk.mean() if len(blk) else np.nan
            yrs = pd.Series(R, index=pd.to_datetime(tf, utc=True).tz_convert(C.TZ).year).groupby(level=0).sum()
            row["years_positive"], row["years_traded"] = int((yrs > 0).sum()), int(len(yrs))
            nul = V2.random_direction_null(F, t["win"], tr, t["model"], N_NULL, rng)
            null_store[tid] = nul
            row["null_p95"] = float(np.percentile(nul, 95))
            row["null_pctile"] = float((nul < row["exp_R"]).mean() * 100)
            row["mirror_R"] = float(V2.mirror(F, tr).mean())
            row.update(monte_carlo(np.array([x["net"] for x in tr]), rng))
        rows.append(row)
        print(f"  test {tid:2d} {t['label']:18s} n={row.get('n', 0):4d}  ({time.time() - t0:.0f}s)")
    res = pd.DataFrame(rows)
    res["p_raw"] = res["p_raw"].fillna(1.0)
    res["p_holm"], res["p_bh"] = holm(res["p_raw"]), bh(res["p_raw"])
    res["verdict"] = res.apply(verdict, axis=1)

    # ---------------- outputs
    res.to_csv(os.path.join(HERE, "results_tests_v2.csv"), index=False)
    fun = pd.DataFrame([dict(test_id=t["test_id"], label=t["label"],
                             signals=len(sigs[t["win"]]),
                             signals_with_fvg=sum(s["has_fvg"] for s in sigs[t["win"]]),
                             **funnels[t["test_id"]]) for t in tests])
    fun.to_csv(os.path.join(HERE, "funnel_v2.csv"), index=False)
    write_trades(all_trades, cut_ns)
    skip_by_year(setups)
    desc = descriptive(F, runs, tests, setups, rolls)
    charts(res, runs, null_store, tests, cutoff)
    json.dump(dict(prereg_sha256=sha, validation=val, data_first=str(first), data_last=str(last),
                   is_oos_cutoff=str(cutoff), n_tests=32, expected_false_positives_at_0_05=0.05 * 32,
                   raw_p_below_0_05=int((res["p_raw"] < 0.05).sum()),
                   candidates=int(res["verdict"].str.startswith("CANDIDATE").sum()),
                   signal_counts={w: dict(signals=len(sigs[w]), **sig_counts[w]) for w in sigs},
                   runtime_s=round(time.time() - t0)),
              open(os.path.join(HERE, "run_summary_v2.json"), "w"), indent=2, default=str)
    write_tables(res, fun, val, desc)
    print(f"done in {time.time() - t0:.0f}s")


# ----------------------------------------------------------------------------- outputs

def write_trades(all_trades, cut_ns):
    tdf = pd.DataFrame(all_trades)
    for col in ("arm_time", "t_fill", "t_exit", "win_start", "win_end", "expiry_time"):
        tdf[col] = pd.to_datetime(tdf[col], utc=True).dt.tz_convert(C.TZ)
    tdf["direction"] = np.where(tdf["dir"] == 1, "long", "short")
    tdf["sample"] = np.where(pd.to_datetime(tdf["t_fill"]).dt.tz_convert("UTC").astype("int64") < cut_ns, "IS", "OOS")
    keep = ["test_id", "label", "model", "win", "exit_rule", "day", "direction", "level", "arm_time", "t_fill", "t_exit",
            "entry", "stop", "target", "R", "atr_s", "R_atr", "exit_px", "exit_reason", "net", "net_R", "gross0", "gross0_R",
            "bias", "gap", "leg", "sample"]
    tdf[keep].to_csv(os.path.join(HERE, "trades_ict_v2.csv"), index=False)


def skip_by_year(setups):
    rows = []
    for (model, win), lst in setups.items():
        for su in lst:
            rows.append(dict(model=model, win=win, status=su["status"],
                             year=pd.Timestamp(su["arm_time"], tz="UTC").tz_convert(C.TZ).year))
    d = pd.DataFrame(rows)
    d.groupby(["model", "win", "status", "year"]).size().unstack("year", fill_value=0).to_csv(
        os.path.join(HERE, "skips_by_reason_year_v2.csv"))


def descriptive(F, runs, tests, setups, rolls):
    """Exploratory splits (§7). Never used for selection."""
    prim = [x for t in tests if t["family"] == "primary" for x in runs[t["test_id"]]]
    d = pd.DataFrame(prim)
    ft = pd.to_datetime(d["t_fill"], utc=True).dt.tz_convert(C.TZ)
    d["year"], d["month"], d["weekday"] = ft.dt.year, ft.dt.month, ft.dt.day_name()
    mins = ft.dt.hour * 60 + ft.dt.minute
    d["bucket30"] = ((mins // 30) * 30).map(lambda v: f"{v // 60:02d}:{v % 60:02d}")
    d["sb_am"] = np.where((mins >= 540) & (mins < 600), "SB-AM fill", "outside SB-AM")
    d["direction"] = np.where(d["dir"] == 1, "long", "short")
    rng_rth = F.rth_hi - F.rth_lo
    k = np.searchsorted(F.rth_end, d["t_fill"].values, "right") - 1
    q = np.quantile(rng_rth, [1 / 3, 2 / 3])
    pr = rng_rth[k]
    d["range_tercile"] = np.where(pr <= q[0], "low", np.where(pr <= q[1], "mid", "high"))
    d["account_fit"] = np.where(d["R"] <= 30, "stop<=30pts", "stop>30pts")
    out = []
    for split in ("direction", "level", "year", "month", "weekday", "bucket30", "sb_am", "range_tercile", "account_fit"):
        g = d.groupby(["label", split]).agg(n=("net_R", "size"), mean_R=("net_R", "mean"), sum_R=("net_R", "sum"),
                                             mean_usd=("net", "mean")).reset_index()
        g.insert(0, "split", split)
        out.append(g.rename(columns={split: "value"}).astype({"value": str}))
    # SB-PM: separate descriptive-only simulation (not a test)
    sb = []
    for model in V2.MODELS:
        for ex in V2.EXITS:
            tr, fu = V2.run_test(F, setups[(model, "SBPM")], "SBPM", ex, rolls)
            R = np.array([x["net_R"] for x in tr])
            sb.append(dict(split="SB-PM run", label=f"{model}-SBPM-{ex}", value="13:00-14:00", n=len(R),
                           mean_R=R.mean() if len(R) else np.nan, sum_R=R.sum(),
                           mean_usd=np.mean([x["net"] for x in tr]) if tr else np.nan))
    out.append(pd.DataFrame(sb))
    # stop distance in points by year
    sp = d.groupby(["model", "win", "year"])["R"].describe()[["count", "25%", "50%", "75%"]].reset_index()
    sp.to_csv(os.path.join(HERE, "stop_points_by_year_v2.csv"), index=False)
    res = pd.concat(out)
    res.to_csv(os.path.join(HERE, "descriptive_splits_v2.csv"), index=False)
    return res


def _style(ax):
    ax.grid(alpha=0.3, lw=0.5)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(labelsize=7, colors=INK2)


def charts(res, runs, null_store, tests, cutoff):
    os.makedirs(os.path.join(HERE, "charts"), exist_ok=True)
    for fam in ("primary", "bias"):
        tt = [t for t in tests if t["family"] == fam]
        specs = (("equity", "Cumulative net R per trade (after costs) — dashed line = IS/OOS cutoff"),
                 ("null", "Random-direction null (1000 sims): mean net R per trade"),
                 ("yearly", "Net R by calendar year (blue = positive, orange = negative)"))
        for kind, title in specs:
            fig, axes = plt.subplots(4, 4, figsize=(16, 12))
            for ax, t in zip(axes.flat, tt):
                tr = runs[t["test_id"]]
                r = res[res["test_id"] == t["test_id"]].iloc[0]
                if kind == "equity":
                    if tr:
                        ax.plot(pd.to_datetime([x["t_fill"] for x in tr], utc=True), np.cumsum([x["net_R"] for x in tr]),
                                color=BLUE, lw=1.5)
                        ax.axvline(cutoff, color=GRAY, lw=1, ls="--")
                    ax.axhline(0, color=INK2, lw=0.6)
                    ax.set_title(f"{t['label']}  (n={len(tr)})", fontsize=9, color=INK)
                elif kind == "null":
                    nul = null_store.get(t["test_id"], np.array([]))
                    if len(nul):
                        ax.hist(nul, bins=40, color=GRAY, edgecolor="white", linewidth=0.5)
                        ax.axvline(r["exp_R"], color=BLUE, lw=2, label="real")
                        ax.axvline(r["null_p95"], color=ORANGE, lw=1.2, ls="--", label="null 95th pct")
                        ax.set_title(f"{t['label']}  real at {r['null_pctile']:.0f}th pct", fontsize=9, color=INK)
                    else:
                        ax.set_title(f"{t['label']}  (no trades)", fontsize=9, color=INK)
                else:
                    if tr:
                        s = pd.Series([x["net_R"] for x in tr],
                                      index=pd.to_datetime([x["t_fill"] for x in tr], utc=True).tz_convert(C.TZ).year)
                        y = s.groupby(level=0).sum()
                        ax.bar(y.index.astype(str), y.values, color=[BLUE if v > 0 else ORANGE for v in y.values], width=0.7)
                    ax.axhline(0, color=INK2, lw=0.6)
                    ax.set_title(t["label"], fontsize=9, color=INK)
                _style(ax)
            if kind == "null":
                axes.flat[0].legend(fontsize=7)
            fig.suptitle(f"{title} — {fam} tests", color=INK)
            fig.tight_layout()
            fig.savefig(os.path.join(HERE, "charts", f"{kind}_{fam}.png"), dpi=90)
            plt.close(fig)


def _f(x, fmt="{:.3f}"):
    try:
        if x is None or np.isnan(x):
            return "–"
    except TypeError:
        pass
    return fmt.format(x)


def write_tables(res, fun, val, desc):
    L = ["### Results — all 32 tests (net of costs; primary metric = expectancy in R; p = one-sided t-test on net R)\n",
         "| # | Test | n | IS/OOS n | Win% | BE win% | Avg win R | Avg loss R | Exp R | Exp R 0-cost | Exp $ | Avg win $ | Avg loss $ | PF | "
         "Max DD $ | Loss streak | p raw | p Holm | p BH | 95% CI (R) | MDE R | Exp R IS | Exp R OOS | Blocks 1/2/3 (R) | Yrs + | "
         "Null pct | Mirror R | Verdict |",
         "|" + "---|" * 28]
    for _, r in res.iterrows():
        if not r.get("n"):
            L.append(f"| {r.test_id} | {r.label} | 0 |" + " – |" * 24 + f" {r.verdict} |")
            continue
        L.append(
            f"| {r.test_id} | {r.label} | {int(r.n)} | {int(r.n_is)}/{int(r.n_oos)} | {_f(100 * r.win_rate, '{:.1f}')} | "
            f"{_f(100 * r.be_win_rate, '{:.1f}')} | {_f(r.avg_win_R, '{:.2f}')} | {_f(r.avg_loss_R, '{:.2f}')} | {_f(r.exp_R)} | "
            f"{_f(r.exp_R_zero_cost)} | {_f(r.exp_usd, '{:.2f}')} | {_f(r.avg_win_usd, '{:.2f}')} | {_f(r.avg_loss_usd, '{:.2f}')} | "
            f"{_f(r.pf, '{:.2f}')} | {_f(r.max_dd_usd, '{:.0f}')} | {int(r.loss_streak)} | {_f(r.p_raw)} | {_f(r.p_holm)} | "
            f"{_f(r.p_bh)} | [{_f(r.ci_lo)}, {_f(r.ci_hi)}] | {_f(r.mde_R)} | {_f(r.exp_R_is)} | {_f(r.exp_R_oos)} | "
            f"{_f(r.block1_R, '{:.2f}')}/{_f(r.block2_R, '{:.2f}')}/{_f(r.block3_R, '{:.2f}')} | "
            f"{int(r.years_positive)}/{int(r.years_traded)} | {_f(r.null_pctile, '{:.1f}')} | {_f(r.mirror_R)} | {r.verdict} |")
    L += ["\n### Monte Carlo ($; 2000 orderings, fresh account; * = n below horizon, resampled with replacement)\n",
          "Warning: risk per trade varies with stop size, so these $ drawdown probabilities are not R-based.\n",
          "| # | Test | n | P(DD > $292 in 50) | P(DD > $500 in 100) |", "|---|---|---|---|---|"]
    for _, r in res.iterrows():
        if r.get("n"):
            L.append(f"| {r.test_id} | {r.label} | {int(r.n)} | {_f(100 * r.p_dd292_50, '{:.1f}')}%{'*' if r.mc_resampled_50 else ''} | "
                     f"{_f(100 * r.p_dd500_100, '{:.1f}')}%{'*' if r.mc_resampled_100 else ''} |")
    cols = ["signals", "signals_with_fvg", "setups", "stale", "skip_small", "skip_large", "skip_leg", "fill_outside_window",
            "gap_through_stop", "valid", "bias_reject", "ignored_busy", "ignored_losscap", "armed", "cancelled", "expired",
            "filled", "roll_excluded"]
    L += ["\n### Funnel: signal → setup → armed → filled, with every skip/cancel reason (⚠ = fills < 30% of valid setups)\n",
          "`signals` = sweep→MSS signals in the window (A1/A2 additionally need the FVG: `signals_with_fvg`; D counts BOS setups).\n",
          "| # | Test | " + " | ".join(cols) + " | fill/valid |", "|" + "---|" * (len(cols) + 3)]
    for _, r in fun.iterrows():
        rr = res[res["test_id"] == r.test_id].iloc[0]
        sig = "–" if r.label.startswith("D") else str(int(r.signals))
        sfvg = str(int(r.signals_with_fvg)) if r.label.startswith("A") else "–"
        vals = [sig, sfvg] + [str(int(r[c])) for c in cols[2:]]
        flag = " ⚠" if rr.low_fill_flag else ""
        L.append(f"| {r.test_id} | {r.label} | " + " | ".join(vals) + f" | {_f(100 * rr.fill_ratio, '{:.0f}')}%{flag} |")
    L += ["\n### Validation\n"] + [f"- {k}: {v}" for k, v in val.items()]
    open(os.path.join(HERE, "results_tables_v2.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
