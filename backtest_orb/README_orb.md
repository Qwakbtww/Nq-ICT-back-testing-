# Opening Range Breakout on MNQ: a pre-registered test (Study 4)

## Honesty clause

ORB is a standard, widely known idea, specified here before looking at any ORB result. But this is the 4th study on the same 2019-2026 history (~100+ tests so far across studies), so the effective multiple-testing burden is larger than this study's own 24 tests. Any positive result is a lead, not proof; the forward test is the only real confirmation. A negative result does not rule out discretionary skill.

(The analyst had seen the results of the three earlier ICT studies, but no ORB result, before `PREREGISTRATION.md` was frozen and pushed: commit `e1d2cd7`, SHA-256 `19ae71c7…ee63f06`.)

## Verdict

**A lead, not proof.** Unlike the three ICT studies, this one did **not** come back empty.

**6 of the 24 pre-registered tests meet every "candidate edge" criterion:**
- positive after costs in both IS and OOS;
- ≥ 200 trades (here 1,485–1,902);
- positive in at least 4 calendar years (here 7–8 of 8);
- above the 95th percentile of the drift-matched null (here the 100th);
- better than the mirror;
- Holm p < 0.10.

**Multiplicity:** 12 of 24 raw p-values are below 0.05, against about 1.2 expected by chance.

**All six candidates are one family: the S1 stop (the opposite OR extreme) with a 15- or 30-minute opening range.** They overlap heavily (same days, mostly the same trades), so count them as **one finding, not six**.

| # | Test | n | Exp R (net) | 95% CI (R) | Exp $ | p raw | p Holm | IS / OOS (R) | Years + | Mirror R |
|---|---|---|---|---|---|---|---|---|---|---|
| 18 | N30-S1-E1-F1 | 1485 | **+0.101** | [+0.049, +0.154] | +$18.85 | 0.0001 | 0.002 | +0.110 / +0.080 | 8/8 | −0.100 |
| 20 | N30-S1-E2-F1 | 1485 | **+0.110** | [+0.054, +0.168] | +$21.11 | 0.0001 | 0.002 | +0.126 / +0.072 | 7/8 | −0.096 |
| 12 | N15-S1-E2-F1 | 1573 | +0.107 | [+0.040, +0.175] | +$17.07 | 0.0012 | 0.027 | +0.105 / +0.112 | 7/8 | −0.053 |
| 10 | N15-S1-E1-F1 | 1573 | +0.091 | [+0.031, +0.151] | +$13.83 | 0.0017 | 0.036 | +0.087 / +0.100 | 8/8 | −0.082 |
| 19 | N30-S1-E2-F0 | 1902 | +0.075 | [+0.024, +0.127] | +$13.30 | 0.0026 | 0.052 | +0.078 / +0.066 | 7/8 | −0.048 |
| 17 | N30-S1-E1-F0 | 1902 | +0.066 | [+0.019, +0.115] | +$10.79 | 0.0031 | 0.059 | +0.074 / +0.048 | 7/8 | −0.057 |

### Why this is still only a lead

1. **Multiplicity across studies.** About 96+ tests have now been run on this same history. A crude Bonferroni correction at α = 0.10 over 96–150 tests needs p < 0.0007–0.001. **Only tests 18 and 20 (p ≈ 0.0001) pass that stricter bar.** The other four do not.
2. **A small edge in a fat right tail.**
   - The edge is about +0.07 to +0.11R per trade, and the median trade is ≤ 0R.
   - Removing the best 5% of trades turns every candidate's mean to about 0 or negative. Removing the best 1% leaves +0.03 to +0.08R.
   - This is the typical profile of a breakout or trend strategy. It means missing a handful of big trend days in live trading would erase the result.
3. **The risk per trade is far beyond a small account.**
   - The S1 stop sits at the opposite OR extreme. The median R is 73–75 pts for N15 and 94–97 pts for N30, which is about $146–194 of risk on 1 MNQ.
   - It keeps growing with price: the median N30-S1 R was 36 pts in 2019 and 180 pts in 2026.
   - **Only 3–8% of candidate trades fit a $50–62 risk budget** (R ≤ 25–31 pts).
   - On that small subset (58–111 trades) the result is flat to negative: +0.06R, −0.02R and −0.18R for tests 18, 20 and 12.
   - In the Monte Carlo, the probability of a drawdown over $292 within 50 trades is **100%** for every S1 test.
   - **As specified, this cannot be traded within a $50–62-per-trade risk budget on 1 MNQ.**
4. **Execution realism.**
   - Fills assume only 1 tick of slippage on the stop entry, and that 1m bars capture the intrabar path.
   - Because R is large (about 95 pts), each extra tick of slippage costs only about 0.003R per trade, so costs are not the main risk.
   - The bigger risk is the pre-registered assumption that breakout fills occur at the trigger + 1 tick.
5. **Same data, 4th study.** As the honesty clause says, only the forward test can confirm it.

### The other 18 tests

- **S2 (midpoint stop):** ≈ 0 to negative with a 2R target (E1). For example, N5-S2-E1 is −0.10R with a CI entirely below zero. It is weakly positive without a target (E2), but never significant after correction.
- **N5 with the S1 stop and no target (E2):** +0.08R with raw p = 0.04, but Holm p = 0.52–0.57 and the CI includes 0.
- **N5 with the S1 stop and a 2R target (E1):** about 0.

