"""ORB main script: hash check -> validation gate (no P&L computed or printed before it passes) ->
24 tests, controls, drift baseline, statistics, Monte Carlo, descriptive splits, charts, tables.

Usage:  python3 backtest_orb/run_orb.py
"""
import hashlib
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import orb_core as O
import validate_orb as VAL
import run_v2 as RV          # statistics helpers from study 3 (summarize, holm, bh, monte_carlo)

C = O.C
HERE = os.path.dirname(os.path.abspath(__file__))
BASE_SEED = 20261028
N_NULL = 1000
BLUE, ORANGE, GRAY, INK, INK2 = "#2a78d6", "#eb6834", "#a3a29c", "#0b0b0b", "#52514e"


def verify_prereg():
    want = open(os.path.join(HERE, "PREREGISTRATION.sha256")).read().split()[0]
    got = hashlib.sha256(open(os.path.join(HERE, "PREREGISTRATION.md"), "rb").read()).hexdigest()
    if got != want:
        sys.exit(f"PREREGISTRATION.md hash mismatch ({got} != {want}); refusing to run.")
    print("pre-registration hash OK:", got)
    return got


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


def main():
    t0 = time.time()
    sha = verify_prereg()
    df1m, rolls = C.load_1m(), C.load_rolls()
    M = O.Market(df1m)
    first, last = df1m.index.min(), df1m.index.max()
    cutoff = first + 0.70 * (last - first)
    cut_ns = cutoff.value
    print(f"data {first} -> {last}; IS/OOS cutoff {cutoff}; candidate days {len(M.days)}")
    infos, runs, funnels = O.run_all(M, rolls)
    tests = O.tests()
    all_trades = [x for v in runs.values() for x in v]
    print(f"runs done: {len(all_trades)} trades in 24 tests ({time.time() - t0:.0f}s)")

    # ---------------- validation gate
    X = VAL.CT(df1m)
    val = {}
    n_bf, mism = VAL.brute_force_check(X, all_trades, 500, BASE_SEED)
    val["brute_force_trades"], val["brute_force_mismatches"] = n_bf, len(mism)
    if mism:
        print("first mismatch (no P&L shown):", mism[0][0], mism[0][1])
        sys.exit(f"brute-force mismatches {len(mism)}/{n_bf}; halting.")
    val["mutation_detected"] = VAL.mutation_check(X, all_trades, 500, BASE_SEED)
    if val["mutation_detected"] == 0:
        sys.exit("mutation not detected; halting.")
    val["lookahead_trades_checked"] = VAL.lookahead_check(M, infos, all_trades)
    val["rule_check_days"] = VAL.rule_check(M, X, infos, 100, BASE_SEED)
    val["truncation_days"] = VAL.truncation_check(df1m, M, infos, runs, 20, BASE_SEED)
    print("automated validation passed:", val, f"({time.time() - t0:.0f}s)")
    val["charts_check_saved"] = VAL.faithfulness_charts(M, runs, os.path.join(HERE, "charts_check"), 30, BASE_SEED)

    # ---------------- statistics and controls
    rows, null_store = [], {}
    for t in tests:
        tid, tr = t["test_id"], runs[t["test_id"]]
        fu = funnels[tid]
        rng = np.random.default_rng(BASE_SEED + 1000 * tid)
        row = dict(test_id=tid, label=t["label"], N=t["N"], stop=t["stop"], exit=t["exit"], filter=t["filter"])
        row.update(RV.summarize(tr, rng))
        row["pct_days_traded"] = len(tr) / fu["eligible"] if fu["eligible"] else np.nan
        if tr:
            R = np.array([x["net_R"] for x in tr])
            tf = np.array([x["t_fill"] for x in tr])
            is_ = tf < cut_ns
            row.update(n_is=int(is_.sum()), n_oos=int((~is_).sum()),
                       exp_R_is=R[is_].mean() if is_.any() else np.nan, exp_R_oos=R[~is_].mean() if (~is_).any() else np.nan)
            k = len(R) // 3
            for bi, blk in enumerate([R[:k], R[k:2 * k], R[2 * k:]], 1):
                row[f"block{bi}_R"] = blk.mean() if len(blk) else np.nan
            yrs = pd.Series(R, index=pd.to_datetime(tf, utc=True).tz_convert(C.TZ).year).groupby(level=0).sum()
            row["years_positive"], row["years_traded"] = int((yrs > 0).sum()), int(len(yrs))
            nul = O.drift_null(M, infos, tr, N_NULL, rng)
            null_store[tid] = nul
            row["null_p95"] = float(np.percentile(nul, 95))
            row["null_pctile"] = float((nul < row["exp_R"]).mean() * 100)
            row["mirror_R"] = float(O.mirror(M, tr).mean())
            row["drift_long_R"], row["drift_short_R"], _ = O.drift_baseline(M, tr)
            row["long_share"] = float(np.mean([x["dir"] == 1 for x in tr]))
            Rp = np.array([x["R"] for x in tr])
            row["share_R_gt30"] = float((Rp > 30).mean())
            row["fit_50"], row["fit_62"] = float((Rp * 2 <= 50).mean()), float((Rp * 2 <= 62).mean())
            row["median_R_pts"] = float(np.median(Rp))
            row.update(RV.monte_carlo(np.array([x["net"] for x in tr]), rng))
        rows.append(row)
        print(f"  test {tid:2d} {t['label']:16s} n={row.get('n', 0)} ({time.time() - t0:.0f}s)")
    res = pd.DataFrame(rows)
    res["p_raw"] = res["p_raw"].fillna(1.0)
    res["p_holm"], res["p_bh"] = RV.holm(res["p_raw"]), RV.bh(res["p_raw"])
    res["verdict"] = res.apply(verdict, axis=1)

    # ---------------- outputs
    res.to_csv(os.path.join(HERE, "results_orb.csv"), index=False)
    fun = pd.DataFrame([dict(test_id=t["test_id"], label=t["label"], **funnels[t["test_id"]]) for t in tests])
    fun.to_csv(os.path.join(HERE, "funnel_orb.csv"), index=False)
    O.skip_R_by_year(infos).to_csv(os.path.join(HERE, "skip_R8_by_year.csv"))
    write_trades(all_trades, cut_ns)
    descriptive(M, infos, runs, tests)
    charts(res, runs, null_store, tests, cutoff)
    json.dump(dict(prereg_sha256=sha, validation=val, data_first=str(first), data_last=str(last), is_oos_cutoff=str(cutoff),
                   candidate_days=len(M.days), n_tests=24, expected_false_positives_at_0_05=1.2,
                   raw_p_below_0_05=int((res["p_raw"] < 0.05).sum()),
                   candidates=int(res["verdict"].str.startswith("CANDIDATE").sum()),
                   runtime_s=round(time.time() - t0)),
              open(os.path.join(HERE, "run_summary_orb.json"), "w"), indent=2, default=str)
    write_tables(res, fun, val)
    print(f"done in {time.time() - t0:.0f}s")


