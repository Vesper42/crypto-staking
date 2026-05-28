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


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Config:
    # Exchange (price data only)
    exchange_id: str = os.getenv("EXCHANGE_ID", "tokocrypto")

    # Staking positions
    sol_amount: float = _float("STAKING_SOL_AMOUNT", 0.0)
    sol_entry_price: float = _float("STAKING_SOL_ENTRY_PRICE", 0.0)
    sol_apy: float = _float("STAKING_SOL_APY", 0.0571)

    usdt_amount: float = _float("STAKING_USDT_AMOUNT", 0.0)
    usdt_apy: float = _float("STAKING_USDT_APY", 0.10)

    # Alert thresholds
    dca_dip_pct: float = _float("DCA_DIP_PCT", 0.05)
    rebalance_threshold_pct: float = _float("REBALANCE_THRESHOLD_PCT", 0.10)
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
