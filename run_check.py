#!/usr/bin/env python3
"""Crypto Staking Monitor — main runner for cron jobs.

Usage:
    python run_check.py              # Check portfolio + alerts
    python run_check.py --report     # Full portfolio report
    python run_check.py --init       # Initialize staking positions from .env
"""
from __future__ import annotations

import sys
import os

# Setup path
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from config import CONFIG  # noqa: E402
from src import storage  # noqa: E402
from src.staking_tracker import calc_portfolio, run_all_checks, format_portfolio_report  # noqa: E402
from src.notifier import send, send_alert  # noqa: E402


def init_positions():
    """Seed staking positions from .env config."""
    storage.init_db()
    storage.upsert_position("SOL", CONFIG.sol_amount, CONFIG.sol_entry_price, CONFIG.sol_apy)
    storage.upsert_position("USDT", CONFIG.usdt_amount, 0, CONFIG.usdt_apy)
    print(f"✅ Positions initialized:")
    print(f"   SOL: Rp {CONFIG.sol_amount:,.0f} @ ${CONFIG.sol_entry_price:.2f} ({CONFIG.sol_apy*100:.2f}% APY)")
    print(f"   USDT: Rp {CONFIG.usdt_amount:,.0f} ({CONFIG.usdt_apy*100:.1f}% APY)")


def run_check():
    """Run monitoring checks, send alerts if needed."""
    storage.init_db()
    alerts = run_all_checks()

    if alerts:
        for alert in alerts:
            # Deduplicate: don't send same alert type twice in one day
            if not storage.was_alert_sent_today(alert.type):
                send_alert(alert.emoji, alert.title, alert.message, alert.action)
                storage.record_alert(alert.type, alert.message)
                print(f"🔔 {alert.type}: {alert.title}")
            else:
                print(f"⏭️  {alert.type}: already sent today")
    else:
        print("✅ No alerts — portfolio on track")


def run_report():
    """Print full portfolio report."""
    storage.init_db()
    snap = calc_portfolio()
    report = format_portfolio_report(snap)
    print(report)
    send(report)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""

    if arg == "--init":
        init_positions()
    elif arg == "--report":
        run_report()
    else:
        run_check()