def write_trades(all_trades, cut_ns):
    d = pd.DataFrame(all_trades)
    for col in ("or_end", "t_fill", "t_exit"):
        d[col] = pd.to_datetime(d[col], utc=True).dt.tz_convert(C.TZ)
    d["date"] = pd.to_datetime(d["date"]).dt.date
    d["direction"] = np.where(d["dir"] == 1, "long", "short")
    d["sample"] = np.where(pd.to_datetime(d["t_fill"]).dt.tz_convert("UTC").astype("int64") < cut_ns, "IS", "OOS")
    keep = ["test_id", "label", "date", "N", "stop_rule", "exit_rule", "filter", "direction", "orh", "orl", "TL", "TS",
            "ema", "ema_close", "or_end", "t_fill", "entry", "stop", "R", "target", "t_exit", "exit_px", "exit_reason",
            "net", "net_R", "gross0", "gross0_R", "sample"]
    d[keep].to_csv(os.path.join(HERE, "trades_orb.csv"), index=False)


def descriptive(M, infos, runs, tests):
    """Exploratory splits (§6), never used for selection."""
    rows = []
    # gap = 08:30 open - last close of the previous RTH session (last 1m bar before 15:00 CT)
    m1 = M.m1
    rth = np.where((m1.tod >= C.hm("08:30")) & (m1.tod < C.hm("15:00")))[0]
    last_close = pd.Series(m1.c[rth], index=m1.date[rth]).groupby(level=0).last()
    dates = np.array(sorted(M.days))
    prev_close = last_close.reindex(dates).shift(1)            # previous RTH date in the data
    gap_of = {d: m1.o[M.days[d]] - prev_close[d] for d in dates}
    for t in tests:
        tr = runs[t["test_id"]]
        if not tr:
            continue
        ok = [i for i in infos[t["N"]].values() if i["status"] == "ok"]
        w = np.array([(i["orh"] - i["orl"]) / i["atr"] for i in ok])
        qw = np.nanquantile(w, [1 / 3, 2 / 3])
        d = pd.DataFrame(tr)
        ft = pd.to_datetime(d["t_fill"], utc=True).dt.tz_convert(C.TZ)
        d["year"], d["month"], d["weekday"] = ft.dt.year, ft.dt.month, ft.dt.day_name()
        d["direction"] = np.where(d["dir"] == 1, "long", "short")
        wr = (d["orh"] - d["orl"]) / d["atr"]
        d["or_width_tercile"] = np.where(wr <= qw[0], "narrow", np.where(wr <= qw[1], "mid", "wide"))
        d["gap"] = [gap_of[x["date"]] for x in tr]
        qg = np.nanquantile(np.abs(d["gap"]), [1 / 3, 2 / 3])
        d["gap_tercile"] = np.where(np.abs(d["gap"]) <= qg[0], "small |gap|", np.where(np.abs(d["gap"]) <= qg[1], "mid |gap|", "large |gap|"))
        d["account_fit"] = np.where(d["R"] <= 30, "R<=30pts", "R>30pts")
        for split in ("direction", "year", "month", "weekday", "or_width_tercile", "gap_tercile", "account_fit"):
            g = d.groupby(split).agg(n=("net_R", "size"), mean_R=("net_R", "mean"), sum_R=("net_R", "sum"),
                                      mean_usd=("net", "mean")).reset_index().rename(columns={split: "value"})
            g.insert(0, "split", split)
            g.insert(0, "label", t["label"])
            g["value"] = g["value"].astype(str)
            rows.append(g)
    pd.concat(rows).to_csv(os.path.join(HERE, "descriptive_splits_orb.csv"), index=False)
    # R distribution in points by year (all tests pooled per N and stop rule, F0 E2 — R does not depend on the exit)
    rr = []
    for t in tests:
        if t["exit"] == "E2" and t["filter"] == "F0":
            for x in runs[t["test_id"]]:
                rr.append(dict(N=t["N"], stop=t["stop"], year=pd.Timestamp(x["date"]).year, R=x["R"]))
    r = pd.DataFrame(rr)
    g = r.groupby(["N", "stop", "year"])["R"]
    out = g.describe()[["count", "25%", "50%", "75%"]]
    out["share_R_gt30"] = g.apply(lambda s: (s > 30).mean())
    out["share_fit_50usd"] = g.apply(lambda s: (s * 2 <= 50).mean())
    out.reset_index().to_csv(os.path.join(HERE, "R_points_by_year.csv"), index=False)


