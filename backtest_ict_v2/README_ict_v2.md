# ICT v2 on MNQ: a pre-registered, mechanical re-test judged in R-multiples

## Honesty clause

v2 was designed AFTER seeing study-2 results on this same data. Therefore ANY positive v2 result on this history is NOT out-of-sample evidence; it is at most a lead. The only real confirmation is the forward test (see deliverables): frozen rules run on data after 2026-10-23.

(The analyst who ran v2 also produced and saw the earlier ICT study in `backtest_ict/` on the same data. No earlier results file was opened before `PREREGISTRATION.md` was frozen and pushed (commit `eedcc6b`), but those results were already known from producing them.)

## Verdict

**No evidence of an edge.** None of the 32 pre-registered tests meets the "candidate edge" criteria, and the multiplicity results are as clean a null as they get:

- Every Holm-corrected p-value is 1.000.
- No raw p-value is below 0.05; chance alone would produce about 1.6 of 32.
- The smallest raw p is 0.074 (A2-ASIA-X1, 27 trades).

| Model | Primary trades (NY-AM / ASIA) | Expectancy after costs (X1 / X2) | Plain reading |
|---|---|---|---|
| A1 Sweep + FVG, market | 107 / 21 | NY-AM −0.05R / −0.11R; ASIA +0.28R / +0.16R | NY-AM ≈ zero to negative. ASIA is too small (21 trades; detectable effect ≈ 0.6R). |
| A2 Sweep + FVG, limit | 134 / 27 | NY-AM +0.06R / −0.01R; ASIA +0.34R / +0.25R | NY-AM ≈ zero. ASIA is too small, and its out-of-sample is ≤ 0. |
| B OTE | 221 / 15 | NY-AM −0.02R / −0.02R; ASIA +0.44R / +0.27R | NY-AM, with a real sample, is flat (95% CI −0.17 to +0.15R). ASIA has 15 trades. |
| D Order block | 949 / 360 | NY-AM −0.17R / −0.22R; ASIA −0.24R / −0.22R | **Reliably negative.** All four 95% CIs are below zero, and it loses in every year (0/8 positive years in three of the four tests). |

The 1H-bias filter doesn't change the picture. For A and B it removes 80–90% of setups, because a sweep of highs mostly happens in a bullish 1H stack, so these setups are structurally counter-trend. That leaves 2–30 trades per test. D with the bias filter is still negative in R.

**Scope:** this tests **one rigid, mechanical interpretation** of each model. It says nothing about how a skilled discretionary trader applies ICT; such a trader picks context, skips setups and reads structure flexibly. A negative result here does not prove that discretionary ICT has no skill. A positive result would have been a lead for the forward test, never proof.

## What v2 changed, and whether each fix worked

| Flaw found in study 1 | v2 change (pre-registered) | Did it work? |
|---|---|---|
| A fixed 8–40 pt stop filter starved the samples as price doubled | Risk filter 0.4–3.0 × ATR; stop buffer 0.1 × ATR | **Yes.** Skips are now spread evenly by year (`skips_by_reason_year_v2.csv`). The cost: stops in points grew with price, e.g. the median A1 NY-AM stop went from 26 pts (2019) to 118 pts (2026), as shown in `stop_points_by_year_v2.csv`. |
| The OTE "no-retrace" cancel invalidated ~81% of signals before arming | Removed; B is armed at the MSS close and valid 24 bars | **Yes.** B-NY-AM has 636 valid setups and 221 trades (study 1: 16). The fill ratio is 35%; ASIA is 20% (flagged). |
| Cancel rules were inert | A2 keeps "cancel beyond the sweep extreme"; D keeps the close-beyond-edge cancel | **No.** There were **0 cancels in every test**. Price can't reach the sweep extreme or close past the OB edge without first trading through the limit, so the fill always comes first. This was predicted in the pre-registration (interpretation #15) and is reported, not changed. |
| MSS could be trivially satisfied | The reference swing must be ≤ 40 bars older than the sweep; plus a new sweep-invalidation rule | **Age rule: no.** It rejected 0 signals; only 0.1% of window bars have a most-recent swing older than 40 bars, and the median age is 6. The faithfulness chart `charts_check/modelB_03.png` shows the MSS can still be trivial: the swing low had already been closed through by the sweep bar. The real problem is a swing that was *already broken*, not an *old* one. **Invalidation rule: binding.** It removed 4,107 of 6,226 NY-AM sweeps (66%) and 801 of 1,272 ASIA sweeps. |

## Data and how to run

- **Data:** the back-adjusted MNQ 1m series and roll log from `backtest_ict/data/`, reused.
  - Databento GLBX.MDP3 `ohlcv-1m`, MNQ.FUT, 2019-05-05 → 2026-10-23.
  - 30 volume-based rolls at the 17:00 CT open; additive back-adjustment.
  - No API call or credit was used for v2.
- **Engine reuse:** `ict_core.py` provides levels, swings, displacement, the 1H bias and the 1m exit simulator. All passed validation in study 1 and are re-validated here.
- **Time handling:** explicit ns timestamps, America/Chicago with DST, nothing held through the 16:00–17:00 CT halt.
- **Roll exclusions:** 0, because rolls happen at the 17:00 open and no trade spans one.
- **IS/OOS cutoff:** 2024-07-27 11:42 UTC (70% of the calendar span).

```bash
python3 backtest_ict_v2/run_v2.py       # verifies the PREREGISTRATION hash, validates, then runs (~5 min)
```

## Definitions

The binding text is **[PREREGISTRATION.md](PREREGISTRATION.md)** (SHA-256 `088fe751…4c80f`, frozen before any v2 code). Summary:

- **Levels:**
  - PDH/PDL = the most recent completed 08:30–15:00 CT session.
  - ONH/ONL = 17:00 CT the previous evening to 08:30 CT, usable from 08:30.
  - NY-AM (08:30–11:00) uses all four; ASIA (17:00–20:00) uses PDH/PDL only.
- **Indicators:**
  - 1H bias = EMA 9/21/50 stack on completed 1H bars.
  - ATR = Wilder 14 on 5m. Setup ATR (ATR_s) = ATR at the close of the arm bar, frozen for the setup.
