# RUN_LOG: MNQ SMT + OB

One line per run (spec: date, spec commit hash, split, test, trade count, mean R, CI, verdict).

| Date | Spec commit | Split | Test | Trades | Mean R | 95% CI | Verdict |
|---|---|---|---|---|---|---|---|
| 2026-11-07 | `53f15d5` (spec + clarifications), calendar `b1ce21c` | train | A0 / A / B | 58 / 28 / 59 | not computed | not computed | **v1 halted: infeasible by trade count, no P&L computed.** |
| 2026-11-07 | `53f15d5` (spec + clarifications), calendar `b1ce21c` | validation | A0 / A / B | 13 / 7 / 21 | not computed | not computed | **v1 halted: infeasible by trade count, no P&L computed.** |
| 2026-11-07 | `53f15d5` (spec + clarifications), calendar `b1ce21c` | holdout | A0 / A / B | 0 / 0 / 1 | not computed | not computed | **v1 halted: infeasible by trade count, no P&L computed.** Holdout not opened for results. |

## Notes on the halt

- **Counts only.** The counts above come from a pass that applied the frozen v1 rules and reported trade counts (clarification #25). No P&L, win rate, expectancy or R-multiple outcome was computed, printed or viewed for any split. Train and validation remain unseen; the holdout was never opened for results.
- **Reason.** Criterion 1 requires at least 250 trades per split. Every test falls far short in every split.
  - The 8–40 pt R filter rejects most signals: the median signal R rose from 31 pts (2019) to 102 (2022) and 133 (2026), and 0 of 55 signals fit in 2026.
  - Even with no R filter, there are only 149 SMT signals in train and 60 in validation, both below 250.
- **Decision.** The spec owner decided on 2026-11-07 not to run v1. Any follow-up becomes a new spec (v2).
- **Reproducibility.** The data, calendar and engine used for the counts are committed:
  - `build_smt_data.py`, `smt_core.py`, `calendar_skip_days.csv` (hash in `CALENDAR.sha256`), `data/rolls_smt.csv`.
  - MES data: Databento GLBX.MDP3 ohlcv-1m, MES.FUT, 2019-05-01 → 2026-10-24, quoted at $13.90 before download.
