"""Trade executor — buy/sell SOL on Tokocrypto via CCXT.

Safety features (borrowed from ai-trader-bot pattern):
- TRADING_ENABLED gate: no real orders unless explicitly true
- DRY_RUN: paper-trade mode (default)
- Precision handling via exchange native rules
- Max trade size cap
- Order fill polling
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import ccxt

from config import CONFIG

# Tokocrypto mirrors Binance — ISP blocks api.binance.com
_TOKOCRYPTO_OVERRIDE = "https://www.tokocrypto.site/api/v3"


@dataclass
class TradeResult:
    success: bool
    action: str  # BUY / SELL
    symbol: str
    quantity: float
    price: float
    cost_idr: float
    order_id: str
    dry_run: bool
    error: str = ""


def _build_exchange(authenticated: bool = True) -> ccxt.Exchange:
    """Build CCXT exchange client."""
    kwargs: dict[str, Any] = {"enableRateLimit": True, "options": {"defaultType": "spot"}}
    if authenticated and CONFIG.trading_enabled:
        kwargs["apiKey"] = CONFIG.exchange_api_key
        kwargs["secret"] = CONFIG.exchange_secret

    cls = getattr(ccxt, CONFIG.exchange_id)
    exchange = cls(kwargs)

    if CONFIG.exchange_id == "tokocrypto":
        exchange.urls["api"]["rest"]["binance"] = _TOKOCRYPTO_OVERRIDE

    return exchange


def _to_precision(exchange: ccxt.Exchange, symbol: str, *, amount=None, price=None):
    """Round to exchange-native precision."""
    try:
        exchange.load_markets()
    except Exception:
        pass
    out = {}
    if amount is not None:
        out["amount"] = float(exchange.amount_to_precision(symbol, amount))
    if price is not None:
        out["price"] = float(exchange.price_to_precision(symbol, price))
    return out


def execute_buy(sol_amount_idr: float) -> TradeResult:
    """Buy SOL with IDR (via SOL/USDT).

    Args:
        sol_amount_idr: How much IDR worth of SOL to buy
    """
    symbol = "SOL/USDT"
    exchange = _build_exchange(authenticated=CONFIG.trading_enabled)

    # Fetch current price
    ticker = exchange.fetch_ticker(symbol)
    price = float(ticker["last"])

    # Convert IDR → USDT → SOL quantity
    usdt_amount = sol_amount_idr / CONFIG.idr_usd
    raw_qty = usdt_amount / price

    # Cap at max trade size
    max_usdt = CONFIG.max_trade_idr / CONFIG.idr_usd
    if usdt_amount > max_usdt:
        usdt_amount = max_usdt
        raw_qty = usdt_amount / price

    if CONFIG.dry_run or not CONFIG.trading_enabled:
        return TradeResult(
            success=True, action="BUY", symbol=symbol,
            quantity=raw_qty, price=price,
            cost_idr=sol_amount_idr, order_id="DRY-BUY",
            dry_run=True,
        )

    # LIVE execution
    try:
        precise = _to_precision(exchange, symbol, amount=raw_qty, price=price * 1.001)
        order = exchange.create_limit_buy_order(symbol, precise["amount"], precise["price"])
        order_id = order.get("id", "unknown")

        # Wait for fill
        final = _wait_fill(exchange, symbol, order_id)
        filled = float(final.get("filled") or 0.0)
        fill_price = float(final.get("average") or price)

        return TradeResult(
            success=filled > 0, action="BUY", symbol=symbol,
            quantity=filled, price=fill_price,
            cost_idr=filled * fill_price * CONFIG.idr_usd,
            order_id=order_id, dry_run=False,
        )
    except Exception as e:
        return TradeResult(
            success=False, action="BUY", symbol=symbol,
            quantity=0, price=price, cost_idr=0,
            order_id="", dry_run=False, error=str(e),
        )


def execute_sell(sol_quantity: float) -> TradeResult:
    """Sell SOL for USDT.

    Args:
        sol_quantity: How many SOL tokens to sell
    """
    symbol = "SOL/USDT"
    exchange = _build_exchange(authenticated=CONFIG.trading_enabled)

    ticker = exchange.fetch_ticker(symbol)
    price = float(ticker["last"])

    if CONFIG.dry_run or not CONFIG.trading_enabled:
        proceeds_idr = sol_quantity * price * CONFIG.idr_usd
        return TradeResult(
            success=True, action="SELL", symbol=symbol,
            quantity=sol_quantity, price=price,
            cost_idr=proceeds_idr, order_id="DRY-SELL",
            dry_run=True,
        )

    # LIVE execution
    try:
        precise = _to_precision(exchange, symbol, amount=sol_quantity, price=price * 0.999)
        order = exchange.create_limit_sell_order(symbol, precise["amount"], precise["price"])
        order_id = order.get("id", "unknown")

        final = _wait_fill(exchange, symbol, order_id)
        filled = float(final.get("filled") or 0.0)
        fill_price = float(final.get("average") or price)

        return TradeResult(
            success=filled > 0, action="SELL", symbol=symbol,
            quantity=filled, price=fill_price,
            cost_idr=filled * fill_price * CONFIG.idr_usd,
            order_id=order_id, dry_run=False,
        )
    except Exception as e:
        return TradeResult(
            success=False, action="SELL", symbol=symbol,
            quantity=0, price=price, cost_idr=0,
            order_id="", dry_run=False, error=str(e),
        )


def _wait_fill(exchange: ccxt.Exchange, symbol: str, order_id: str, timeout: int = 30) -> dict:
    """Poll order until filled or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            order = exchange.fetch_order(order_id, symbol)
            if order.get("status") in ("closed", "canceled", "expired", "rejected"):
                return order
        except Exception:
            pass
        time.sleep(2)
    return {"status": "timeout", "filled": 0, "average": 0}


def get_sol_balance() -> float:
    """Get SOL balance from exchange. Returns 0 in dry-run."""
    if CONFIG.dry_run or not CONFIG.trading_enabled:
        return 0.0
    try:
        exchange = _build_exchange()
        bal = exchange.fetch_balance()
        return float(bal.get("SOL", {}).get("free", 0.0))
    except Exception:
        return 0.0