- **Sweep:**
  - the prior bar closed on the near side;
  - the bar trades at least 1 tick through the level;
  - a close back across the level comes within 3 bars.
  - Sweep extreme = the extreme price from the sweep bar to the reclaim bar.
- **Sweep invalidation:** any bar after the reclaim and before the MSS that trades beyond the sweep extreme kills the setup.
- **Displacement:** the bar closes beyond the prior bar's extreme, with body ≥ 1.0 × ATR (prior bar's close).
- **MSS:**
  - the first displacement bar within s+1 … s+12 (at or after the reclaim) that closes beyond the most recent opposite swing formed before the sweep;
  - that swing must be confirmed, and no older than 40 bars before the sweep.
- **FVG:** bar MSS−1 vs bar MSS+1, gap ≥ 2.0 pts. The near edge is bar3's extreme.
- **Model D:**
  - Break of structure = the first close-break of the most recent confirmed swing, made by a displacement bar.
  - Order block = the last opposite-colour candle among the 5 bars before it.
- **Models:**
  - **A1:** market at the next bar's open + 1 tick (armed at the MSS+1 close).
  - **A2:** limit at the FVG near edge, valid to MSS+12, cancelled beyond the sweep extreme.
  - **B:** limit at the 70.5% retracement of the sweep-extreme → MSS-extreme leg, leg ≥ 1.5 × ATR_s. Armed at the MSS close, valid 24 bars, cancelled only beyond the sweep extreme.
  - **D:** limit at the order block midpoint, valid 24 bars, cancelled on a 5m close beyond the far edge.
  - **Stops:** structure point ± 0.1 × ATR_s, rounded outward.
  - **Risk filter:** 0.4 ≤ R / ATR_s ≤ 3.0.
- **Execution, simulated on 1m bars:**
  - Limits and targets need a trade 1 tick through.
  - Stops fill as market orders with 1 tick of slippage, at the bar open if price gapped past.
  - If stop and target are both reachable in one 1m bar, the stop counts first. In the fill bar only the stop is checked.
  - X1 target = 1.5R; X2 target = 3.0R.
  - $2 per point and $1 round-trip commission; results are also shown at zero cost.
  - RTH trades are flat by 14:55 CT. ASIA trades are flat at fill + 3h or at 23:00 CT, whichever comes first.
  - One position and one pending order at a time; at most 2 losses per window per day.

### Interpretation log (from the pre-registration)

| # | Ambiguity | Chosen definition |
|---|---|---|
| 1 | Where the data layer lives (`./data`, `./backtest`, `./backtest_levels` do not exist) | Reuse `backtest_ict/data` and `backtest_ict/ict_core.py`. |
| 2 | "ATR as of the arm-bar close" per model | A1/A2: bar m+1; B: bar m; D: bar d. Displacement still uses the prior bar's ATR. |
| 3 | Rounding of buffered stops | Outward to the tick (wider stop). |
| 4 | Rounding of R-multiple targets | Toward the entry. |
| 5 | A1 "next bar's open" | First 1m bar with open ≥ arm time; fill = open + 1 tick adverse. |
| 6 | A1 risk-filter timing | Applied at the fill, with R from the actual fill price. |
| 7 | A1 open already beyond the stop | Skipped ("gap_through_stop"). |
| 8 | "Trades beyond the sweep extreme" | ≥ 1 tick beyond. |
| 9 | Invalidation range | Bars strictly after the reclaim bar and before the MSS bar. |
| 10 | Swing-age rule when the most recent swing is too old | No signal; no fallback to another swing. |
| 11 | Age measured from | The sweep bar: p ≥ s − 40. |
| 12 | B leg extent | From the sweep extreme to the extreme of bars s … m inclusive. |
| 13 | B "24 bars after the MSS bar" | Through the close of bar m+24. |
| 14 | Fill and cancel in the same 1m bar | Fill first (conservative). |
| 15 | Inert cancel rules (A2, B, D) | Kept as specified; they effectively act only across gaps. Counts reported. |
| 16 | Stale check for A2 | Arm-bar close at/through the near edge → stale. |
| 17 | Simultaneous setups | By arm time, then sweep bar, then short before long. |
| 18 | Primary statistic | Net R (null, mirror, IS/OOS, years, t-test); $ reported alongside. |
| 19 | MDE | (z0.95 + z0.80) × SD / √n (normal approximation). |
| 20 | Null stop sizing | ATR multiple of the real trade × ATR at the close of the bar before the null entry. |
| 21 | Null entry slippage | +1 tick for A1 tests; none for limit models. |
| 22 | Equal-trade-count blocks | 3 chronological blocks of ⌊n/3⌋; the remainder goes to the last block. |
| 23 | SB-PM split | A separate descriptive-only simulation (no tested window covers 13:00–14:00). |
| 24 | "Valid signals" for the 30% flag | Setups with status ok. |
| 25 | Calendar year for "positive years" | CT year of the fill; net R sum > 0. |
| 26 | Holiday early closes | Time exit at the last 1m bar before the cutoff in the fill's session. |
| 27 | Losing trade for the loss cap | Net $ < 0 after costs. |
| 28 | Roll-excluded trades | Still occupy the slot and count toward the loss cap; removed from the statistics only. |

## Validation (passed before any P&L was computed or printed)

No smoke run printed P&L, win rate or expectancy before this gate; smoke runs printed counts only.

