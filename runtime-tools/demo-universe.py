#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

EXCHANGE_INFO = "https://demo-fapi.binance.com/fapi/v1/exchangeInfo"
BOOK_TICKER = "https://demo-fapi.binance.com/fapi/v1/ticker/bookTicker"
PRICE_TICKER = "https://demo-fapi.binance.com/fapi/v1/ticker/price"


def fetch_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Passivbot-Grid-Lab/1.0"})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def eligible_bases(exchange_info, book_tickers, price_tickers):
    book = {
        str(row.get("symbol")): row
        for row in book_tickers
        if isinstance(row, dict) and row.get("symbol")
    }
    prices = {
        str(row.get("symbol")): row
        for row in price_tickers
        if isinstance(row, dict) and row.get("symbol")
    }

    eligible = []
    rejected = {}

    for market in exchange_info.get("symbols", []):
        if not isinstance(market, dict):
            continue
        symbol = str(market.get("symbol") or "")
        base = str(market.get("baseAsset") or "")
        reasons = []

        if market.get("status") != "TRADING":
            reasons.append("status")
        if market.get("contractType") != "PERPETUAL":
            reasons.append("contract")
        if market.get("quoteAsset") != "USDT":
            reasons.append("quote")

        b = book.get(symbol)
        p = prices.get(symbol)
        try:
            bid = float((b or {}).get("bidPrice", 0))
            ask = float((b or {}).get("askPrice", 0))
            last = float((p or {}).get("price", 0))
        except (TypeError, ValueError):
            bid = ask = last = 0.0

        if not (bid > 0 and ask >= bid and last > 0):
            reasons.append("ticker")

        if base and not reasons:
            eligible.append(base)
        elif symbol:
            rejected[symbol] = reasons or ["base"]

    return sorted(set(eligible)), rejected


def update_config(path: Path, bases: list[str]):
    cfg = json.loads(path.read_text(encoding="utf-8"))
    live = cfg.get("live")
    if not isinstance(live, dict):
        raise RuntimeError("config missing live object")
    approved = live.get("approved_coins")
    if not isinstance(approved, dict):
        raise RuntimeError("config missing live.approved_coins object")

    approved["long"] = list(bases)
    approved["short"] = list(bases)

    backup = path.with_suffix(path.suffix + ".pre-demo-universe.bak")
    if not backup.exists():
        backup.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")

    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config")
    parser.add_argument("--report", default="runtime-tools/demo-universe-report.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    exchange_info = fetch_json(EXCHANGE_INFO)
    book_tickers = fetch_json(BOOK_TICKER)
    price_tickers = fetch_json(PRICE_TICKER)
    bases, rejected = eligible_bases(exchange_info, book_tickers, price_tickers)

    if not bases:
        raise RuntimeError("Demo universe preflight returned zero eligible markets")

    report = {
        "eligible_count": len(bases),
        "eligible_bases": bases,
        "rejected_count": len(rejected),
        "rejected": rejected,
        "source": {
            "exchangeInfo": EXCHANGE_INFO,
            "bookTicker": BOOK_TICKER,
            "priceTicker": PRICE_TICKER,
        },
    }

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if args.config and not args.dry_run:
        update_config(Path(args.config), bases)

    print(f"DEMO-UNIVERSE-PASS eligible={len(bases)} rejected={len(rejected)}")
    print(f"REPORT {report_path}")
    if args.config:
        print("CONFIG " + ("UNCHANGED" if args.dry_run else "UPDATED") + f" {args.config}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"DEMO-UNIVERSE-FAIL {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