So the positive family needs **a wide stop and a longer opening range**. With a tight stop or the 5-minute range, the edge disappears.

**Scope:** this tests **one rigid, mechanical ORB**. A negative result elsewhere does not rule out discretionary skill, and these positive results are a lead for the forward test, not proof.

## Data and how to run

- **Data:** the back-adjusted MNQ 1m series and roll log from `backtest_ict/data/`, reused.
  - Databento GLBX.MDP3 ohlcv-1m, MNQ.FUT, 2019-05-05 → 2026-10-23.
  - 30 volume-based rolls at the 17:00 CT open; additive back-adjustment.
  - No API call or credit was used.
- **Code reuse:** the data layer and the validated 1m exit simulator from `backtest_ict/ict_core.py`, plus tick helpers and the vectorised exit engine from `backtest_ict_v2/core_v2.py`.
- **Time handling:** explicit ns timestamps; America/Chicago with DST; nothing held through the halt.
- **Roll exclusions:** 0, because rolls happen at 17:00 and RTH trades end by 14:55.
- **IS/OOS cutoff:** 2024-07-27 11:42 UTC (70% of the calendar span).
- **Days:**
  - 1,929 candidate days (with an 08:30 CT 1m bar).
  - Missing OR bars: 2 / 3 / 4 days for N = 5 / 15 / 30.
  - Both-side conflicts: 4 / 1 / 1 days.

```bash
python3 backtest_orb/run_orb.py        # verifies the PREREGISTRATION hash, validates, then runs (~40 min; the null is the slow part)
```

The first full run was stopped by the session's 30-minute background time limit at test 18 of 24, after validation had passed. It was rerun unchanged with a longer limit. All seeds are fixed, so the run is deterministic. No code or parameter changed between the two runs.

## Definitions (binding text: [PREREGISTRATION.md](PREREGISTRATION.md))

- **Opening range:** 1m bars in [08:30, 08:30 + N) CT, N ∈ {5, 15, 30}. All N bars must exist.
- **Trigger window:** from the OR end to 14:00:00 CT. Bars opening at or after 14:00 can't trigger. One trade per day, no re-entry, and the two orders cancel each other (OCO).
- **Entry:**
  - Stop order at OR high + 1 tick (long) or OR low − 1 tick (short).
  - It triggers when a 1m bar trades at least 1 tick through that level.
  - Fill = the trigger (or the bar open, if price gapped through) + 1 tick adverse.
- **Both-sides conflict:** if the first triggering bar triggers both sides, the day is skipped for every variant of that N, before any entry simulation.
- **Stops:**
  - S1 = the opposite OR extreme.
  - S2 = the OR midpoint, rounded outward.
  - Stops are hit on touch and fill with 1 tick of slippage (at the bar open if price gapped past).
  - Planned R < 8 pts → that side's order isn't placed.
- **Exits:**
  - E1 = 2R limit target (needs 1 tick through).
  - E2 = no target.
  - Both are flat at the last 1m bar before 14:55 CT (1 tick slippage).
  - If stop and target are both reachable in one 1m bar, the stop counts first. In the fill bar only the stop is checked.
- **Filter:**
  - F0 = none.
  - F1 = 5m EMA(200) on real bars (no synthetic bars), locked at the close of the last OR 5m bar. Close above the EMA → long order only; below → short only.
- **Costs:** $2 per point and $1 round-trip commission; zero-cost results are also reported. Every price is on the 0.25 tick grid (asserted for every trade).

### Interpretation log (from the pre-registration)

| # | Ambiguity | Chosen definition |
|---|---|---|
| 1 | "Fills when a 1m bar trades ≥ 1 tick through" | Through the trigger level: high ≥ T_long + 1 tick (low ≤ T_short − 1 tick). |
| 2 | Fill price | max(T_long, open) + 1 tick (short: min(T_short, open) − 1 tick). |
| 3 | Scope of the both-sides conflict | Day-level per N: if the first bar triggering either side triggers both, skip all 8 variants of that N that day. |
| 4 | Conflict test with F1 (one order) | Same day-level flag; F1 skips the same conflict days. |
| 5 | F1 order placement | Only the allowed side's order; it may trigger after the other side was touched. |
| 6 | EMA equality | No trade. |
| 7 | EMA warm-up | The first 200 5m bars of the series. |
| 8 | R < 8 check timing | At order placement, with the planned fill (trigger ± 1 tick); actual R used for P&L. |
| 9 | S1 stop placement | Exactly at the opposite OR extreme; hit on touch. |
| 10 | Time-exit slippage | 1 tick, consistent with the earlier studies. |
| 11 | Complete OR | All N 1m bars present. |
| 12 | Holiday / early-close sessions | Traded if the OR is complete; orders expire at the last bar before 14:00; time exit at the last bar before 14:55 in the session. |
| 13 | Null "same dates" | Each null trade uses a real trade's date (one-to-one) and its R. |
| 14 | Null entry price | Bar open + 1 tick adverse. |
| 15 | Null direction proportions | Long probability = the long share of the real trades in that calendar year, for that test. |
| 16 | Drift baseline R and dates | The test's traded dates and their real R; entry at the 08:35 1m open + 1 tick. |
| 17 | Gap size | 08:30 open − last close of the previous RTH session (last 1m bar before 15:00 CT). |
| 18 | OR width normaliser | ATR(14) Wilder on 5m at the close of the last OR 5m bar. |
| 19 | Risk-budget fraction | R × $2 ≤ $50 and ≤ $62 (excluding commission and slippage). |
| 20 | Calendar year for "positive years" | CT year of the fill; net R sum > 0. |