| Check | Result |
|---|---|
| Independent brute-force 1m simulator vs. main engine, 500 random trades (fill bar and price, exit bar and price, reason, net $) | **0 mismatches** |
| Mutation test: every exit price shifted by 1 tick | **500 / 500 detected** |
| Look-ahead assertions on all 5,713 tested setups and every trade (level known, swing confirmed, swing age ≤ 40, no invalidation bar before the MSS, FVG at arm, ATR_s from the arm bar, completed-bar 1H bias, fill ≥ arm, fill < window end) | Pass |
| Hand-coded rule re-verification, 100 random setups per model, from independently aggregated 5m bars, independently computed levels and a hand-rolled ATR | 400 / 400 pass. Corrupting the stop, ATR_s, swing reference, OB stop, filter status or the sweep extreme was caught 30/30 for each. |
| Truncation test, 20 setups per model, re-derived from data cut at the arm time | 80 / 80 identical |
| Vectorised null engine vs. `simulate_exit`, 3,000 random draws | 0 mismatches |
| `forward_test.py` rebuild of the history from the raw file vs. the frozen series | Identical (2,635,600 bars, max price diff 0.0, identical rolls) |
| Faithfulness charts, 15 per model (`charts_check/`, 60 PNGs) | **Reviewed (A1_01, A2_02, B_03, D_04 checked level by level): all match the definitions.** Sweep, reclaim, swing age, MSS close, FVG near edge, 70.5% level, OB midpoint, buffered stop and R/ATR, targets and exits all match. The review also showed the trivially satisfied MSS (B_03), which is a property of the frozen definition, not a code bug. |

## Results

**32 tests.** All metrics are net of costs, with expectancy in R as the primary metric.

- **p-values:** p = one-sided t-test on net R (H1: mean > 0). Holm–Bonferroni and Benjamini–Hochberg are both applied across all 32. Expected false positives at p < 0.05: **1.6**; observed: **0**.
- **Candidate edge:** a test qualifies only if it meets **all** of the following:
  - IS > 0 and OOS > 0;
  - n ≥ 200;
  - at least 4 positive years;
  - above the null's 95th percentile;
  - better than its mirror;
  - Holm p < 0.10.
- **MDE:** the smallest true mean R this sample could detect with 80% power.
- **Null pct:** the real mean R's percentile among 1000 random-direction simulations. These use the same window and 30-minute bucket, random direction, stop sizes resampled as ATR multiples, the same exits and the same costs.
- **Mirror R:** the same fills traded in the opposite direction with the same distances.

#### Results — all 32 tests (net of costs; primary metric = expectancy in R; p = one-sided t-test on net R)