def _style(ax):
    ax.grid(alpha=0.3, lw=0.5)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(labelsize=7, colors=INK2)


def charts(res, runs, null_store, tests, cutoff):
    os.makedirs(os.path.join(HERE, "charts"), exist_ok=True)
    for kind, title in (("equity", "Cumulative net R (after costs) — dashed line = IS/OOS cutoff"),
                        ("null", "Drift-matched random-timing null (1000 sims): mean net R per trade"),
                        ("yearly", "Net R by calendar year (blue = positive, orange = negative)")):
        fig, axes = plt.subplots(4, 6, figsize=(22, 13))
        for ax, t in zip(axes.flat, tests):
            tr = runs[t["test_id"]]
            r = res[res["test_id"] == t["test_id"]].iloc[0]
            if kind == "equity" and tr:
                ax.plot(pd.to_datetime([x["t_fill"] for x in tr], utc=True), np.cumsum([x["net_R"] for x in tr]), color=BLUE, lw=1.3)
                ax.axvline(cutoff, color=GRAY, lw=1, ls="--")
                ax.axhline(0, color=INK2, lw=0.6)
                ax.set_title(f"{t['label']} (n={len(tr)})", fontsize=9, color=INK)
            elif kind == "null" and t["test_id"] in null_store:
                ax.hist(null_store[t["test_id"]], bins=40, color=GRAY, edgecolor="white", linewidth=0.5)
                ax.axvline(r["exp_R"], color=BLUE, lw=2, label="real")
                ax.axvline(r["null_p95"], color=ORANGE, lw=1.2, ls="--", label="null 95th pct")
                ax.set_title(f"{t['label']} real at {r['null_pctile']:.0f}th pct", fontsize=9, color=INK)
            elif kind == "yearly" and tr:
                s = pd.Series([x["net_R"] for x in tr], index=pd.to_datetime([x["t_fill"] for x in tr], utc=True).tz_convert(C.TZ).year)
                y = s.groupby(level=0).sum()
                ax.bar(y.index.astype(str), y.values, color=[BLUE if v > 0 else ORANGE for v in y.values], width=0.7)
                ax.axhline(0, color=INK2, lw=0.6)
                ax.set_title(t["label"], fontsize=9, color=INK)
            _style(ax)
        if kind == "null":
            axes.flat[0].legend(fontsize=7)
        fig.suptitle(f"ORB — {title}", color=INK)
        fig.tight_layout()
        fig.savefig(os.path.join(HERE, "charts", f"{kind}_orb.png"), dpi=80)
        plt.close(fig)