## Validation (passed before any P&L was computed or printed)

No smoke run printed P&L, win rate or expectancy; smoke runs printed counts only.

| Check | Result |
|---|---|
| Independent brute-force 1m simulator vs. main engine, 500 random trades: direction, fill bar and price, stop, R, exit bar and price, reason, net $, OR levels | **0 mismatches** |
| Mutation test: every exit price shifted by 1 tick | **500 / 500 detected** |
| Look-ahead assertions on all 41,548 trades: no trade on a conflict or skipped day; OR known before the fill; EMA locked at the OR's last 5m close; fill < 14:00; exit < 14:55 and in the same session; every price on the tick grid; R ≥ 8 | Pass |
| Hand-coded rule re-verification: 100 random (day, N) cases plus every conflict / missing-OR day (115 in all), each across all 8 variants, from raw 1m data with independent code (OR, independent 5m resample + EMA, conflict, trigger, fill, stop, R filter, filter decision, target, exit) | Pass. Corrupting the OR high, the EMA or the day status was caught 15/15 for each. |
| Truncation test, 20 days: OR / EMA / filter from data cut at the OR end; trigger and fill from data cut at the fill bar | 20 / 20 identical |
| Vectorised null engine vs. `simulate_exit`, 3,000 draws, including E2 (no target) and entry slippage | 0 mismatches |
| Faithfulness charts: 30 random trading days (`charts_check/`) | **Reviewed (days 01, 05, 25 checked number by number): all match the definitions.** OR box, triggers at ±1 tick, entry 1 tick beyond the trigger, S1 at the opposite extreme, S2 midpoint rounded outward (e.g. 22488.375 → 22488.50 for a short), R, 2R target, F1 direction vs. the EMA, and exits all checked. |

## Results: every test

All metrics are net of costs, with expectancy in R as the primary metric.

- **p-values:** one-sided t-test on net R. Holm–Bonferroni and Benjamini–Hochberg are both applied across all 24. Expected false positives at p < 0.05: **1.2**; observed raw p < 0.05: **12**.
- **% days:** trades / eligible days.
- **Null pct:** the real mean's percentile in the drift-matched random-timing null, which uses random entry minutes on the same dates, yearly long/short proportions matched to the real trades, and the real R.
- **Mirror R:** the same fills traded in the opposite direction.

#### Results — all 24 tests (net of costs; primary metric = expectancy in R; p = one-sided t-test on net R)

