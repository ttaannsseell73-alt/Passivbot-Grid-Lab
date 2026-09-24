# PROJECT STATE — GRID V2

## Canonical track
GRID V2 only. ScalpHunter is a separate project and must not be mixed into this repository.

## Upstream lock
- enarjord/passivbot
- v8.1.0
- 7af64f3e930f4cf0cbb5fb88f31e9ce9594b0eb9

## TEST #01 — Native Forager baseline
Status: STARTUP BLOCKED / BOT STOPPED

Baseline:
- equity: 4994.38271713 USDT
- timestamp: 2026-09-24T10:37:59.408729Z
- positions: 0
- open orders: 0

Configured TEST #01 intent:
- Binance USD-M Demo
- long + short
- 5 long slots / 5 short slots
- TWEL 30% long / 30% short
- Forager weights: EMA readiness 45%, volatility 40%, volume 15%
- approved universe: all eligible long / all eligible short
- Direction Bridge: OFF
- HSL: enabled, unified
- leverage: 3x
- no time-based forced closing

## Current blocker
Startup reaches the dynamic universe, loads 557 long and 557 short candidates, then fails in:

src/live/market_snapshot.py:get_snapshots

Pinned code raises RuntimeError when any requested ticker snapshot remains unavailable:

```
if any(symbol not in out for symbol in missing):
    missing_after = [symbol for symbol in missing if symbol not in out]
    raise RuntimeError(
        f"[market] ticker snapshots incomplete | exchange={self.exchange_name} "
        f"missing={len(missing_after)} symbols={','.join(missing_after[:12])}"
    )
```

Observed startup failure:
- origin: market_snapshot.py:get_snapshots:231
- error_type: RuntimeError
- bot restarts
- TEST #01 therefore has NOT begun trading.

Likely compatibility issue to prove before patching:
Binance Demo ticker coverage and the 557-symbol approved/cached market universe are not identical. One or more missing quotes currently abort the whole startup.

## Next engineering action
Add a diagnostic/fail-safe compatibility patch and tests so unavailable Demo symbols cannot silently contaminate the Forager universe or crash the whole process. Preserve fail-closed execution for symbols without fresh quotes.

## Locked measurement
Primary economic metric:
NET TEST P/L = current/final mark-to-market equity - starting equity

Final report must include:
- starting/current equity
- net P/L USDT and %
- realized and unrealized PnL
- fees
- funding
- max drawdown
- max exposure
- fill/trade count
- coin PnL
- long/short PnL

Observation duration must never force a position closed.