| # | Test | n | IS/OOS n | Win% | BE win% | Avg win R | Avg loss R | Exp R | Exp R 0-cost | Exp $ | Avg win $ | Avg loss $ | PF | Max DD $ | Loss streak | p raw | p Holm | p BH | 95% CI (R) | MDE R | Exp R IS | Exp R OOS | Blocks 1/2/3 (R) | Yrs + | Null pct | Mirror R | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | A1-NYAM-X1 | 107 | 79/28 | 39.3 | 41.5 | 1.31 | -0.93 | -0.050 | -0.034 | -14.75 | 178.29 | -139.48 | 0.83 | 2468 | 12 | 0.676 | 1.000 | 0.969 | [-0.261, 0.164] | 0.273 | -0.014 | -0.153 | 0.16/-0.04/-0.26 | 5/8 | 39.0 | -0.159 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,null,p_holm) |
| 2 | A1-NYAM-X2 | 106 | 78/28 | 32.1 | 36.5 | 1.57 | -0.90 | -0.110 | -0.093 | -12.18 | 240.88 | -131.69 | 0.86 | 2985 | 12 | 0.805 | 1.000 | 1.000 | [-0.354, 0.147] | 0.318 | -0.038 | -0.311 | -0.08/0.19/-0.43 | 2/8 | 19.2 | -0.225 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,p_holm) |
| 3 | A1-ASIA-X1 | 21 | 12/9 | 61.9 | 47.7 | 1.04 | -0.95 | 0.283 | 0.317 | 16.48 | 66.58 | -64.94 | 1.67 | 170 | 3 | 0.119 | 1.000 | 0.736 | [-0.161, 0.721] | 0.578 | 0.396 | 0.131 | 0.51/-0.13/0.46 | 6/8 | 92.2 | -0.347 | underpowered; no evidence of an edge (fails: underpowered,null,p_holm) |
| 4 | A1-ASIA-X2 | 21 | 12/9 | 57.1 | 49.1 | 0.99 | -0.95 | 0.157 | 0.194 | -2.81 | 50.75 | -74.22 | 0.91 | 272 | 3 | 0.269 | 1.000 | 0.870 | [-0.303, 0.661] | 0.621 | 0.407 | -0.177 | 0.55/-0.14/0.06 | 4/8 | 81.0 | -0.320 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,null,p_holm) |
| 5 | A2-NYAM-X1 | 134 | 96/38 | 44.0 | 41.4 | 1.33 | -0.94 | 0.059 | 0.072 | -4.73 | 156.61 | -131.65 | 0.94 | 2055 | 8 | 0.280 | 1.000 | 0.870 | [-0.136, 0.261] | 0.252 | 0.054 | 0.072 | 0.15/-0.04/0.07 | 4/8 | 74.4 | -0.189 | underpowered; no evidence of an edge (fails: underpowered,null,p_holm) |
| 6 | A2-NYAM-X2 | 133 | 95/38 | 36.1 | 36.6 | 1.59 | -0.92 | -0.012 | 0.003 | -12.61 | 184.67 | -124.01 | 0.84 | 2682 | 8 | 0.538 | 1.000 | 0.935 | [-0.241, 0.229] | 0.300 | 0.020 | -0.089 | 0.26/-0.17/-0.13 | 3/8 | 47.4 | -0.205 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,p_holm) |
| 7 | A2-ASIA-X1 | 27 | 17/10 | 59.3 | 44.5 | 1.28 | -1.02 | 0.340 | 0.365 | 8.83 | 80.22 | -95.00 | 1.23 | 441 | 3 | 0.074 | 1.000 | 0.736 | [-0.112, 0.770] | 0.567 | 0.550 | -0.019 | 0.41/0.51/0.09 | 6/8 | 97.4 | -0.194 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,p_holm) |
| 8 | A2-ASIA-X2 | 27 | 17/10 | 48.1 | 38.3 | 1.56 | -0.97 | 0.249 | 0.278 | -8.41 | 78.08 | -88.71 | 0.82 | 676 | 5 | 0.184 | 1.000 | 0.736 | [-0.260, 0.789] | 0.676 | 0.653 | -0.438 | 0.60/0.52/-0.37 | 6/8 | 88.4 | -0.213 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,null,p_holm) |
| 9 | B-NYAM-X1 | 221 | 151/70 | 40.7 | 41.3 | 1.46 | -1.03 | -0.015 | 0.012 | -5.63 | 85.53 | -68.26 | 0.86 | 2012 | 15 | 0.574 | 1.000 | 0.935 | [-0.171, 0.146] | 0.206 | -0.030 | 0.017 | -0.13/0.11/-0.02 | 3/8 | 62.6 | -0.132 | no evidence of an edge (fails: IS/OOS,years,null,p_holm) |
| 10 | B-NYAM-X2 | 216 | 148/68 | 27.8 | 28.5 | 2.58 | -1.03 | -0.024 | 0.006 | -7.76 | 143.25 | -65.84 | 0.84 | 2225 | 17 | 0.584 | 1.000 | 0.935 | [-0.243, 0.201] | 0.283 | -0.030 | -0.011 | -0.22/0.21/-0.07 | 4/8 | 53.5 | -0.240 | no evidence of an edge (fails: IS/OOS,null,p_holm) |
| 11 | B-ASIA-X1 | 15 | 10/5 | 60.0 | 42.6 | 1.45 | -1.08 | 0.441 | 0.497 | 20.07 | 53.83 | -30.58 | 2.64 | 73 | 2 | 0.102 | 1.000 | 0.736 | [-0.229, 1.104] | 0.824 | 0.432 | 0.460 | 0.43/0.43/0.46 | 4/7 | 95.5 | -0.565 | underpowered; no evidence of an edge (fails: underpowered,p_holm) |
| 12 | B-ASIA-X2 | 15 | 10/5 | 33.3 | 26.5 | 2.95 | -1.07 | 0.273 | 0.333 | 9.30 | 98.60 | -35.35 | 1.39 | 190 | 5 | 0.299 | 1.000 | 0.870 | [-0.544, 1.339] | 1.258 | 0.530 | -0.241 | -0.27/1.33/-0.24 | 3/7 | 81.5 | -0.658 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,p_holm) |
| 13 | D-NYAM-X1 | 949 | 667/282 | 35.6 | 42.4 | 1.45 | -1.07 | -0.170 | -0.111 | -3.05 | 56.61 | -36.05 | 0.87 | 3094 | 17 | 1.000 | 1.000 | 1.000 | [-0.248, -0.094] | 0.098 | -0.174 | -0.160 | -0.20/-0.16/-0.16 | 0/8 | 7.2 | -0.420 | no evidence of an edge (fails: IS/OOS,years,null,p_holm) |
| 14 | D-NYAM-X2 | 945 | 664/281 | 21.2 | 26.6 | 2.94 | -1.07 | -0.218 | -0.155 | -4.99 | 113.33 | -36.76 | 0.83 | 5238 | 26 | 1.000 | 1.000 | 1.000 | [-0.321, -0.114] | 0.133 | -0.208 | -0.242 | -0.23/-0.23/-0.19 | 0/8 | 2.1 | -0.407 | no evidence of an edge (fails: IS/OOS,years,null,p_holm) |
| 15 | D-ASIA-X1 | 360 | 229/131 | 36.4 | 45.7 | 1.38 | -1.16 | -0.237 | -0.093 | -0.38 | 25.24 | -15.04 | 0.96 | 620 | 10 | 1.000 | 1.000 | 1.000 | [-0.362, -0.109] | 0.162 | -0.312 | -0.105 | -0.48/-0.14/-0.09 | 0/8 | 15.3 | -0.418 | no evidence of an edge (fails: IS/OOS,years,null,p_holm) |
| 16 | D-ASIA-X2 | 358 | 227/131 | 23.5 | 28.9 | 2.87 | -1.16 | -0.218 | -0.068 | 1.65 | 56.71 | -15.23 | 1.14 | 554 | 14 | 0.991 | 1.000 | 1.000 | [-0.394, -0.041] | 0.226 | -0.361 | 0.030 | -0.48/-0.23/0.06 | 1/8 | 24.0 | -0.356 | no evidence of an edge (fails: IS/OOS,years,null,p_holm) |
| 17 | A1-NYAM-X1+bias | 7 | 5/2 | 71.4 | 42.4 | 1.37 | -1.01 | 0.691 | 0.706 | 148.86 | 285.90 | -193.75 | 3.69 | 250 | 1 | 0.086 | 1.000 | 0.736 | [-0.293, 1.407] | 1.109 | 0.486 | 1.204 | 0.22/0.24/1.30 | 4/5 | 94.7 | -0.656 | underpowered; no evidence of an edge (fails: underpowered,null,p_holm) |
| 18 | A1-NYAM-X2+bias | 7 | 5/2 | 57.1 | 35.6 | 1.85 | -1.02 | 0.617 | 0.635 | 190.21 | 437.75 | -139.83 | 4.17 | 250 | 2 | 0.180 | 1.000 | 0.736 | [-0.469, 1.749] | 1.551 | 0.358 | 1.267 | -1.03/0.99/1.46 | 3/5 | 89.2 | -0.848 | underpowered; no evidence of an edge (fails: underpowered,years,null,p_holm) |
| 19 | A1-ASIA-X1+bias | 3 | 1/2 | 33.3 | 32.2 | 1.48 | -0.70 | 0.024 | 0.061 | -8.17 | 60.50 | -42.50 | 0.71 | 48 | 1 | 0.488 | 1.000 | 0.935 | [-1.043, 1.476] | 1.870 | -1.043 | 0.558 | -1.04/1.48/-0.36 | 1/3 | 60.2 | -1.030 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,p_holm) |
| 20 | A1-ASIA-X2+bias | 3 | 1/2 | 33.3 | 36.7 | 1.21 | -0.70 | -0.065 | -0.025 | -11.83 | 49.50 | -42.50 | 0.58 | 48 | 1 | 0.534 | 1.000 | 0.935 | [-1.043, 1.207] | 1.656 | -1.043 | 0.424 | -1.04/1.21/-0.36 | 1/3 | 53.8 | -1.030 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,p_holm) |
| 21 | A2-NYAM-X1+bias | 10 | 7/3 | 60.0 | 43.7 | 1.30 | -1.01 | 0.378 | 0.391 | 39.70 | 177.92 | -167.62 | 1.59 | 244 | 2 | 0.180 | 1.000 | 0.736 | [-0.370, 1.119] | 0.976 | 0.258 | 0.660 | -0.19/0.66/0.59 | 5/6 | 86.3 | -0.320 | underpowered; no evidence of an edge (fails: underpowered,null,p_holm) |
| 22 | A2-NYAM-X2+bias | 10 | 7/3 | 40.0 | 39.5 | 1.48 | -0.97 | 0.012 | 0.028 | 17.85 | 244.25 | -133.08 | 1.22 | 326 | 4 | 0.489 | 1.000 | 0.935 | [-0.748, 0.902] | 1.116 | -0.202 | 0.513 | -1.03/0.43/0.48 | 3/6 | 52.2 | -0.462 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,p_holm) |
| 23 | A2-ASIA-X1+bias | 4 | 2/2 | 75.0 | 40.7 | 1.47 | -1.01 | 0.851 | 0.871 | 19.38 | 86.83 | -183.00 | 1.42 | 183 | 1 | 0.132 | 1.000 | 0.736 | [-0.389, 1.481] | 1.541 | 0.222 | 1.479 | -1.01/1.45/1.48 | 3/3 | 96.1 | -0.404 | underpowered; no evidence of an edge (fails: underpowered,years,p_holm) |
| 24 | A2-ASIA-X2+bias | 4 | 2/2 | 25.0 | 36.3 | 1.34 | -0.76 | -0.237 | -0.208 | -46.00 | 51.50 | -78.50 | 0.22 | 211 | 2 | 0.650 | 1.000 | 0.969 | [-1.032, 0.751] | 1.389 | -1.032 | 0.558 | -1.01/-1.06/0.56 | 1/3 | 38.9 | -0.525 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,p_holm) |
| 25 | B-NYAM-X1+bias | 30 | 18/12 | 40.0 | 40.7 | 1.49 | -1.02 | -0.019 | -0.001 | -5.78 | 121.46 | -90.61 | 0.89 | 606 | 6 | 0.532 | 1.000 | 0.935 | [-0.437, 0.400] | 0.567 | 0.230 | -0.392 | 0.48/-0.02/-0.51 | 3/6 | 55.2 | -0.018 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,mirror,p_holm) |
| 26 | B-NYAM-X2+bias | 30 | 18/12 | 23.3 | 27.8 | 2.65 | -1.02 | -0.165 | -0.145 | -17.20 | 218.29 | -88.87 | 0.75 | 826 | 8 | 0.708 | 1.000 | 0.969 | [-0.699, 0.447] | 0.740 | -0.041 | -0.350 | -0.22/0.34/-0.62 | 2/6 | 33.1 | -0.003 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,mirror,p_holm) |
| 27 | B-ASIA-X1+bias | 2 | 1/1 | 50.0 | 40.8 | 1.48 | -1.02 | 0.229 | 0.248 | 7.50 | 88.00 | -73.00 | 1.21 | 73 | 1 | 0.442 | 1.000 | 0.935 | [-1.021, 1.479] | 3.108 | -1.021 | 1.479 | 0.23/–/– | 1/2 | 82.3 | 0.229 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,p_holm) |
| 28 | B-ASIA-X2+bias | 2 | 1/1 | 50.0 | 25.5 | 2.98 | -1.02 | 0.981 | 1.000 | 52.25 | 177.50 | -73.00 | 2.43 | 73 | 1 | 0.355 | 1.000 | 0.935 | [-1.021, 2.983] | 4.978 | -1.021 | 2.983 | 0.98/–/– | 1/2 | 91.6 | 0.043 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,p_holm) |
| 29 | D-NYAM-X1+bias | 401 | 277/124 | 38.9 | 42.6 | 1.45 | -1.08 | -0.093 | -0.030 | 2.21 | 58.27 | -33.48 | 1.11 | 572 | 8 | 0.934 | 1.000 | 1.000 | [-0.218, 0.029] | 0.154 | -0.111 | -0.052 | -0.24/-0.02/-0.02 | 2/8 | 60.8 | -0.576 | no evidence of an edge (fails: IS/OOS,years,null,p_holm) |
| 30 | D-NYAM-X2+bias | 401 | 277/124 | 22.7 | 26.6 | 2.96 | -1.07 | -0.159 | -0.092 | 0.39 | 120.35 | -34.83 | 1.01 | 1407 | 20 | 0.970 | 1.000 | 1.000 | [-0.321, 0.009] | 0.210 | -0.212 | -0.041 | -0.29/-0.24/0.05 | 2/8 | 21.2 | -0.493 | no evidence of an edge (fails: IS/OOS,years,null,p_holm) |
| 31 | D-ASIA-X1+bias | 148 | 89/59 | 35.8 | 45.5 | 1.37 | -1.15 | -0.245 | -0.114 | -1.79 | 24.53 | -16.47 | 0.83 | 488 | 11 | 0.992 | 1.000 | 1.000 | [-0.437, -0.049] | 0.249 | -0.298 | -0.164 | -0.41/-0.17/-0.15 | 2/8 | 23.1 | -0.396 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,p_holm) |
| 32 | D-ASIA-X2+bias | 147 | 88/59 | 26.5 | 28.8 | 2.84 | -1.15 | -0.089 | 0.046 | 1.47 | 51.67 | -16.66 | 1.12 | 468 | 12 | 0.726 | 1.000 | 0.969 | [-0.366, 0.210] | 0.365 | -0.169 | 0.031 | -0.37/0.08/0.02 | 3/8 | 70.3 | -0.281 | underpowered; no evidence of an edge (fails: IS/OOS,underpowered,years,null,p_holm) |