| # | Test | n | % days | IS/OOS n | Long % | Win% | BE win% | Avg win R | Avg loss R | Exp R | Exp R 0-cost | Exp $ | Avg win $ | Avg loss $ | PF | Max DD $ | Loss streak | p raw | p Holm | p BH | 95% CI (R) | MDE R | Exp R IS | Exp R OOS | Blocks 1/2/3 | Yrs + | Null pct | Mirror R | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | N5-S1-E1-F0 | 1911 | 99% | 1333/578 | 50 | 35.7 | 35.9 | 1.79 | -1.00 | -0.004 | 0.018 | -2.57 | 194.05 | -111.92 | 0.96 | 9705 | 13 | 0.552 | 1.000 | 0.692 | [-0.064, 0.060] | 0.078 | -0.020 | 0.032 | -0.02/-0.03/0.04 | 5/8 | 68.5 | -0.022 | no evidence of an edge (fails: IS/OOS,null,p_holm) |
| 2 | N5-S1-E1-F1 | 1674 | 87% | 1173/501 | 54 | 35.3 | 36.3 | 1.75 | -1.00 | -0.028 | -0.005 | -5.19 | 188.13 | -110.68 | 0.93 | 9831 | 12 | 0.800 | 1.000 | 0.873 | [-0.091, 0.036] | 0.082 | -0.041 | 0.003 | -0.04/-0.02/-0.02 | 3/8 | 34.7 | -0.031 | no evidence of an edge (fails: IS/OOS,years,null,p_holm) |
| 3 | N5-S1-E2-F0 | 1911 | 99% | 1333/578 | 50 | 29.8 | 27.6 | 2.61 | -0.99 | 0.081 | 0.105 | 7.51 | 282.77 | -109.49 | 1.10 | 5458 | 20 | 0.037 | 0.524 | 0.080 | [-0.007, 0.171] | 0.113 | 0.073 | 0.100 | 0.05/0.08/0.11 | 6/8 | 99.8 | 0.035 | no evidence of an edge (fails: p_holm) |
| 4 | N5-S1-E2-F1 | 1674 | 87% | 1173/501 | 54 | 30.3 | 28.0 | 2.56 | -0.99 | 0.082 | 0.106 | 6.15 | 271.28 | -109.03 | 1.08 | 3454 | 17 | 0.044 | 0.569 | 0.088 | [-0.009, 0.176] | 0.120 | 0.075 | 0.098 | 0.07/0.10/0.07 | 7/8 | 99.6 | 0.052 | no evidence of an edge (fails: p_holm) |
| 5 | N5-S2-E1-F0 | 1852 | 96% | 1275/577 | 50 | 31.2 | 34.4 | 1.97 | -1.03 | -0.095 | -0.055 | -4.55 | 116.09 | -59.28 | 0.89 | 8586 | 19 | 0.998 | 1.000 | 0.998 | [-0.161, -0.032] | 0.080 | -0.116 | -0.049 | -0.15/-0.06/-0.07 | 1/8 | 5.9 | 0.017 | no evidence of an edge (fails: IS/OOS,years,null,mirror,p_holm) |
| 6 | N5-S2-E1-F1 | 1623 | 84% | 1123/500 | 53 | 31.1 | 34.4 | 1.96 | -1.03 | -0.099 | -0.058 | -5.88 | 112.69 | -59.43 | 0.86 | 9623 | 21 | 0.998 | 1.000 | 0.998 | [-0.168, -0.032] | 0.086 | -0.121 | -0.049 | -0.13/-0.08/-0.08 | 1/8 | 4.2 | -0.014 | no evidence of an edge (fails: IS/OOS,years,null,mirror,p_holm) |
| 7 | N5-S2-E2-F0 | 1852 | 96% | 1275/577 | 50 | 16.2 | 15.9 | 5.45 | -1.03 | 0.020 | 0.064 | 0.07 | 305.09 | -58.89 | 1.00 | 5850 | 31 | 0.380 | 1.000 | 0.512 | [-0.105, 0.151] | 0.162 | 0.010 | 0.041 | 0.03/0.02/0.01 | 5/8 | 78.7 | -0.015 | no evidence of an edge (fails: null,p_holm) |
| 8 | N5-S2-E2-F1 | 1623 | 84% | 1123/500 | 53 | 16.3 | 16.0 | 5.40 | -1.03 | 0.021 | 0.065 | -1.84 | 291.05 | -59.00 | 0.96 | 6842 | 37 | 0.384 | 1.000 | 0.512 | [-0.115, 0.165] | 0.174 | 0.012 | 0.041 | 0.10/-0.04/0.01 | 5/8 | 74.5 | -0.022 | no evidence of an edge (fails: null,p_holm) |
| 9 | N15-S1-E1-F0 | 1920 | 100% | 1342/578 | 52 | 43.0 | 40.3 | 1.37 | -0.93 | 0.063 | 0.078 | 7.70 | 218.98 | -151.82 | 1.09 | 8422 | 10 | 0.013 | 0.242 | 0.046 | [0.006, 0.119] | 0.070 | 0.063 | 0.061 | 0.06/0.05/0.07 | 5/8 | 100.0 | -0.037 | no evidence of an edge (fails: p_holm) |
| 10 | N15-S1-E1-F1 | 1573 | 82% | 1099/474 | 55 | 44.4 | 40.4 | 1.34 | -0.91 | 0.091 | 0.106 | 13.83 | 216.89 | -148.58 | 1.17 | 6116 | 10 | 0.002 | 0.036 | 0.010 | [0.031, 0.151] | 0.077 | 0.087 | 0.100 | 0.08/0.10/0.09 | 8/8 | 100.0 | -0.082 | CANDIDATE EDGE (lead only; see honesty clause) |
| 11 | N15-S1-E2-F0 | 1920 | 100% | 1342/578 | 52 | 40.9 | 38.2 | 1.49 | -0.92 | 0.065 | 0.082 | 8.51 | 237.85 | -150.44 | 1.10 | 9205 | 10 | 0.023 | 0.398 | 0.070 | [-0.000, 0.130] | 0.082 | 0.075 | 0.041 | 0.05/0.10/0.04 | 5/8 | 99.7 | 0.005 | no evidence of an edge (fails: p_holm) |
| 12 | N15-S1-E2-F1 | 1573 | 82% | 1099/474 | 55 | 42.8 | 38.3 | 1.47 | -0.91 | 0.107 | 0.124 | 17.07 | 237.68 | -147.89 | 1.20 | 6850 | 15 | 0.001 | 0.027 | 0.010 | [0.040, 0.175] | 0.088 | 0.105 | 0.112 | 0.07/0.14/0.11 | 7/8 | 100.0 | -0.053 | CANDIDATE EDGE (lead only; see honesty clause) |
| 13 | N15-S2-E1-F0 | 1903 | 99% | 1325/578 | 52 | 34.7 | 34.9 | 1.89 | -1.02 | -0.006 | 0.023 | 0.02 | 160.82 | -85.56 | 1.00 | 4805 | 17 | 0.577 | 1.000 | 0.692 | [-0.070, 0.058] | 0.080 | -0.007 | -0.004 | 0.01/-0.02/-0.01 | 5/8 | 76.6 | -0.042 | no evidence of an edge (fails: IS/OOS,null,p_holm) |
| 14 | N15-S2-E1-F1 | 1559 | 81% | 1085/474 | 54 | 35.0 | 35.3 | 1.86 | -1.01 | -0.009 | 0.020 | 0.57 | 159.48 | -84.84 | 1.01 | 4873 | 13 | 0.605 | 1.000 | 0.692 | [-0.078, 0.060] | 0.088 | -0.030 | 0.038 | -0.03/-0.01/0.01 | 5/8 | 67.8 | -0.054 | no evidence of an edge (fails: IS/OOS,null,p_holm) |
| 15 | N15-S2-E2-F0 | 1903 | 99% | 1325/578 | 52 | 25.5 | 23.3 | 3.33 | -1.01 | 0.095 | 0.126 | 6.79 | 272.59 | -84.12 | 1.11 | 6032 | 21 | 0.034 | 0.524 | 0.080 | [-0.007, 0.197] | 0.129 | 0.115 | 0.048 | 0.13/0.12/0.04 | 5/8 | 99.5 | 0.009 | no evidence of an edge (fails: p_holm) |
| 16 | N15-S2-E2-F1 | 1559 | 81% | 1085/474 | 54 | 26.6 | 24.2 | 3.15 | -1.01 | 0.100 | 0.132 | 8.45 | 262.39 | -83.67 | 1.14 | 4246 | 18 | 0.033 | 0.524 | 0.080 | [-0.006, 0.207] | 0.135 | 0.100 | 0.101 | 0.11/0.12/0.07 | 6/8 | 99.4 | -0.060 | no evidence of an edge (fails: p_holm) |
| 17 | N30-S1-E1-F0 | 1902 | 99% | 1328/574 | 53 | 47.9 | 44.3 | 1.02 | -0.81 | 0.066 | 0.079 | 10.79 | 205.12 | -167.85 | 1.12 | 7940 | 11 | 0.003 | 0.059 | 0.012 | [0.019, 0.115] | 0.060 | 0.074 | 0.048 | 0.05/0.09/0.07 | 7/8 | 100.0 | -0.057 | CANDIDATE EDGE (lead only; see honesty clause) |
| 18 | N30-S1-E1-F1 | 1485 | 77% | 1036/449 | 56 | 49.9 | 44.3 | 1.00 | -0.80 | 0.101 | 0.113 | 18.85 | 205.56 | -167.10 | 1.23 | 5554 | 8 | 0.000 | 0.002 | 0.001 | [0.049, 0.154] | 0.067 | 0.110 | 0.080 | 0.09/0.11/0.10 | 8/8 | 100.0 | -0.100 | CANDIDATE EDGE (lead only; see honesty clause) |
| 19 | N30-S1-E2-F0 | 1902 | 99% | 1328/574 | 53 | 47.3 | 43.3 | 1.07 | -0.81 | 0.075 | 0.088 | 13.30 | 214.41 | -166.95 | 1.15 | 7798 | 11 | 0.003 | 0.052 | 0.012 | [0.024, 0.127] | 0.066 | 0.078 | 0.066 | 0.04/0.11/0.08 | 7/8 | 100.0 | -0.048 | CANDIDATE EDGE (lead only; see honesty clause) |
| 20 | N30-S1-E2-F1 | 1485 | 77% | 1036/449 | 56 | 49.3 | 43.3 | 1.04 | -0.80 | 0.110 | 0.123 | 21.11 | 213.93 | -166.33 | 1.25 | 5846 | 8 | 0.000 | 0.002 | 0.001 | [0.054, 0.168] | 0.073 | 0.126 | 0.072 | 0.09/0.14/0.10 | 7/8 | 100.0 | -0.096 | CANDIDATE EDGE (lead only; see honesty clause) |
| 21 | N30-S2-E1-F0 | 1893 | 98% | 1319/574 | 53 | 37.5 | 36.8 | 1.70 | -0.99 | 0.019 | 0.042 | 1.76 | 180.61 | -105.34 | 1.03 | 7540 | 11 | 0.274 | 1.000 | 0.411 | [-0.042, 0.079] | 0.077 | 0.028 | -0.003 | 0.02/0.05/-0.01 | 4/8 | 92.0 | -0.093 | no evidence of an edge (fails: IS/OOS,null,p_holm) |
| 22 | N30-S2-E1-F1 | 1479 | 77% | 1030/449 | 56 | 38.7 | 37.4 | 1.65 | -0.99 | 0.033 | 0.057 | 6.06 | 182.81 | -105.41 | 1.09 | 5148 | 13 | 0.170 | 1.000 | 0.272 | [-0.036, 0.104] | 0.087 | 0.031 | 0.038 | 0.03/0.03/0.04 | 5/8 | 96.0 | -0.136 | no evidence of an edge (fails: p_holm) |
| 23 | N30-S2-E2-F0 | 1893 | 98% | 1319/574 | 53 | 32.5 | 30.7 | 2.21 | -0.98 | 0.058 | 0.083 | 4.19 | 227.38 | -103.48 | 1.06 | 9100 | 13 | 0.083 | 0.912 | 0.142 | [-0.023, 0.140] | 0.104 | 0.084 | -0.001 | 0.04/0.13/0.01 | 5/8 | 97.6 | -0.085 | no evidence of an edge (fails: IS/OOS,p_holm) |
| 24 | N30-S2-E2-F1 | 1479 | 77% | 1030/449 | 56 | 34.0 | 31.9 | 2.09 | -0.98 | 0.064 | 0.089 | 8.48 | 226.20 | -103.72 | 1.12 | 5558 | 13 | 0.076 | 0.908 | 0.140 | [-0.022, 0.154] | 0.111 | 0.084 | 0.018 | 0.04/0.11/0.03 | 5/8 | 97.5 | -0.132 | no evidence of an edge (fails: p_holm) |

