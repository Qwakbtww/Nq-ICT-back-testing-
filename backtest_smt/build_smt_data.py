"""Raw (unadjusted) front-month 1m series for MNQ and MES, on MNQ's roll schedule (clarifications #5, #7).

Roll rule (same as backtest_ict/build_data.py): session date = CT date of (timestamp + 7h); the MNQ contract
for session D is the outright with the highest volume in session D-1, never moving back to an earlier expiry.
MES uses the same contract month (MNQZ9 -> MESZ9). No back-adjustment.

Outputs (data/, git-ignored except the roll list):
  mnq_1m_raw.parquet, mes_1m_raw.parquet   ts (UTC ns), open, high, low, close, volume, contract
  rolls_smt.csv                            session date of the first session on each new contract
"""
import os
import sys

import numpy as np
import pandas as pd
import databento as db

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "backtest_ict"))
import build_data as BD  # noqa: E402  (expiry_key, session_date)
from smt_common import verify_freeze  # noqa: E402

RAW_MNQ = os.path.join(ROOT, "backtest_ict", "data", "raw", "MNQ_FUT_ohlcv1m_2019-05-01_2026-10-24.dbn.zst")
RAW_MES = os.path.join(HERE, "data", "raw", "MES_FUT_ohlcv1m_2019-05-01_2026-10-24.dbn.zst")


def load_outrights(path):
    raw = db.DBNStore.from_file(path).to_df(price_type="float", pretty_ts=True, map_symbols=True)
    raw = raw[~raw["symbol"].str.contains("-")][["open", "high", "low", "close", "volume", "symbol"]].copy()
    raw.index = pd.DatetimeIndex(raw.index).as_unit("ns")
    assert str(raw.index.dtype) == "datetime64[ns, UTC]"
    raw["sdate"] = BD.session_date(raw.index)
    return raw


def main():
    verify_freeze()
    mnq, mes = load_outrights(RAW_MNQ), load_outrights(RAW_MES)
    vol = mnq.groupby(["sdate", "symbol"])["volume"].sum().unstack(fill_value=0)
    chosen, cur = {}, None
    for i, d in enumerate(vol.index):
        if i == 0:
            cur = vol.iloc[0].idxmax()
        else:
            lead = vol.iloc[i - 1].idxmax()
            if BD.expiry_key(lead) > BD.expiry_key(cur):
                cur = lead
        chosen[d] = cur
    chosen = pd.Series(chosen)
    out = {}
    for name, raw, prefix in (("mnq", mnq, "MNQ"), ("mes", mes, "MES")):
        want = chosen.reindex(raw["sdate"]).str.replace("MNQ", prefix, regex=False).values
        f = raw[raw["symbol"].values == want].drop(columns=["sdate"]).rename(columns={"symbol": "contract"})
        f.index.name = "ts"
        assert f.index.is_unique and f.index.is_monotonic_increasing
        f.to_parquet(os.path.join(HERE, "data", f"{name}_1m_raw.parquet"))
        out[name] = f
        print(f"{name}: {len(f):,} front-month 1m bars, {f['contract'].nunique()} contracts")
    rolls = [d for i, d in enumerate(chosen.index[1:], 1) if chosen.iloc[i] != chosen.iloc[i - 1]]
    pd.DataFrame({"roll_session_date": [pd.Timestamp(d).date() for d in rolls],
                  "old": [chosen[chosen.index[chosen.index.get_loc(d) - 1]] for d in rolls],
                  "new": [chosen[d] for d in rolls]}).to_csv(os.path.join(HERE, "data", "rolls_smt.csv"), index=False)
    print(f"rolls: {len(rolls)}")
    # MES must have bars for the chosen month in every session where MNQ has bars
    s_mnq = set(BD.session_date(out["mnq"].index).unique())
    s_mes = set(BD.session_date(out["mes"].index).unique())
    print(f"sessions: MNQ {len(s_mnq)}, MES {len(s_mes)}, MNQ-only {len(s_mnq - s_mes)}")


if __name__ == "__main__":
    main()