#### Monte Carlo ($; 2000 orderings, fresh account; * = n below horizon, resampled with replacement)

Warning: risk per trade varies with stop size, so these $ drawdown probabilities are not R-based.

| # | Test | n | P(DD > $292 in 50) | P(DD > $500 in 100) |
|---|---|---|---|---|
| 1 | A1-NYAM-X1 | 107 | 100.0% | 100.0% |
| 2 | A1-NYAM-X2 | 106 | 100.0% | 100.0% |
| 3 | A1-ASIA-X1 | 21 | 56.0%* | 28.8%* |
| 4 | A1-ASIA-X2 | 21 | 91.5%* | 86.7%* |
| 5 | A2-NYAM-X1 | 134 | 100.0% | 100.0% |
| 6 | A2-NYAM-X2 | 133 | 100.0% | 100.0% |
| 7 | A2-ASIA-X1 | 27 | 94.5%* | 89.6%* |
| 8 | A2-ASIA-X2 | 27 | 99.4%* | 99.0%* |
| 9 | B-NYAM-X1 | 221 | 98.6% | 98.8% |
| 10 | B-NYAM-X2 | 216 | 99.8% | 99.9% |
| 11 | B-ASIA-X1 | 15 | 3.9%* | 0.3%* |
| 12 | B-ASIA-X2 | 15 | 66.7%* | 44.0%* |
| 13 | D-NYAM-X1 | 949 | 84.0% | 77.5% |
| 14 | D-NYAM-X2 | 945 | 95.5% | 95.2% |
| 15 | D-ASIA-X1 | 360 | 11.7% | 4.0% |
| 16 | D-ASIA-X2 | 358 | 24.6% | 11.1% |
| 17 | A1-NYAM-X1+bias | 7 | 96.0%* | 86.9%* |
| 18 | A1-NYAM-X2+bias | 7 | 97.2%* | 92.9%* |
| 19 | A1-ASIA-X1+bias | 3 | 93.5%* | 93.5%* |
| 20 | A1-ASIA-X2+bias | 3 | 96.6%* | 98.8%* |
| 21 | A2-NYAM-X1+bias | 10 | 99.9%* | 99.1%* |
| 22 | A2-NYAM-X2+bias | 10 | 100.0%* | 100.0%* |
| 23 | A2-ASIA-X1+bias | 4 | 97.9%* | 93.7%* |
| 24 | A2-ASIA-X2+bias | 4 | 100.0%* | 100.0%* |
| 25 | B-NYAM-X1+bias | 30 | 100.0%* | 99.5%* |
| 26 | B-NYAM-X2+bias | 30 | 100.0%* | 100.0%* |
| 27 | B-ASIA-X1+bias | 2 | 83.5%* | 70.1%* |
| 28 | B-ASIA-X2+bias | 2 | 60.0%* | 35.8%* |
| 29 | D-NYAM-X1+bias | 401 | 62.3% | 48.4% |
| 30 | D-NYAM-X2+bias | 401 | 91.8% | 87.2% |
| 31 | D-ASIA-X1+bias | 148 | 20.9% | 9.0% |
| 32 | D-ASIA-X2+bias | 147 | 24.6% | 8.4% |