#### Drift baseline (reference only): always-long / always-short entries at 08:35 CT, the test's dates and R, same exits

| # | Test | Real exp R | Always-long R | Always-short R |
|---|---|---|---|---|
| 1 | N5-S1-E1-F0 | -0.004 | -0.035 | -0.037 |
| 2 | N5-S1-E1-F1 | -0.028 | -0.071 | -0.117 |
| 3 | N5-S1-E2-F0 | 0.081 | 0.055 | 0.003 |
| 4 | N5-S1-E2-F1 | 0.082 | -0.004 | -0.131 |
| 5 | N5-S2-E1-F0 | -0.095 | -0.041 | -0.019 |
| 6 | N5-S2-E1-F1 | -0.099 | -0.057 | -0.067 |
| 7 | N5-S2-E2-F0 | 0.020 | 0.071 | -0.035 |
| 8 | N5-S2-E2-F1 | 0.021 | -0.045 | -0.273 |
| 9 | N15-S1-E1-F0 | 0.063 | 0.039 | -0.025 |
| 10 | N15-S1-E1-F1 | 0.091 | 0.007 | -0.092 |
| 11 | N15-S1-E2-F0 | 0.065 | 0.071 | -0.019 |
| 12 | N15-S1-E2-F1 | 0.107 | 0.030 | -0.107 |
| 13 | N15-S2-E1-F0 | -0.006 | -0.084 | -0.111 |
| 14 | N15-S2-E1-F1 | -0.009 | -0.085 | -0.145 |
| 15 | N15-S2-E2-F0 | 0.095 | -0.013 | -0.096 |
| 16 | N15-S2-E2-F1 | 0.100 | -0.083 | -0.250 |
| 17 | N30-S1-E1-F0 | 0.066 | 0.046 | -0.026 |
| 18 | N30-S1-E1-F1 | 0.101 | 0.059 | -0.093 |
| 19 | N30-S1-E2-F0 | 0.075 | 0.051 | -0.015 |
| 20 | N30-S1-E2-F1 | 0.110 | 0.065 | -0.094 |
| 21 | N30-S2-E1-F0 | 0.019 | -0.083 | -0.130 |
| 22 | N30-S2-E1-F1 | 0.033 | -0.014 | -0.126 |
| 23 | N30-S2-E2-F0 | 0.058 | -0.020 | -0.116 |
| 24 | N30-S2-E2-F1 | 0.064 | 0.026 | -0.181 |

