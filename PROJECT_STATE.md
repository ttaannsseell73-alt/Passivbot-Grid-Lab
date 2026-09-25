# PROJECT STATE — LOCKED CHECKPOINT

Locked at: 2026-09-25 13:10 TRT
Engineering checkpoint updated: 2026-09-25 13:42 TRT
Reconfirmed after remote-runner handoff: 2026-09-25

## Canonical track

GRID V2 remains the active project in this repository.
ScalpHunter remains a separate project and must not be mixed into GRID V2 unless explicitly reopened.

## Upstream lock

- enarjord/passivbot
- v8.1.0
- pinned commit: `7af64f3e930f4cf0cbb5fb88f31e9ce9594b0eb9`

## GRID V2 — TEST #01 Native Forager baseline

Current status: **TRADING EVIDENCE CONFIRMED / 3 OPEN POSITIONS**

Baseline:
- equity: **4994.38271713 USDT**
- timestamp: **2026-09-24T10:37:59.408729Z**
- positions: 0
- open orders: 0
- unrealized PnL: 0

Latest evidence snapshot — 2026-09-25 13:51 TRT:
- positions: **3**
- open orders: **0**
- wallet: **4994.36714536 USDT**
- equity: **4993.24094784 USDT**
- unrealized PnL: **-1.12619752 USDT**
- NET TEST P/L: **-1.14176929 USDT**
- NET RETURN: **-0.02286%**
- AKE long: qty 204, entry 0.0403305, mark 0.03536449, uPnL -1.01306400
- BROCCOLI714 short: qty 201, entry 0.02985, mark 0.03127951, uPnL -0.28733352
- NIL long: qty 67, entry 0.1225, mark 0.1251, uPnL +0.17420000
- bot reached `startup-ready` and subsequently produced real Forager selection/order/fill evidence

Locked TEST #01 configuration:
- Binance USD-M Demo/Test
- dynamic universe: all eligible LONG / all eligible SHORT
- currently observed approved universe: 527 long / 527 short
- 5 LONG slots / 5 SHORT slots
- leverage: 3x
- TWEL: 30% long / 30% short
- Forager weights: EMA readiness 45%, volatility 40%, volume 15%
- Direction Bridge: OFF
- HSL: enabled, unified
- single-instance protection: ON
- no time-based forced closing

## Current technical blocker

The process is alive and startup-ready, but the full 527-market universe is producing a large candle-fetch lock storm.

Observed evidence:
- repeated `fetch_lock_hold_timeout`
- affects both 1m and 1h candle surfaces
- Forager shortlist/entry evidence is now confirmed
- the lock storm still exists, but it did not prevent TEST #01 from eventually selecting candidates and opening positions

Interpretation:
- this is currently a market-data / Forager-readiness bottleneck
- it is **not** profitability evidence
- shortlist, entries, fills, and mark-to-market equity evidence now exist; current snapshot is a small loss, not a final verdict

Next engineering action remains on this exact line:
- bound/fix candle refresh pressure
- preserve the full locked experiment
- do not change the TEST #01 strategy logic merely to make the bot trade

## Candle bottleneck engineering checkpoint — 2026-09-25

Root-cause narrowing:
- the earlier `GRID_V2_BOUNDED_FORAGER_RANKING` patch is already present on the runner baseline
- the broad Forager candidate refresh loop itself is sequential and is not the source of the hundreds-task storm
- pinned upstream `src/passivbot.py` still contains an unbounded orchestrator EMA fan-out when `fetch_delay_s == 0`: one `load_symbol_bundle()` task per ordered symbol
- this code path is consistent with the observed simultaneous 1h/1m lock-hold watchdog storm across many distinct symbols

Prepared canonical fix:
- `runtime-tools/patch-orchestrator-concurrency.py`
- marker: `GRID_V2_BOUNDED_ORCHESTRATOR_EMA`
- preserves EMA math, Forager weights, shortlist rules, candle validity requirements, fetch budget, leverage, TWEL, and slot counts
- only changes coroutine fan-out: orchestrator EMA work is processed in bounded batches using Passivbot's existing candle concurrency control
- patch is fail-closed against an unexpected pinned source shape and is idempotent
- dedicated unit test added
- ranking patch test fixture repaired
- repository CI is GREEN after these changes

Deployment status:
- **NOT DEPLOYED TO THE LOCAL PASSIVBOT SOURCE**
- no claim is made that the candle storm is fixed yet
- guarded deployment mode `deploy-orchestrator-test01` is committed
- self-hosted `gridv2` runner is now online and connected
- deploy guard executed and correctly refused the patch because TEST #01 had 3 open positions
- therefore the running experiment was left untouched
- patch remains staged for the next verified flat state (`POSITIONS = 0` and `OPEN ORDERS = 0`)
- once flat: apply patch -> compile -> verify both bounded markers -> preflight universe -> restart unchanged TEST #01 -> collect post-patch lock/Forager evidence

## First confirmed Native Forager trading evidence — 2026-09-25