#### Funnel: signal → setup → armed → filled, with every skip/cancel reason (⚠ = fills < 30% of valid setups)

`signals` = sweep→MSS signals in the window (A1/A2 additionally need the FVG: `signals_with_fvg`; D counts BOS setups).

| # | Test | signals | signals_with_fvg | setups | stale | skip_small | skip_large | skip_leg | fill_outside_window | gap_through_stop | valid | bias_reject | ignored_busy | ignored_losscap | armed | cancelled | expired | filled | roll_excluded | fill/valid |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | A1-NYAM-X1 | 678 | 470 | 436 | 0 | 0 | 318 | 0 | 7 | 0 | 111 | 0 | 4 | 0 | 107 | 0 | 0 | 107 | 0 | 96% |
| 2 | A1-NYAM-X2 | 678 | 470 | 436 | 0 | 0 | 318 | 0 | 7 | 0 | 111 | 0 | 5 | 0 | 106 | 0 | 0 | 106 | 0 | 95% |
| 3 | A1-ASIA-X1 | 90 | 69 | 60 | 0 | 0 | 35 | 0 | 4 | 0 | 21 | 0 | 0 | 0 | 21 | 0 | 0 | 21 | 0 | 100% |
| 4 | A1-ASIA-X2 | 90 | 69 | 60 | 0 | 0 | 35 | 0 | 4 | 0 | 21 | 0 | 0 | 0 | 21 | 0 | 0 | 21 | 0 | 100% |
| 5 | A2-NYAM-X1 | 678 | 470 | 436 | 3 | 0 | 231 | 0 | 0 | 0 | 202 | 0 | 14 | 0 | 188 | 0 | 54 | 134 | 0 | 66% |
| 6 | A2-NYAM-X2 | 678 | 470 | 436 | 3 | 0 | 231 | 0 | 0 | 0 | 202 | 0 | 15 | 0 | 187 | 0 | 54 | 133 | 0 | 66% |
| 7 | A2-ASIA-X1 | 90 | 69 | 60 | 0 | 0 | 19 | 0 | 0 | 0 | 41 | 0 | 0 | 0 | 41 | 0 | 14 | 27 | 0 | 66% |
| 8 | A2-ASIA-X2 | 90 | 69 | 60 | 0 | 0 | 19 | 0 | 0 | 0 | 41 | 0 | 1 | 0 | 40 | 0 | 13 | 27 | 0 | 66% |
| 9 | B-NYAM-X1 | 678 | – | 638 | 0 | 0 | 0 | 2 | 0 | 0 | 636 | 0 | 55 | 0 | 581 | 0 | 360 | 221 | 0 | 35% |
| 10 | B-NYAM-X2 | 678 | – | 638 | 0 | 0 | 0 | 2 | 0 | 0 | 636 | 0 | 59 | 1 | 576 | 0 | 360 | 216 | 0 | 34% |
| 11 | B-ASIA-X1 | 90 | – | 75 | 0 | 0 | 0 | 1 | 0 | 0 | 74 | 0 | 1 | 0 | 73 | 0 | 58 | 15 | 0 | 20% ⚠ |
| 12 | B-ASIA-X2 | 90 | – | 75 | 0 | 0 | 0 | 1 | 0 | 0 | 74 | 0 | 1 | 0 | 73 | 0 | 58 | 15 | 0 | 20% ⚠ |
| 13 | D-NYAM-X1 | – | – | 2305 | 0 | 209 | 0 | 0 | 0 | 0 | 2096 | 0 | 256 | 22 | 1818 | 0 | 869 | 949 | 0 | 45% |
| 14 | D-NYAM-X2 | – | – | 2305 | 0 | 209 | 0 | 0 | 0 | 0 | 2096 | 0 | 265 | 31 | 1800 | 0 | 855 | 945 | 0 | 45% |
| 15 | D-ASIA-X1 | – | – | 1703 | 0 | 621 | 0 | 0 | 0 | 0 | 1082 | 0 | 79 | 2 | 1001 | 0 | 641 | 360 | 0 | 33% |
| 16 | D-ASIA-X2 | – | – | 1703 | 0 | 621 | 0 | 0 | 0 | 0 | 1082 | 0 | 83 | 3 | 996 | 0 | 638 | 358 | 0 | 33% |
| 17 | A1-NYAM-X1+bias | 678 | 470 | 436 | 0 | 0 | 318 | 0 | 7 | 0 | 111 | 104 | 0 | 0 | 7 | 0 | 0 | 7 | 0 | 6% ⚠ |
| 18 | A1-NYAM-X2+bias | 678 | 470 | 436 | 0 | 0 | 318 | 0 | 7 | 0 | 111 | 104 | 0 | 0 | 7 | 0 | 0 | 7 | 0 | 6% ⚠ |
| 19 | A1-ASIA-X1+bias | 90 | 69 | 60 | 0 | 0 | 35 | 0 | 4 | 0 | 21 | 18 | 0 | 0 | 3 | 0 | 0 | 3 | 0 | 14% ⚠ |
| 20 | A1-ASIA-X2+bias | 90 | 69 | 60 | 0 | 0 | 35 | 0 | 4 | 0 | 21 | 18 | 0 | 0 | 3 | 0 | 0 | 3 | 0 | 14% ⚠ |
| 21 | A2-NYAM-X1+bias | 678 | 470 | 436 | 3 | 0 | 231 | 0 | 0 | 0 | 202 | 184 | 0 | 0 | 18 | 0 | 8 | 10 | 0 | 5% ⚠ |
| 22 | A2-NYAM-X2+bias | 678 | 470 | 436 | 3 | 0 | 231 | 0 | 0 | 0 | 202 | 184 | 0 | 0 | 18 | 0 | 8 | 10 | 0 | 5% ⚠ |
| 23 | A2-ASIA-X1+bias | 90 | 69 | 60 | 0 | 0 | 19 | 0 | 0 | 0 | 41 | 35 | 0 | 0 | 6 | 0 | 2 | 4 | 0 | 10% ⚠ |
| 24 | A2-ASIA-X2+bias | 90 | 69 | 60 | 0 | 0 | 19 | 0 | 0 | 0 | 41 | 35 | 0 | 0 | 6 | 0 | 2 | 4 | 0 | 10% ⚠ |
| 25 | B-NYAM-X1+bias | 678 | – | 638 | 0 | 0 | 0 | 2 | 0 | 0 | 636 | 536 | 2 | 0 | 98 | 0 | 68 | 30 | 0 | 5% ⚠ |
| 26 | B-NYAM-X2+bias | 678 | – | 638 | 0 | 0 | 0 | 2 | 0 | 0 | 636 | 536 | 2 | 0 | 98 | 0 | 68 | 30 | 0 | 5% ⚠ |
| 27 | B-ASIA-X1+bias | 90 | – | 75 | 0 | 0 | 0 | 1 | 0 | 0 | 74 | 66 | 0 | 0 | 8 | 0 | 6 | 2 | 0 | 3% ⚠ |
| 28 | B-ASIA-X2+bias | 90 | – | 75 | 0 | 0 | 0 | 1 | 0 | 0 | 74 | 66 | 0 | 0 | 8 | 0 | 6 | 2 | 0 | 3% ⚠ |
| 29 | D-NYAM-X1+bias | – | – | 2305 | 0 | 209 | 0 | 0 | 0 | 0 | 2096 | 1279 | 64 | 0 | 753 | 0 | 352 | 401 | 0 | 19% ⚠ |
| 30 | D-NYAM-X2+bias | – | – | 2305 | 0 | 209 | 0 | 0 | 0 | 0 | 2096 | 1279 | 66 | 0 | 751 | 0 | 350 | 401 | 0 | 19% ⚠ |
| 31 | D-ASIA-X1+bias | – | – | 1703 | 0 | 621 | 0 | 0 | 0 | 0 | 1082 | 669 | 20 | 0 | 393 | 0 | 245 | 148 | 0 | 14% ⚠ |
| 32 | D-ASIA-X2+bias | – | – | 1703 | 0 | 621 | 0 | 0 | 0 | 0 | 1082 | 669 | 21 | 0 | 392 | 0 | 245 | 147 | 0 | 14% ⚠ |