#### Risk size and Monte Carlo ($; 2000 orderings, fresh account)

Warning: risk per trade varies with OR width, so the $ drawdown probabilities mix very different trade sizes.

| # | Test | Median R (pts) | Share R > 30 pts | Fits $50 risk (R ≤ 25) | Fits $62 risk (R ≤ 31) | P(DD > $292 in 50) | P(DD > $500 in 100) |
|---|---|---|---|---|---|---|---|
| 1 | N5-S1-E1-F0 | 49.0 | 82% | 12% | 19% | 100.0% | 100.0% |
| 2 | N5-S1-E1-F1 | 49.0 | 82% | 12% | 19% | 100.0% | 100.0% |
| 3 | N5-S1-E2-F0 | 49.0 | 82% | 12% | 19% | 100.0% | 100.0% |
| 4 | N5-S1-E2-F1 | 49.0 | 82% | 12% | 19% | 100.0% | 100.0% |
| 5 | N5-S2-E1-F0 | 25.2 | 37% | 49% | 65% | 98.4% | 97.5% |
| 6 | N5-S2-E1-F1 | 25.2 | 37% | 49% | 65% | 98.5% | 98.2% |
| 7 | N5-S2-E2-F0 | 25.2 | 37% | 49% | 65% | 99.9% | 100.0% |
| 8 | N5-S2-E2-F1 | 25.2 | 37% | 49% | 65% | 100.0% | 99.9% |
| 9 | N15-S1-E1-F0 | 72.9 | 93% | 4% | 8% | 100.0% | 100.0% |
| 10 | N15-S1-E1-F1 | 74.5 | 93% | 4% | 8% | 100.0% | 100.0% |
| 11 | N15-S1-E2-F0 | 72.9 | 93% | 4% | 8% | 100.0% | 100.0% |
| 12 | N15-S1-E2-F1 | 74.5 | 93% | 4% | 8% | 100.0% | 100.0% |
| 13 | N15-S2-E1-F0 | 37.0 | 65% | 24% | 38% | 99.9% | 99.5% |
| 14 | N15-S2-E1-F1 | 37.8 | 66% | 23% | 37% | 99.9% | 99.5% |
| 15 | N15-S2-E2-F0 | 37.0 | 65% | 24% | 38% | 100.0% | 100.0% |
| 16 | N15-S2-E2-F1 | 37.8 | 66% | 23% | 37% | 100.0% | 99.9% |
| 17 | N30-S1-E1-F0 | 93.8 | 96% | 3% | 5% | 100.0% | 100.0% |
| 18 | N30-S1-E1-F1 | 96.8 | 96% | 3% | 4% | 100.0% | 100.0% |
| 19 | N30-S1-E2-F0 | 93.8 | 96% | 3% | 5% | 100.0% | 100.0% |
| 20 | N30-S1-E2-F1 | 96.8 | 96% | 3% | 4% | 100.0% | 100.0% |
| 21 | N30-S2-E1-F0 | 47.5 | 79% | 13% | 23% | 100.0% | 99.9% |
| 22 | N30-S2-E1-F1 | 48.8 | 80% | 13% | 22% | 100.0% | 99.8% |
| 23 | N30-S2-E2-F0 | 47.5 | 79% | 13% | 23% | 100.0% | 100.0% |
| 24 | N30-S2-E2-F1 | 48.8 | 80% | 13% | 22% | 100.0% | 100.0% |

#### Funnel and skip counts

