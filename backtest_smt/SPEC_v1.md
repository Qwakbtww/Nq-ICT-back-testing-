# MNQ SMT + OB backtest spec (v1)

Nov 6, 2026 · @Drake

## Purpose and rules

This spec tests two things on MNQ: whether SMT divergence (MNQ vs MES) improves sweep-and-reversal trades, and whether an order-block limit entry improves them further. Every rule is frozen before any code runs.

- **Null hypothesis:** expectancy after costs is zero or negative. The earlier studies (EMA pullbacks, level rejections, FVG, mechanical order blocks) found no edge, so the default expectation is a fail.
- **Freeze:** commit this file before building anything. Any change after the first run becomes v2 with a new holdout.
- **Run order:** build data, code signals, run each split once, write the report. No peeking at the holdout.
- **For Claude Code:** read this spec in full, list every ambiguity as a question, and wait for answers before coding. Do not fill gaps with guesses.

## Data and sessions

The test uses 1-minute MNQ and MES bars from Databento, May 2019 to October 23, 2026, resampled to 5 minutes for signals.

- **Contracts:** front month by volume, rolled the day volume flips. MNQ and MES must use the same quarterly month. Skip signals in the 5 trading days around each roll.
- **Time zone:** America/Chicago (CT) with daylight saving handled.
- **Overnight window:** 17:00 CT the prior evening to 08:29 CT. The overnight high and low are computed separately for MNQ and MES from the 1-minute data.
- **Signal window:** 08:30 to 11:00 CT (NY morning). No signals outside it.
- **Forced exit:** any open trade closes at the 11:30 CT bar close.
- **Skipped days:** NFP, CPI and FOMC days, early-close days and holidays, from a calendar file built from published schedules before running. Also skip any day with a data gap over 5 minutes in either instrument between 17:00 and 11:30 CT.

## Definitions

All definitions below are written for shorts. Longs are the exact mirror, using the overnight low.

- **Sweep:** a 5m bar in the signal window whose high exceeds MNQ's overnight high by at least 1 tick (0.25). Only the first sweep per side per day counts.
- **Up-run:** the consecutive bullish 5m bars (close above open) ending at the sweep bar, capped at 6 bars. If the sweep bar closes bearish, the run ends at the bar before it. **D** is the open of the first bar in the run.
- **CISD:** the first 5m bar after the sweep that closes below D. It must occur within 12 bars of the sweep, or there is no signal.
- **SMT divergence:** at the close of the CISD bar, MES has not traded above its own overnight high at any point since 08:30 CT. For longs, MES has not traded below its overnight low.
- **Order block (test B only):** the last bullish 5m bar of the up-run. The zone is its body, open to close. The entry price is the body midpoint.
- **One trade per day:** the first valid signal only.

## The three tests

Test A0 is the control. A tests whether SMT adds anything, and B tests whether an order-block limit entry beats a market entry. Stops, targets and filters are identical across all three.

| Test | Signal | Entry | Stop | Target |
| --- | --- | --- | --- | --- |
| A0 control | Sweep + CISD, no SMT | Market, open of the bar after CISD | Sweep extreme + 2 pts | 2R |
| A | Sweep + CISD + SMT | Market, open of the bar after CISD | Sweep extreme + 2 pts | 2R |
| B | Sweep + CISD + SMT | Limit at OB body midpoint, valid 12 bars | Sweep extreme + 2 pts | 2R |

- **Sweep extreme:** the highest high from the sweep bar through the CISD bar (lowest low for longs).
- **R:** the distance from entry to stop. Skip any trade with R under 8 pts or over 40 pts, in every test.
- **Unfilled limits:** if B's limit does not fill within 12 bars of the CISD bar, there is no trade.
- **SMT effect:** compare A with A0, and compare the A0 trades that had SMT with the ones that did not.

## Execution and costs

Fills are modeled conservatively so a small edge cannot come from optimistic assumptions. The cost numbers are set once now and frozen with the rest of the spec.

- **Signals** use closed 5m bars only. Fills inside a bar use the 1-minute data.
- **Market entries** fill at the next bar's open, 1 tick worse.
- **Stops** fill at the stop price, 1 tick worse. If a bar gaps through the stop, fill at that bar's open.
- **Limits and targets** fill only if price trades 1 tick through the level.
- **Stop and target in the same 1m bar:** assume the stop was hit first.
- **Commission:** $1.00 per contract round trip. Check this against the commission on your Lucid dashboard before freezing.
- **Size:** 1 MNQ per trade in the simulation. Report results in R and in dollars.

## Splits and pass/fail

A test passes only if it clears every criterion below in both the train and validation splits. Anything else is a fail or inconclusive, and the rules do not get loosened.

| Split | Dates | Use |
| --- | --- | --- |
| Train | 2019-05-01 to 2023-12-31 | Run once per test |
| Validation | 2024-01-01 to 2025-12-31 | Run once per test |
| Holdout | 2026-01-01 to 2026-10-23 | Run once, only if train and validation both pass |
| Forward | After 2026-10-23 | Script written before any live use |

The earlier studies already looked at this price history, so the splits reduce overlap bias but do not remove it. The forward test is the real check.

**Criteria, for A and B separately:**

1. At least 250 trades in each split. Fewer is INCONCLUSIVE, not a pass.
2. Mean R after costs above +0.10, with the 95% bootstrap lower bound above 0 (10,000 resamples, trades resampled in blocks by week).
3. Profit factor at least 1.15, and a win rate at least 3 points above breakeven (about 33.3% at 2R, plus costs).
4. Positive mean R in at least 60% of calendar years.
5. A must beat A0 by at least 0.10 R, or SMT adds nothing.
6. Two primary tests, so each needs p below 0.025, one-sided.

## Robustness and prop-rule simulation

These checks describe a result after the fact. They never choose parameters, because the primary numbers above are fixed.

- **Sensitivity grid (reported only):** stop buffer 0, 2 and 4 pts. Target 1.5R, 2R and 3R. CISD window 8, 12 and 16 bars. Up-run cap 4, 6 and 8 bars. If the sign of mean R flips on a neighboring setting, call the result fragile.
- **Breakdowns:** long vs short, by hour, by year, by overnight range size, and by day of week.
- **Prop-rule simulation (only if train and validation pass):** replay the trade list at 1 MNQ on Lucid Flex rules. The 25K has a $1,000 max loss and $600 daily limit, and the 50K has a $2,000 max loss and $1,200 daily limit. Use a day-block bootstrap with 10,000 paths and report the chance of hitting the target before the max loss, the median days to get there, and the worst day.
- **Consistency check:** report the largest single day as a share of total profit against the 40% rule.

## Logging and off-limits

Every run goes in a log, and a short list of moves is banned, because those moves are how a failing test turns into a fake edge.

- **Log:** one line per run in RUN\_LOG.md with the date, the spec commit hash, split, test, trade count, mean R, confidence interval and verdict.
- **Output:** report.md with a table per test and split, R equity curves, and the full trade list as CSV.
- **Off-limits:**
  - Changing any definition, filter or cost after seeing a result.
  - Running a split twice or opening the holdout early.
  - Adding the 1H bias, an EMA filter or any new rule to rescue a failing test. Those ideas go in a v2 spec with a new holdout.
  - Testing Asia or any other session in this version.
- **If A or B passes:** write the forward-test script before trading it, in the same style as the ORB one, and judge it only on the pre-registered criteria.
