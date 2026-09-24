import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "runtime-tools" / "demo-universe.py"
spec = importlib.util.spec_from_file_location("demo_universe", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_filters_to_tradeable_perpetual_usdt_with_valid_quotes():
    exchange = {
        "symbols": [
            {"symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT", "status": "TRADING", "contractType": "PERPETUAL"},
            {"symbol": "OLDUSDT", "baseAsset": "OLD", "quoteAsset": "USDT", "status": "BREAK", "contractType": "PERPETUAL"},
            {"symbol": "ETHUSDC", "baseAsset": "ETH", "quoteAsset": "USDC", "status": "TRADING", "contractType": "PERPETUAL"},
            {"symbol": "BADUSDT", "baseAsset": "BAD", "quoteAsset": "USDT", "status": "TRADING", "contractType": "PERPETUAL"},
        ]
    }
    books = [
        {"symbol": "BTCUSDT", "bidPrice": "100", "askPrice": "101"},
        {"symbol": "OLDUSDT", "bidPrice": "1", "askPrice": "1.1"},
        {"symbol": "ETHUSDC", "bidPrice": "10", "askPrice": "11"},
        {"symbol": "BADUSDT", "bidPrice": "5", "askPrice": "4"},
    ]
    prices = [
        {"symbol": "BTCUSDT", "price": "100.5"},
        {"symbol": "OLDUSDT", "price": "1.05"},
        {"symbol": "ETHUSDC", "price": "10.5"},
        {"symbol": "BADUSDT", "price": "4.5"},
    ]

    eligible, rejected = mod.eligible_markets(exchange, books, prices)

    assert eligible == [
        {
            "identifier": "binance::BTCUSDT",
            "native_symbol": "BTCUSDT",
            "base": "BTC",
        }
    ]
    assert "OLDUSDT" in rejected
    assert "ETHUSDC" in rejected
    assert "BADUSDT" in rejected


def test_keeps_distinct_native_markets_even_when_base_alias_matches():
    exchange = {
        "symbols": [
            {"symbol": "ABCUSDT", "baseAsset": "ABC", "quoteAsset": "USDT", "status": "TRADING", "contractType": "PERPETUAL"},
            {"symbol": "1000ABCUSDT", "baseAsset": "ABC", "quoteAsset": "USDT", "status": "TRADING", "contractType": "PERPETUAL"},
        ]
    }
    books = [
        {"symbol": "ABCUSDT", "bidPrice": "100", "askPrice": "101"},
        {"symbol": "1000ABCUSDT", "bidPrice": "10", "askPrice": "11"},
    ]
    prices = [
        {"symbol": "ABCUSDT", "price": "100.5"},
        {"symbol": "1000ABCUSDT", "price": "10.5"},
    ]

    eligible, _ = mod.eligible_markets(exchange, books, prices)
    identifiers = [row["identifier"] for row in eligible]

    assert identifiers == ["binance::1000ABCUSDT", "binance::ABCUSDT"]