| # | Test | candidate_days | missing_or_bars | conflict | eligible | no_filter_direction | skip_R<8 | no_trigger | filled | roll_excluded |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | N5-S1-E1-F0 | 1929 | 2 | 4 | 1923 | 0 | 12 | 0 | 1911 | 0 |
| 2 | N5-S1-E1-F1 | 1929 | 2 | 4 | 1923 | 1 | 12 | 236 | 1674 | 0 |
| 3 | N5-S1-E2-F0 | 1929 | 2 | 4 | 1923 | 0 | 12 | 0 | 1911 | 0 |
| 4 | N5-S1-E2-F1 | 1929 | 2 | 4 | 1923 | 1 | 12 | 236 | 1674 | 0 |
| 5 | N5-S2-E1-F0 | 1929 | 2 | 4 | 1923 | 0 | 71 | 0 | 1852 | 0 |
| 6 | N5-S2-E1-F1 | 1929 | 2 | 4 | 1923 | 1 | 71 | 228 | 1623 | 0 |
| 7 | N5-S2-E2-F0 | 1929 | 2 | 4 | 1923 | 0 | 71 | 0 | 1852 | 0 |
| 8 | N5-S2-E2-F1 | 1929 | 2 | 4 | 1923 | 1 | 71 | 228 | 1623 | 0 |
| 9 | N15-S1-E1-F0 | 1929 | 3 | 1 | 1925 | 0 | 5 | 0 | 1920 | 0 |
| 10 | N15-S1-E1-F1 | 1929 | 3 | 1 | 1925 | 1 | 5 | 346 | 1573 | 0 |
| 11 | N15-S1-E2-F0 | 1929 | 3 | 1 | 1925 | 0 | 5 | 0 | 1920 | 0 |
| 12 | N15-S1-E2-F1 | 1929 | 3 | 1 | 1925 | 1 | 5 | 346 | 1573 | 0 |
| 13 | N15-S2-E1-F0 | 1929 | 3 | 1 | 1925 | 0 | 22 | 0 | 1903 | 0 |
| 14 | N15-S2-E1-F1 | 1929 | 3 | 1 | 1925 | 1 | 22 | 343 | 1559 | 0 |
| 15 | N15-S2-E2-F0 | 1929 | 3 | 1 | 1925 | 0 | 22 | 0 | 1903 | 0 |
| 16 | N15-S2-E2-F1 | 1929 | 3 | 1 | 1925 | 1 | 22 | 343 | 1559 | 0 |
| 17 | N30-S1-E1-F0 | 1929 | 4 | 1 | 1924 | 0 | 2 | 20 | 1902 | 0 |
| 18 | N30-S1-E1-F1 | 1929 | 4 | 1 | 1924 | 1 | 2 | 436 | 1485 | 0 |
| 19 | N30-S1-E2-F0 | 1929 | 4 | 1 | 1924 | 0 | 2 | 20 | 1902 | 0 |
| 20 | N30-S1-E2-F1 | 1929 | 4 | 1 | 1924 | 1 | 2 | 436 | 1485 | 0 |
| 21 | N30-S2-E1-F0 | 1929 | 4 | 1 | 1924 | 0 | 11 | 20 | 1893 | 0 |
| 22 | N30-S2-E1-F1 | 1929 | 4 | 1 | 1924 | 1 | 11 | 433 | 1479 | 0 |
| 23 | N30-S2-E2-F0 | 1929 | 4 | 1 | 1924 | 0 | 11 | 20 | 1893 | 0 |
| 24 | N30-S2-E2-F1 | 1929 | 4 | 1 | 1924 | 1 | 11 | 433 | 1479 | 0 |

#### Validation

- brute_force_trades: 500
- brute_force_mismatches: 0
- mutation_detected: 500
- lookahead_trades_checked: 41548
- rule_check_days: 115
- truncation_days: 20
- charts_check_saved: 30


Charts: `charts/equity_orb.png` (cumulative R with the IS/OOS cutoff), `charts/null_orb.png`, `charts/yearly_orb.png`.

### Controls in plain words

- **Drift-matched null:**
  - Every S1 test at N15/N30 sits at the 99.4th–100th percentile.
  - The S2-E1 tests sit at the 4th–96th percentile (N5-S2-E1 at the 4th–6th, i.e. worse than random timing).
  - Matching the yearly long share means the 2019–2026 uptrend alone can't explain the S1 results.
- **Mirror:**
  - For every candidate, the mirror is negative (−0.05 to −0.10R) while the real trade is positive.
  - The breakout's direction carries information: fading the breakout loses.
- **Drift baseline** (always-long / always-short from 08:35, reference only):
  - Always-long earns +0.05 to +0.065R on the N30-S1 dates and R, so part of the long side resembles plain drift.
  - Always-short loses −0.02 to −0.09R there, yet the real strategy's **shorts are positive too** (+0.06 to +0.08R in the candidates). The real mean exceeds always-long by 0.02–0.08R across the candidates (0.04R for tests 18 and 20).
- **Costs:** they cost only about 0.01–0.02R per trade for S1, because R is large (zero-cost vs. net expectancy).

### Power

- MDE at 80% power is 0.06–0.09R for every S1 test and every S2-E1 test (n ≈ 1,500–1,900), and 0.10–0.17R for the S2-E2 tests, whose results are noisier.
- The candidates' effects (+0.07 to +0.11R) are just above their MDEs.
- Even a large forward sample will take years to confirm an effect this size. The F1 candidates trade about 200 times a year (F0 about 255), so reaching the pre-registered n ≥ 200 takes about a year. Reaching an MDE ≈ 0.1R takes about 1,500 trades, which is several years.

