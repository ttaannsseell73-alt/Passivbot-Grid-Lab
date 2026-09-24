#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

MARKER = "GRID_V2_BOUNDED_FORAGER_RANKING"

SCALAR_OLD = """        tasks = {s: asyncio.create_task(one(s)) for s in syms}
        out = {}
        n = len(syms)
        started_ms = utc_ms()
        for sym, task in tasks.items():
            try:
                val = await task
            except Exception:
                val = None
            if val is not None:
                out[sym] = float(val)
"""

SCALAR_NEW = """        out = {}
        n = len(syms)
        started_ms = utc_ms()
        # GRID_V2_BOUNDED_FORAGER_RANKING
        # Bound cache/EMA task fan-out separately from the network-fetch budget.
        # The original code spawned one task per approved symbol, which can make
        # hundreds of coroutines contend on CandlestickManager locks at once.
        ranking_concurrency = max(
            1,
            min(
                n or 1,
                int(self._candle_fetch_concurrency(context="forager_ranking")),
            ),
        )
        for offset in range(0, n, ranking_concurrency):
            batch = syms[offset : offset + ranking_concurrency]
            tasks = {s: asyncio.create_task(one(s)) for s in batch}
            for sym, task in tasks.items():
                try:
                    val = await task
                except Exception:
                    val = None
                if val is not None:
                    out[sym] = float(val)
"""

PAIR_OLD = """        tasks = {s: asyncio.create_task(one(s)) for s in syms}
        volumes: Dict[str, float] = {}
        log_ranges: Dict[str, float] = {}
        started_ms = utc_ms()
        for sym, task in tasks.items():
            try:
                res = await task
            except Exception:
                res = None
            if res is None:
                continue
            vol, lr = res
            volumes[sym] = float(vol)
            log_ranges[sym] = float(lr)
"""

PAIR_NEW = """        volumes: Dict[str, float] = {}
        log_ranges: Dict[str, float] = {}
        started_ms = utc_ms()
        # GRID_V2_BOUNDED_FORAGER_RANKING
        # Preserve ranking math and fetch budgets; only bound coroutine fan-out.
        n = len(syms)
        ranking_concurrency = max(
            1,
            min(
                n or 1,
                int(self._candle_fetch_concurrency(context="forager_ranking")),
            ),
        )
        for offset in range(0, n, ranking_concurrency):
            batch = syms[offset : offset + ranking_concurrency]
            tasks = {s: asyncio.create_task(one(s)) for s in batch}
            for sym, task in tasks.items():
                try:
                    res = await task
                except Exception:
                    res = None
                if res is None:
                    continue
                vol, lr = res
                volumes[sym] = float(vol)
                log_ranges[sym] = float(lr)
"""


def patch_text(text: str) -> tuple[str, dict]:
    if MARKER in text:
        return text, {"already_patched": True, "scalar": 0, "pair": 0}

    scalar_count = text.count(SCALAR_OLD)
    pair_count = text.count(PAIR_OLD)
    if scalar_count != 2 or pair_count != 1:
        raise RuntimeError(
            f"unexpected pinned source shape: scalar={scalar_count} pair={pair_count}"
        )

    patched = text.replace(SCALAR_OLD, SCALAR_NEW).replace(PAIR_OLD, PAIR_NEW)
    compile(patched, "<patched-passivbot>", "exec")
    return patched, {
        "already_patched": False,
        "scalar": scalar_count,
        "pair": pair_count,
    }


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
            "RANKING-PATCH-CHECK-PASS "
            f"already={report['already_patched']} "
            f"scalar={report['scalar']} pair={report['pair']}"
        )
        return

    if patched != original:
        backup = path.with_suffix(path.suffix + ".gridv2-ranking.bak")
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_text(patched, encoding="utf-8")
        print(f"RANKING-PATCH-PASS backup={backup}")
    else:
        print("RANKING-PATCH-PASS already-patched")


if __name__ == "__main__":
    main()