#### Validation

- brute_force_trades: 500
- brute_force_mismatches: 0
- mutation_detected: 500
- lookahead_setups_checked: 5713
- rule_check_A1: 100
- truncation_check_A1: 20
- rule_check_A2: 100
- truncation_check_A2: 20
- rule_check_B: 100
- truncation_check_B: 20
- rule_check_D: 100
- truncation_check_D: 20
- charts_check_saved: 60


Charts: `charts/equity_{primary,bias}.png` (cumulative R with the IS/OOS cutoff), `charts/null_{primary,bias}.png`, `charts/yearly_{primary,bias}.png`.

### Controls in plain words

- **Random-direction null:**
  - No test with n ≥ 30 beats the null's 95th percentile.
  - The two that do (A2-ASIA-X1 at 97.4, B-ASIA-X1 at 95.5) have 27 and 15 trades.
  - D-NYAM sits at the 2nd–7th percentile, worse than random entries in the same buckets.
- **Mirror:**
  - Real beats mirror in most tests, but mostly because the mirror is also negative after costs. For example, D-NYAM-X1 is −0.17R real and −0.42R mirrored.
  - Beating a losing mirror is not evidence of an edge.
- **Costs:**
  - They take about 0.06–0.15R per trade off D, whose stops are small: zero-cost expectancy is −0.11R (NY-AM X1) and −0.09R (ASIA X1).
  - D is negative even before costs.
