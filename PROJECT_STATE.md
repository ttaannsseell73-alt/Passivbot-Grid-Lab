# PROJECT STATE — LOCKED CHECKPOINT

Locked at: 2026-09-24 15:31 TRT

## Canonical track

GRID V2 remains the active project in this repository.
ScalpHunter remains a separate project and must not be mixed into GRID V2 unless explicitly reopened.

## Upstream lock

- enarjord/passivbot
- v8.1.0
- pinned commit: `7af64f3e930f4cf0cbb5fb88f31e9ce9594b0eb9`

## GRID V2 — TEST #01 Native Forager baseline

Current status: **BOT STARTUP-READY / NO TRADING EVIDENCE YET**

Baseline:
- equity: **4994.38271713 USDT**
- timestamp: **2026-09-24T10:37:59.408729Z**
- positions: 0
- open orders: 0
- unrealized PnL: 0

Latest evidence snapshot:
- positions: 0
- open orders: 0
- NET TEST P/L: **+0.00000000 USDT**
- NET RETURN: **+0.00000%**
- bot reached `startup-ready`

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
- no Forager shortlist/entry evidence yet
- no positions/open orders yet

Interpretation:
- this is currently a market-data / Forager-readiness bottleneck
- it is **not** profitability evidence
- do not declare TEST #01 profitable or unprofitable until shortlist, entries, fills, and mark-to-market equity evidence exist

Next engineering action remains on this exact line:
- bound/fix candle refresh pressure
- preserve the full locked experiment
- do not change the TEST #01 strategy logic merely to make the bot trade

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