Selection:
- LONG slots=5: selected included NIL, AKE, FLOCK (+2)
- LONG top scores observed: NIL 0.855, AKE 0.727, FLOCK 0.627
- SHORT slots=5: selected included FLOCK, PHA, BROCCOLI714 (+2)
- SHORT top scores observed: FLOCK 0.582, PHA 0.579, BROCCOLI714 0.558

Orders posted:
- AKE buy long 204 @ 0.0403305
- BROCCOLI714 sell short 201 @ 0.02984
- NIL buy long 67 @ 0.1225

Confirmed positions later:
- AKE long 204
- BROCCOLI714 short 201
- NIL long 67

Interpretation:
- TEST #01 has now proven the native Forager can rank the 527-market universe sufficiently to select candidates and create real Binance Demo positions
- this is an execution/readiness milestone, not profitability proof
- current mark-to-market snapshot is slightly negative
- do not flatten positions merely to apply the staged candle-concurrency patch
- allow the running TEST #01 position lifecycle to continue under the locked rules

## GRID V2 — TEST #02 Direction/Quality Gate shadow evaluation — 2026-09-26

Execution:
- read-only shadow evaluation; no exchange orders were created
- same canonical Passivbot 1h candle cache
- 526 cached symbols, 516 symbols with eligible events
- 50,692 causal direction events
- direction features only: EMA spread 45%, EMA slope 30%, 6h momentum 25%
- quality gate: score threshold 0.18, >=2/3 directional votes, 48h contiguous history
- sampled every 4h; forward evaluation at 1h / 4h / 12h
- assumed round-trip cost: 4 bps
- CI GREEN and pre/post account snapshot confirmed TEST #01 account was untouched

TEST #01 entry audit under TEST #02 gate:
- AKE LONG -> TEST #02 = NEUTRAL, score -0.0727 -> would veto
- BROCCOLI714 SHORT -> TEST #02 = LONG, score +0.3253 -> would veto
- NIL LONG -> TEST #02 = NEUTRAL, score +0.1628 -> would veto
- therefore all three existing TEST #01 entries would have been blocked by the Direction/Quality Gate

Broad historical evidence:
- overall 1h gross hit rate: 41.44%; trimmed gross mean -0.0625%
- overall 4h gross hit rate: 45.45%; 1% trimmed gross mean +0.0634%; after 4 bps approx +0.0234%
- overall 12h gross hit rate: 47.27%; 1% trimmed gross mean +0.2182%; after 4 bps approx +0.1782%
- LONG 4h: hit 48.70%; 1% trimmed gross mean +0.1678%; after 4 bps approx +0.1278%
- LONG 12h: hit 51.53%; 1% trimmed gross mean +0.5280%; after 4 bps approx +0.4880%
- SHORT 4h: hit 41.98%; 1% trimmed gross mean -0.0404%; after 4 bps approx -0.0804%
- SHORT 12h: hit 42.70%; 1% trimmed gross mean -0.0862%; after 4 bps approx -0.1262%

Interpretation / lock:
- TEST #02 is **NOT a clean standalone direction-engine PASS**
- it shows useful veto behavior on the actual TEST #01 entries
- medium-horizon LONG evidence is positive but not strong enough to treat as proven
- SHORT direction evidence is negative and must not be promoted
- canonical role for this version of Direction is **VETO / QUALITY GATE CANDIDATE**, not signal generator
- do not promote TEST #02 to real-order execution from this evidence alone
- TEST #01 live positions remain untouched

## Locked TEST ladder

1. TEST #01 — Native Forager baseline
2. TEST #02 — Forager + Direction/Quality Gate
3. TEST #03 — add Price Action
4. TEST #04 — add Quant validation
5. TEST #05 — combined own GRID V2

All tests must use comparable risk/leverage/cost assumptions and be compared on true net equity P/L.

## Locked measurement

Primary economic metric:

`NET TEST P/L = current/final mark-to-market equity - starting equity`

Reports must include:
- starting/current equity
- net P/L USDT and %
- realized PnL
- unrealized/floating PnL
- fees
- funding
- max drawdown % and USDT
- max capital/exposure used
- fill/trade count
- coin-by-coin PnL
- LONG/SHORT PnL

Rules:
- realized PnL alone is never the verdict
- observation duration never forces a position closed
- if positions remain open, report mark-to-market result
- if later manually flattened, report a separate flattened result

## ScalpHunter — separate locked checkpoint

- separate from GRID V2
- latest portable state: ScalpHunter-Lab v0.4 Portable Complete
- infrastructure tests: 29/29 PASS
- Binance public feed integration: pending
- Kronos weights: pending
- TLOB weights: pending
- real replay / OOS evidence: pending
- no model is considered proven until same-data, same-cost, out-of-sample/walk-forward comparison is completed

## Binding workflow rules

- no architecture churn
- no parallel alternative track unless explicitly requested
- do not mix GRID V2, ScalpHunter, Freqtrade, APGE, music, or other projects
- do not ask for Binance API keys again unless concrete evidence proves credentials are the issue
- do not claim profit without true mark-to-market equity evidence
- do not close positions because an observation period ended
- this file is the canonical continuation checkpoint