def _f(x, fmt="{:.3f}"):
    try:
        if x is None or np.isnan(x):
            return "–"
    except TypeError:
        pass
    return fmt.format(x)


def write_tables(res, fun, val):
    L = ["### Results — all 24 tests (net of costs; primary metric = expectancy in R; p = one-sided t-test on net R)\n",
         "| # | Test | n | % days | IS/OOS n | Long % | Win% | BE win% | Avg win R | Avg loss R | Exp R | Exp R 0-cost | Exp $ | "
         "Avg win $ | Avg loss $ | PF | Max DD $ | Loss streak | p raw | p Holm | p BH | 95% CI (R) | MDE R | Exp R IS | Exp R OOS | "
         "Blocks 1/2/3 | Yrs + | Null pct | Mirror R | Verdict |",
         "|" + "---|" * 30]
    for _, r in res.iterrows():
        L.append(
            f"| {r.test_id} | {r.label} | {int(r.n)} | {_f(100 * r.pct_days_traded, '{:.0f}')}% | {int(r.n_is)}/{int(r.n_oos)} | "
            f"{_f(100 * r.long_share, '{:.0f}')} | {_f(100 * r.win_rate, '{:.1f}')} | {_f(100 * r.be_win_rate, '{:.1f}')} | "
            f"{_f(r.avg_win_R, '{:.2f}')} | {_f(r.avg_loss_R, '{:.2f}')} | {_f(r.exp_R)} | {_f(r.exp_R_zero_cost)} | "
            f"{_f(r.exp_usd, '{:.2f}')} | {_f(r.avg_win_usd, '{:.2f}')} | {_f(r.avg_loss_usd, '{:.2f}')} | {_f(r.pf, '{:.2f}')} | "
            f"{_f(r.max_dd_usd, '{:.0f}')} | {int(r.loss_streak)} | {_f(r.p_raw)} | {_f(r.p_holm)} | {_f(r.p_bh)} | "
            f"[{_f(r.ci_lo)}, {_f(r.ci_hi)}] | {_f(r.mde_R)} | {_f(r.exp_R_is)} | {_f(r.exp_R_oos)} | "
            f"{_f(r.block1_R, '{:.2f}')}/{_f(r.block2_R, '{:.2f}')}/{_f(r.block3_R, '{:.2f}')} | {int(r.years_positive)}/{int(r.years_traded)} | "
            f"{_f(r.null_pctile, '{:.1f}')} | {_f(r.mirror_R)} | {r.verdict} |")
    L += ["\n### Drift baseline (reference only): always-long / always-short entries at 08:35 CT, the test's dates and R, same exits\n",
          "| # | Test | Real exp R | Always-long R | Always-short R |", "|---|---|---|---|---|"]
    for _, r in res.iterrows():
        L.append(f"| {r.test_id} | {r.label} | {_f(r.exp_R)} | {_f(r.drift_long_R)} | {_f(r.drift_short_R)} |")
    L += ["\n### Risk size and Monte Carlo ($; 2000 orderings, fresh account)\n",
          "Warning: risk per trade varies with OR width, so the $ drawdown probabilities mix very different trade sizes.\n",
          "| # | Test | Median R (pts) | Share R > 30 pts | Fits $50 risk (R ≤ 25) | Fits $62 risk (R ≤ 31) | P(DD > $292 in 50) | P(DD > $500 in 100) |",
          "|---|---|---|---|---|---|---|---|"]
    for _, r in res.iterrows():
        L.append(f"| {r.test_id} | {r.label} | {_f(r.median_R_pts, '{:.1f}')} | {_f(100 * r.share_R_gt30, '{:.0f}')}% | "
                 f"{_f(100 * r.fit_50, '{:.0f}')}% | {_f(100 * r.fit_62, '{:.0f}')}% | {_f(100 * r.p_dd292_50, '{:.1f}')}% | "
                 f"{_f(100 * r.p_dd500_100, '{:.1f}')}% |")
    cols = ["candidate_days", "missing_or_bars", "conflict", "eligible", "no_filter_direction", "skip_R<8", "no_trigger", "filled", "roll_excluded"]
    L += ["\n### Funnel and skip counts\n", "| # | Test | " + " | ".join(cols) + " |", "|" + "---|" * (len(cols) + 2)]
    for _, r in fun.iterrows():
        L.append(f"| {r.test_id} | {r.label} | " + " | ".join(str(int(r[c])) for c in cols) + " |")
    L += ["\n### Validation\n"] + [f"- {k}: {v}" for k, v in val.items()]
    open(os.path.join(HERE, "results_tables_orb.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
