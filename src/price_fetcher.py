"""Fetch crypto prices via CCXT. Reuses Tokocrypto/Binance pattern from ai-trader-bot."""
from __future__ import annotations

import time

import ccxt

from config import CONFIG

# Tokocrypto mirrors Binance API — ISP in Indonesia blocks api.binance.com
_TOKOCRYPTO_OVERRIDE = "https://www.tokocrypto.site/api/v3"


def _build_exchange() -> ccxt.Exchange:
    cls = getattr(ccxt, CONFIG.exchange_id)
    exchange = cls({"enableRateLimit": True, "options": {"defaultType": "spot"}})
    if CONFIG.exchange_id == "tokocrypto":
        exchange.urls["api"]["rest"]["binance"] = _TOKOCRYPTO_OVERRIDE
    return exchange


def fetch_price(symbol: str = "SOL/USDT") -> float:
    """Fetch current ticker price in USD."""
    exchange = _build_exchange()
    for attempt in range(3):
        try:
            ticker = exchange.fetch_ticker(symbol)
            return float(ticker["last"])
        except (ccxt.NetworkError, ccxt.ExchangeNotAvailable, ccxt.RequestTimeout):
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise
    return 0.0  # unreachable but satisfies type checker


def fetch_sol_price() -> float:
    """Convenience wrapper for SOL/USDT."""
    return fetch_price("SOL/USDT")