### Funnel

- No trigger before 14:00: 0 days for N5 and N15, 20 for N30 (F0). With the F1 filter, 228–436 days per test never trigger, because only one side's order is placed.
- R < 8 skips by year are in `skip_R8_by_year.csv`. Almost all of them are in 2019–2020 S2 tests, for example N5-S2: 47 in 2019 and 0 in 2025–26.

## Exploratory, not evidence

Descriptive splits made after seeing the results; never used for selection. Files: `descriptive_splits_orb.csv`, `R_points_by_year.csv`, `skip_R8_by_year.csv`.

- **OR width** (relative to ATR): in the candidates, wide-OR days did best (N30-S1-F1: +0.16R wide, +0.05 mid, +0.09 to +0.11 narrow).
- **Gap size:** for N15-S1-E2-F1, small-|gap| days were ≈ 0R (−0.007) and mid/large gaps were +0.15 to +0.17R. For N30 the pattern is weaker (+0.06 small vs. +0.11 to +0.15).
- **Weekday:** Fridays and Mondays were strongest in N30-S1-F1 (+0.13 to +0.17R). This is unadjusted noise-level slicing.
- **Long vs. short:** both are positive in every candidate; longs are higher (+0.07 to +0.14R vs. shorts +0.06 to +0.08R).
- **Account-fit subset (R ≤ 30 pts):** only 58–111 trades per candidate, mostly from 2019 when prices were lower (43 of 58 for tests 18 and 20; 76 of 111 for test 12). Results: +0.06R (test 18), −0.02R (test 20), −0.18R (test 12). **There is no evidence the effect exists at small stop sizes.**
- **R in points by year (N30-S1):** median 36 pts (2019) → 77 (2020) → 124 (2022) → 125 (2025) → 180 (2026). The share of trades fitting a $50 budget fell from 19% (2019) to 0% (2025–26).
- **Year-by-year (net R per trade):** for example, N30-S1-E1-F1 by year 2019–2026 is +0.02, +0.14, +0.12, +0.12, +0.11, +0.15, +0.08, +0.04. It is positive every year but weaker in 2019 and 2026.

## Amendments

None. No definition, parameter or test was changed after the freeze.

Two changes were made before any results existed, after the pre-registration was frozen, and neither touches a rule:
- The forward-test import was fixed (the file shares a name with the v2 module).
- The rule check was extended to cover every conflict / missing-OR day.

## Forward test (the only real confirmation)

`forward_test.py`:
- applies the frozen rules unchanged and verifies the pre-registration hash first;
- loads the original raw history plus any new raw Databento MNQ.FUT `ohlcv-1m` DBN files in `./data_forward/`;
- rebuilds the adjusted series with the same roll rule (the v2 rebuild, verified to reproduce the history exactly) so the EMA warms up;
- runs the 24 tests and scores **only dates after 2026-10-23**;
- prints the same metrics (R and $, t-test, Holm/BH, drift-matched null percentile, mirror).

How to run it later:

1. **Wait for at least ~3 months of new data** (about 60 trading days, so at most about 60 trades per test). That is far too few to confirm a 0.1R effect; treat it only as a sign check. A real confirmation needs about 200+ trades, roughly a year for tests 18 and 20.
2. **Check the cost first.** This is free and downloads nothing:
   ```bash
   DATABENTO_KEY_FILE=/path/to/keyfile python3 backtest_ict_v2/fetch_forward.py 2026-10-24 2027-02-01
   ```
3. **Download only after reviewing the quote**, with a dollar cap. A few months of MNQ 1m data should cost well under $2 at the historical rate:
   ```bash
   DATABENTO_KEY_FILE=/path/to/keyfile python3 backtest_ict_v2/fetch_forward.py 2026-10-24 2027-02-01 --confirm --cap 3.00
   ```
4. **Run the forward test:**
   ```bash
   python3 backtest_orb/forward_test.py
   ```
   Results are saved to `backtest_orb/forward_results_<last date>.csv`.

**Pre-commit now to judging the forward test on tests 18 and 20** (the two that survive the cross-study correction). Do not hunt among the 24 afterwards. Do not edit `PREREGISTRATION.md`, `orb_core.py` or the parameters first.

## Files

| File | Contents |
|---|---|
| `PREREGISTRATION.md`, `PREREGISTRATION.sha256` | Frozen design and hash |
| `orb_core.py` | OR, EMA lock, conflict flag, stop entries, exits, mirror, drift-matched null, drift baseline |
| `validate_orb.py` | Brute-force simulator, mutation test, look-ahead / rule / truncation checks, faithfulness charts |
| `run_orb.py` | Hash check → validation gate → 24 tests, controls, statistics, Monte Carlo, splits, charts, tables |
| `forward_test.py` | Forward test on new data (never run here); fetch via `backtest_ict_v2/fetch_forward.py` |
| `trades_orb.csv` | Every trade of all 24 tests (41,548 rows; the `label` column names the test) |
| `results_orb.csv`, `results_tables_orb.md`, `funnel_orb.csv` | Per-test metrics, verdicts, funnels |
| `descriptive_splits_orb.csv`, `R_points_by_year.csv`, `skip_R8_by_year.csv` | Exploratory splits (not evidence) |
| `run_summary_orb.json`, `run_log_orb.txt` | Run metadata and log |
| `charts/`, `charts_check/` | Equity / null / yearly charts; 30 faithfulness charts |
