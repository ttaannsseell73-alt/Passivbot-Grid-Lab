# TEST #01 startup failure — 2026-09-24

## Evidence
Passivbot started with:
- LONG + SHORT
- positions capacity 5L/5S
- TWEL 30%/30%
- 557 approved candidates per side
- REST polling against Binance Demo

State refresh completed far enough to establish:
- account balance 4994.382717 USDT
- all-symbol open-order sweep returned zero orders
- historical fills cache loaded

Then startup failed:
- reason=startup_error
- error_type=RuntimeError
- origin=market_snapshot.py:get_snapshots:231

## Source-level finding
At pinned upstream commit 7af64f3e930f4cf0cbb5fb88f31e9ce9594b0eb9, get_snapshots() raises RuntimeError whenever any requested ticker snapshot is still missing after retry.

The newer upstream line has been changed to a dedicated MarketSnapshotUnavailable exception, indicating this failure mode is treated upstream as transient/unavailable market data rather than a generic programmer error.

## Required behavior for GRID V2
- Never create an order for a symbol lacking a fresh valid quote.
- A small number of unavailable Demo symbols must not crash the entire 557-symbol scanner.
- Missing symbols must be visible in diagnostics and excluded/fail-closed.
- Do not weaken order-creation freshness checks.
- Do not upgrade upstream wholesale; apply the smallest evidence-backed compatibility change to the pinned baseline.
