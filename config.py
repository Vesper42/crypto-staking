"""Centralized configuration for Crypto Staking Monitor."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw not in (None, "") else default


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw not in (None, "") else default


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Config:
    # Exchange
    exchange_id: str = os.getenv("EXCHANGE_ID", "tokocrypto")
    exchange_api_key: str = os.getenv("EXCHANGE_API_KEY", "")
    exchange_secret: str = os.getenv("EXCHANGE_SECRET", "")

    # Trading safety
    trading_enabled: bool = _bool("TRADING_ENABLED", False)
    dry_run: bool = _bool("DRY_RUN", True)
    max_trade_idr: float = _float("MAX_TRADE_IDR", 500000.0)

    # Staking positions
    sol_amount: float = _float("STAKING_SOL_AMOUNT", 0.0)
    sol_entry_price: float = _float("STAKING_SOL_ENTRY_PRICE", 0.0)
    sol_apy: float = _float("STAKING_SOL_APY", 0.0571)

    usdt_amount: float = _float("STAKING_USDT_AMOUNT", 0.0)
    usdt_apy: float = _float("STAKING_USDT_APY", 0.10)

    # Auto-compound
    auto_compound: bool = _bool("AUTO_COMPOUND", True)
    compound_min_idr: float = _float("COMPOUND_MIN_IDR", 10000.0)

    # DCA
    dca_enabled: bool = _bool("DCA_ENABLED", True)
    dca_dip_pct: float = _float("DCA_DIP_PCT", 0.05)
    dca_suggest_min_idr: float = _float("DCA_SUGGEST_MIN", 50000.0)
    dca_suggest_max_idr: float = _float("DCA_SUGGEST_MAX", 200000.0)
    dca_auto_buy: bool = _bool("DCA_AUTO_BUY", False)

    # Rebalance
    rebalance_enabled: bool = _bool("REBALANCE_ENABLED", True)
    rebalance_threshold_pct: float = _float("REBALANCE_THRESHOLD_PCT", 0.10)
    rebalance_interval_months: int = _int("REBALANCE_INTERVAL_MONTHS", 3)
    rebalance_auto_execute: bool = _bool("REBALANCE_AUTO_EXECUTE", False)
    target_sol_pct: float = _float("TARGET_SOL_PCT", 0.50)

    # Rate
    idr_usd: float = _float("IDR_USD_RATE", 16500.0)

    # Telegram
    telegram_enabled: bool = _bool("TELEGRAM_ENABLED", False)
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Platform
    platform: str = os.getenv("PLATFORM", "tokocrypto")

    # Paths
    logs_dir: Path = ROOT / "logs"
    db_path: Path = ROOT / "logs" / "staking.sqlite"


CONFIG = Config()
CONFIG.logs_dir.mkdir(parents=True, exist_ok=True)