- **R vs. $:** D-ASIA-X2 is −0.22R but +$1.65 per trade. Stop size varies, and a few large-stop winners dominate the dollar mean. R is the pre-registered metric.

### Power

- **Model D:** 949 NY-AM trades give MDE ≈ 0.10–0.13R, so the study could have detected a modest real edge. D's observed means are negative and their CIs exclude zero.
- **B-NY-AM:** 221 trades, MDE ≈ 0.21–0.28R.
- **A-NY-AM:** MDE ≈ 0.25–0.32R.
- **ASIA A and B tests, and all bias-filtered A/B tests:** MDE 0.6–5R, so they can't distinguish any realistic edge from zero.
- **Conclusion:** "no evidence" for A and B partly reflects low power. For D it is strong evidence of no positive edge in this rigid form.

### Funnel flags

**Fills under 30% of valid setups:** B-ASIA (20%), and every A, B and D test with the bias filter (3–19%; the filter removes most setups before arming). Without the bias filter, fill ratios are 33–100%.

## Exploratory, not evidence

These come from descriptive splits made after seeing the results. They were never tests, must not be used to select a strategy, and are not out-of-sample (see the honesty clause).

- **Account-fit subset** (stop ≤ 30 pts, X1):
  - A1, A2 and B look better on small stops: for example, A2-NY-AM is +0.55R on n = 17 vs. −0.01R on n = 117.
  - But in NY-AM those small-stop A trades are almost all from 2019–2020, when prices were lower (A2: 15 of 17), so this mixes era and stop size, on tiny samples. In ASIA they are spread across the years, with only 11–13 trades in all.
  - D gets no better on small stops (−0.19R, n = 811).
- **Silver Bullet AM** (09:00–10:00 fills within NY-AM, X1): A2 is +0.21R on n = 66 vs. −0.09R outside it, and A1 is +0.08R vs. −0.15R. These are small, unadjusted subgroups.
- **Silver Bullet PM run** (13:00–14:00, descriptive simulation): A1 +0.33R / +0.19R (n = 20), A2 ≈ 0R (n = 28), B −0.04R / +0.24R (n = 20), D −0.17R / −0.06R (n = 125).
- **Direction:** shorts did better than longs in A2 and A1 (for example, A2-NY-AM shorts +0.14R vs. longs −0.06R). D is symmetric and negative.
- **Stop size by year:** median stops in points rose about 4.5–5.5× from 2019 to 2026 for every model. In 2026 the median A1/A2 NY-AM risk is about 108–118 pts, or $216–236 per MNQ contract.
- **Relation to study 1:** study 1's only lead, D-ASIA (+$4.72 per trade with fixed-point stops), did not survive v2's ATR-scaled rules: here it's −0.24R with a 95% CI below zero. That fits a result that depended on the specific parameters rather than a robust effect.

Files: `descriptive_splits_v2.csv`, `stop_points_by_year_v2.csv`, `skips_by_reason_year_v2.csv`.

## Amendments

None. No bugs were found after the pre-registration was frozen, and no definition, parameter or test was changed.

## Forward test (the only real confirmation)

`forward_test.py`:
- applies the frozen rules unchanged and verifies the pre-registration hash first;
- loads the original raw history plus any new raw Databento MNQ.FUT `ohlcv-1m` DBN files in `./data_forward/`;
- rebuilds the adjusted series with the same roll rule (verified to reproduce the frozen history exactly);
- runs the 32 tests and scores **only trades filled on or after 2026-10-24 CT**;
- prints the same metrics: R and $, t-test, Holm/BH, null percentile and mirror.

How to run it later:

1. **Wait for at least 3 months of new data.** A single test will still be underpowered: expect about 1–4 trades per quarter for the A and ASIA-B tests, about 7 for B-NY-AM, and about 30 for D-NY-AM. Treat the forward result as a check that the sign holds, not as proof. A real confirmation needs the pre-registered bar of 200+ trades.
2. **Check the cost first.** This is free and downloads nothing:
   ```bash
   DATABENTO_KEY_FILE=/path/to/keyfile python3 backtest_ict_v2/fetch_forward.py 2026-10-24 2027-02-01
   ```
3. **Download only after reviewing the quote**, with a dollar cap. Three months of MNQ 1m data should cost well under $2 at the rates quoted for the history:
   ```bash
   DATABENTO_KEY_FILE=/path/to/keyfile python3 backtest_ict_v2/fetch_forward.py 2026-10-24 2027-02-01 --confirm --cap 3.00
   ```
4. **Run the forward test:**
   ```bash
   python3 backtest_ict_v2/forward_test.py
   ```
   Results are saved to `backtest_ict_v2/forward_results_<last date>.csv`.

Do not edit `PREREGISTRATION.md`, the core, or the parameters before running it. Otherwise the forward test stops being a test of these frozen rules.

## Files

| File | Contents |
|---|---|
| `PREREGISTRATION.md`, `PREREGISTRATION.sha256` | Frozen design and hash |
| `core_v2.py` | Signals (with invalidation and swing age), setups A1/A2/B/D, test simulator, vectorised null, mirror |
| `validate_v2.py` | Brute-force simulator, mutation test, look-ahead / rule / truncation checks, faithfulness charts |
| `run_v2.py` | Hash check → validation gate → 32 tests, controls, statistics, Monte Carlo, splits, charts, tables |
| `forward_test.py`, `fetch_forward.py` | Forward test on new data; cost-checked fetcher (never run here) |
| `trades_ict_v2.csv` | Every trade of all 32 tests (the `label` column names the test) |
| `results_tests_v2.csv`, `results_tables_v2.md`, `funnel_v2.csv` | Per-test metrics, verdicts, funnels |
| `descriptive_splits_v2.csv`, `stop_points_by_year_v2.csv`, `skips_by_reason_year_v2.csv` | Exploratory splits (not evidence) |
| `run_summary_v2.json`, `run_log_v2.txt` | Run metadata and log |
| `charts/`, `charts_check/` | Equity / null / yearly charts; 60 faithfulness charts |
