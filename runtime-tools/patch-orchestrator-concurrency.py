#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

MARKER = "GRID_V2_BOUNDED_ORCHESTRATOR_EMA"

OLD = """        else:
            symbol_tasks = [
                asyncio.create_task(load_symbol_bundle(sym)) for sym in ordered_symbols
            ]
            symbol_results = await asyncio.gather(*symbol_tasks, return_exceptions=True)
"""

NEW = """        else:
            # GRID_V2_BOUNDED_ORCHESTRATOR_EMA
            # Preserve EMA/candle semantics and fetch budgets; only bound coroutine
            # fan-out so a broad Forager universe cannot acquire hundreds of
            # symbol/timeframe candle locks before those tasks can make progress.
            ema_concurrency = max(
                1,
                min(
                    len(ordered_symbols) or 1,
                    int(self._candle_fetch_concurrency(context="orchestrator_ema")),
                ),
            )
            logging.debug(
                "[candle] orchestrator EMA bounded fan-out symbols=%d concurrency=%d",
                len(ordered_symbols),
                ema_concurrency,
            )
            symbol_results = []
            for offset in range(0, len(ordered_symbols), ema_concurrency):
                batch = ordered_symbols[offset : offset + ema_concurrency]
                symbol_tasks = [
                    asyncio.create_task(load_symbol_bundle(sym)) for sym in batch
                ]
                symbol_results.extend(
                    await asyncio.gather(*symbol_tasks, return_exceptions=True)
                )
"""


def patch_text(text: str) -> tuple[str, dict]:
    if MARKER in text:
        return text, {"already_patched": True, "matches": 0}

    count = text.count(OLD)
    if count != 1:
        raise RuntimeError(f"unexpected pinned source shape: orchestrator={count}")

    patched = text.replace(OLD, NEW)
    compile(patched, "<patched-passivbot>", "exec")
    return patched, {"already_patched": False, "matches": count}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--path",
        default="/home/tansel/Passivbot-Binance-Test/src/passivbot.py",
    )
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    path = Path(args.path)
    original = path.read_text(encoding="utf-8")
    patched, report = patch_text(original)

    if args.check_only:
        print(
            "ORCHESTRATOR-PATCH-CHECK-PASS "
            f"already={report['already_patched']} matches={report['matches']}"
        )
        return

    if patched != original:
        backup = path.with_suffix(path.suffix + ".gridv2-orchestrator.bak")
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_text(patched, encoding="utf-8")
        print(f"ORCHESTRATOR-PATCH-PASS backup={backup}")
    else:
        print("ORCHESTRATOR-PATCH-PASS already-patched")


if __name__ == "__main__":
    main()
