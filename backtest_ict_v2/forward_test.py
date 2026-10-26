"""Forward test of the frozen ICT v2 rules on data AFTER 2026-10-23 (PREREGISTRATION.md §11).

1. Verifies the pre-registration hash (refuses to run if it changed).
2. Loads the original raw history (backtest_ict/data/raw/*.dbn.zst) plus every new raw Databento
   MNQ.FUT ohlcv-1m DBN file in ./data_forward (repository root) or backtest_ict_v2/data_forward.
3. Rebuilds the back-adjusted 1m series with the SAME roll rule as backtest_ict/build_data.py
   (history is needed so levels, swings, ATR and EMAs warm up).
4. Runs the 32 pre-registered tests unchanged and keeps only trades filled after 2026-10-23 (CT date).
5. Prints the same per-test metrics (R and $), the random-direction null percentile, the mirror,
   and Holm/BH-corrected p-values across the 32 tests.

No download happens here. See README_ict_v2.md ("Forward test") and fetch_forward.py.
Usage:  python3 backtest_ict_v2/forward_test.py
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "backtest_ict"))
import build_data as BD  # noqa: E402  (roll rule helpers)
import run_v2 as RV      # noqa: E402
import core_v2 as V2     # noqa: E402

C = V2.C
FORWARD_START = pd.Timestamp("2026-10-24", tz=C.TZ)       # first CT date after the frozen history


def load_raw(paths):
    import databento as db
    frames = []
    for p in paths:
        df = db.DBNStore.from_file(p).to_df(price_type="float", pretty_ts=True, map_symbols=True)
        frames.append(df[["open", "high", "low", "close", "volume", "symbol"]])
    raw = pd.concat(frames)
    raw = raw[~raw["symbol"].str.contains("-")]
    raw.index = pd.DatetimeIndex(raw.index).as_unit("ns")
    assert str(raw.index.dtype) == "datetime64[ns, UTC]"
    raw = raw.reset_index().drop_duplicates(subset=["ts_event", "symbol"], keep="last").set_index("ts_event").sort_index()
    return raw


def build_adjusted(raw):
    """Same volume-based roll rule and additive back-adjustment as backtest_ict/build_data.py."""
    raw = raw.copy()
    raw["sdate"] = BD.session_date(raw.index)
    vol = raw.groupby(["sdate", "symbol"])["volume"].sum().unstack(fill_value=0)
    chosen, current = {}, None
    for i, d in enumerate(vol.index):
        if i == 0:
            current = vol.iloc[0].idxmax()
        else:
            leader = vol.iloc[i - 1].idxmax()
            if BD.expiry_key(leader) > BD.expiry_key(current):
                current = leader
        chosen[d] = current
    chosen = pd.Series(chosen)
    front = raw[raw["symbol"].values == chosen.reindex(raw["sdate"]).values].copy()
    rolls, adj = [], np.zeros(len(front))
    for i in range(1, len(vol.index)):
        dp, d = vol.index[i - 1], vol.index[i]
        if chosen[dp] == chosen[d]:
            continue
        prev = raw[raw["sdate"] == dp]
        a = prev[prev["symbol"] == chosen[dp]]["close"]
        b = prev[prev["symbol"] == chosen[d]]["close"]
        common = a.index.intersection(b.index)
        assert len(common), f"no common bar for roll on {dp}"
        t_ref = common.max()
        t_roll = front[front["sdate"] == d].index.min()
        adj[front.index < t_roll] += b[t_ref] - a[t_ref]
        rolls.append(t_roll)
    for col in ("open", "high", "low", "close"):
        front[col] = (front[col] + adj).round(2)
    out = front.drop(columns=["sdate", "symbol"])
    out.index.name = "ts"
    return out, pd.DatetimeIndex(rolls).as_unit("ns").asi8


def main():
    RV.verify_prereg()
    hist = sorted(glob.glob(os.path.join(ROOT, "backtest_ict", "data", "raw", "*.dbn.zst")))
    new = sorted(glob.glob(os.path.join(ROOT, "data_forward", "*.dbn*")) + glob.glob(os.path.join(HERE, "data_forward", "*.dbn*")))
    if not hist:
        sys.exit("historical raw file missing (backtest_ict/data/raw); it is needed for warm-up")
    if not new:
        sys.exit("no new DBN files found in ./data_forward; nothing to test")
    df1m, rolls = build_adjusted(load_raw(hist + new))
    last = df1m.index.max()
    print(f"combined data to {last}; forward period starts {FORWARD_START.date()} CT")
    if last.tz_convert(C.TZ) < FORWARD_START:
        sys.exit("no data after 2026-10-23 in the supplied files")
    F = C.Features(df1m)
    _, _, setups = RV.build_all(F, V2.TESTED_WINDOWS)
    tests = RV.test_list()
    runs, funnels = RV.run_all(F, tests, setups, rolls)
    rows = []
    for t in tests:
        tr = [x for x in runs[t["test_id"]] if pd.Timestamp(x["t_fill"], tz="UTC").tz_convert(C.TZ) >= FORWARD_START]
        rng = np.random.default_rng(RV.BASE_SEED + 1000 * t["test_id"])
        row = dict(test_id=t["test_id"], label=t["label"])
        row.update(RV.summarize(tr, rng))
        if tr:
            nul = V2.random_direction_null(F, t["win"], tr, t["model"], RV.N_NULL, rng)
            row["null_pctile"] = float((nul < row["exp_R"]).mean() * 100)
            row["mirror_R"] = float(V2.mirror(F, tr).mean())
        rows.append(row)
    res = pd.DataFrame(rows)
    res["p_raw"] = res.get("p_raw", pd.Series(dtype=float)).fillna(1.0)
    res["p_holm"], res["p_bh"] = RV.holm(res["p_raw"]), RV.bh(res["p_raw"])
    cols = [c for c in ["test_id", "label", "n", "win_rate", "be_win_rate", "exp_R", "exp_R_zero_cost", "exp_usd", "pf",
                        "max_dd_usd", "loss_streak", "p_raw", "p_holm", "p_bh", "ci_lo", "ci_hi", "mde_R", "null_pctile",
                        "mirror_R"] if c in res.columns]
    pd.set_option("display.width", 250)
    print(res[cols].round(3).to_string(index=False))
    out = os.path.join(HERE, f"forward_results_{last.tz_convert(C.TZ).date()}.csv")
    res.to_csv(out, index=False)
    print("saved", out)
    print("Reminder: a forward 'candidate' needs a positive expectancy after costs, enough trades (n >= 200 for the "
          "pre-registered bar), and a corrected p < 0.10. A few months of data will usually be underpowered.")


if __name__ == "__main__":
    main()
