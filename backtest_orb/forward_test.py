"""Forward test of the frozen ORB rules on data AFTER 2026-10-23 (PREREGISTRATION.md §10).

1. Verifies the ORB pre-registration hash (refuses to run if it changed).
2. Loads the original raw history plus every new raw Databento MNQ.FUT ohlcv-1m DBN file in
   ./data_forward (repository root) or backtest_orb/data_forward.
3. Rebuilds the back-adjusted series with the same roll rule (backtest_ict_v2/forward_test.py,
   verified to reproduce the frozen history exactly); history provides the EMA(200) warm-up.
4. Runs the 24 pre-registered tests unchanged and scores only trades on dates after 2026-10-23.
5. Prints the same per-test metrics, the drift-matched null percentile, the mirror and Holm/BH p-values.

Nothing is downloaded here. Fetch new data with the cost-checked, capped fetcher:
    DATABENTO_KEY_FILE=/path/to/key python3 backtest_ict_v2/fetch_forward.py 2026-10-24 <end>            # quote only
    DATABENTO_KEY_FILE=/path/to/key python3 backtest_ict_v2/fetch_forward.py 2026-10-24 <end> --confirm --cap 3.00
Usage:  python3 backtest_orb/forward_test.py
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
import orb_core as O                                        # noqa: E402  (adds the earlier study paths)
import run_orb as RO                                        # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "backtest_ict_v2"))
import forward_test as FV2                                  # noqa: E402  (load_raw, build_adjusted)

C = O.C
FORWARD_START = np.datetime64("2026-10-24")


def main():
    RO.verify_prereg()
    hist = sorted(glob.glob(os.path.join(ROOT, "backtest_ict", "data", "raw", "*.dbn.zst")))
    new = sorted(glob.glob(os.path.join(ROOT, "data_forward", "*.dbn*")) + glob.glob(os.path.join(HERE, "data_forward", "*.dbn*")))
    if not hist:
        sys.exit("historical raw file missing (backtest_ict/data/raw); it is needed for the EMA warm-up")
    if not new:
        sys.exit("no new DBN files found in ./data_forward; nothing to test")
    df1m, rolls = FV2.build_adjusted(FV2.load_raw(hist + new))
    print(f"combined data to {df1m.index.max()}")
    M = O.Market(df1m)
    infos, runs, funnels = O.run_all(M, rolls)
    rows = []
    for t in O.tests():
        tr = [x for x in runs[t["test_id"]] if np.datetime64(x["date"], "D") >= FORWARD_START]
        rng = np.random.default_rng(RO.BASE_SEED + 1000 * t["test_id"])
        row = dict(test_id=t["test_id"], label=t["label"])
        row.update(RO.RV.summarize(tr, rng))
        if tr:
            nul = O.drift_null(M, infos, tr, RO.N_NULL, rng)
            row["null_pctile"] = float((nul < row["exp_R"]).mean() * 100)
            row["mirror_R"] = float(O.mirror(M, tr).mean())
        rows.append(row)
    res = pd.DataFrame(rows)
    if "p_raw" not in res:
        sys.exit("no forward trades yet")
    res["p_raw"] = res["p_raw"].fillna(1.0)
    res["p_holm"], res["p_bh"] = RO.RV.holm(res["p_raw"]), RO.RV.bh(res["p_raw"])
    cols = [c for c in ["test_id", "label", "n", "win_rate", "exp_R", "exp_R_zero_cost", "exp_usd", "pf", "max_dd_usd",
                        "p_raw", "p_holm", "p_bh", "ci_lo", "ci_hi", "mde_R", "null_pctile", "mirror_R"] if c in res]
    pd.set_option("display.width", 250)
    print(res[cols].round(3).to_string(index=False))
    out = os.path.join(HERE, f"forward_results_{df1m.index.max().tz_convert(C.TZ).date()}.csv")
    res.to_csv(out, index=False)
    print("saved", out)
    print("Reminder: about 60 trading days per quarter, so expect at most ~60 trades per test per quarter; "
          "the pre-registered bar is n >= 200 and Holm p < 0.10.")


if __name__ == "__main__":
    main()
