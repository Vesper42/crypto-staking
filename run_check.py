#!/usr/bin/env python3
"""Crypto Staking Monitor — main runner.

Usage:
    python run_check.py              # Run all checks (compound, DCA, rebalance)
    python run_check.py --report     # Full portfolio report
    python run_check.py --init       # Initialize staking positions from .env
    python run_check.py --compound   # Force compound check
    python run_check.py --dca        # Force DCA analysis
    python run_check.py --rebalance  # Force rebalance check
"""
from __future__ import annotations

import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from config import CONFIG  # noqa: E402
from src import storage  # noqa: E402
from src.staking_tracker import (  # noqa: E402
    calc_portfolio, run_all_checks, format_portfolio_report,
    check_auto_compound, check_dca, check_rebalance,
)
from src.notifier import send  # noqa: E402


def init_positions():
    """Seed staking positions from .env config."""
    storage.init_db()
    storage.upsert_position("SOL", CONFIG.sol_amount, CONFIG.sol_entry_price, CONFIG.sol_apy)
    storage.upsert_position("USDT", CONFIG.usdt_amount, 0, CONFIG.usdt_apy)
    print(f"Positions initialized:")
    print(f"  SOL: Rp {CONFIG.sol_amount:,.0f} @ ${CONFIG.sol_entry_price:.2f} ({CONFIG.sol_apy*100:.2f}% APY)")
    print(f"  USDT: Rp {CONFIG.usdt_amount:,.0f} ({CONFIG.usdt_apy*100:.1f}% APY)")
    print(f"  DRY_RUN: {CONFIG.dry_run}")
    print(f"  Auto-compound: {CONFIG.auto_compound}")
    print(f"  DCA auto-buy: {CONFIG.dca_auto_buy}")
    print(f"  Rebalance auto: {CONFIG.rebalance_auto_execute}")


def run_check():
    """Run all monitoring checks, send alerts if needed."""
    storage.init_db()
    results = run_all_checks()

    if results:
        for r in results:
            # Deduplicate alerts (don't send same type twice per day)
            if not storage.was_alert_sent_today(r.action):
                send(r.message)
                storage.record_alert(r.action, r.message)
                status = "EXECUTED" if r.executed else "ALERT"
                print(f"[{status}] {r.emoji} {r.title}")
                print(r.message)
                print()
            else:
                print(f"[SKIP] {r.action}: already sent today")
    else:
        print("No actions needed — portfolio on track")

    # Always print compact status
    snap = calc_portfolio()
    print(f"\nSOL ${snap.sol_price_usd:.2f} | "
          f"Total Rp {snap.total_value_idr:,.0f} | "
          f"SOL {snap.sol_pct*100:.1f}% | "
          f"Rewards Rp {snap.sol_daily_reward_idr + snap.usdt_daily_reward_idr:,.0f}/day")


def run_report():
    """Full portfolio report."""
    storage.init_db()
    snap = calc_portfolio()
    report = format_portfolio_report(snap)
    print(report)
    send(report)


def force_compound():
    """Force compound check (ignoring dedup)."""
    storage.init_db()
    snap = calc_portfolio()
    result = check_auto_compound(snap)
    if result:
        print(f"{result.emoji} {result.title}")
        print(result.message)
    else:
        print("No compound — rewards below threshold")


def force_dca():
    """Force DCA analysis."""
    storage.init_db()
    snap = calc_portfolio()
    result = check_dca(snap)
    if result:
        print(f"{result.emoji} {result.title}")
        print(result.message)
    else:
        print(f"No DCA opportunity — SOL {snap.sol_change_from_entry_pct*100:+.1f}% from entry")


def force_rebalance():
    """Force rebalance check."""
    storage.init_db()
    snap = calc_portfolio()
    result = check_rebalance(snap)
    if result:
        print(f"{result.emoji} {result.title}")
        print(result.message)
    else:
        print(f"Portfolio balanced — SOL {snap.sol_pct*100:.1f}% (target {CONFIG.target_sol_pct*100:.0f}%)")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""

    if arg == "--init":
        init_positions()
    elif arg == "--report":
        run_report()
    elif arg == "--compound":
        force_compound()
    elif arg == "--dca":
        force_dca()
    elif arg == "--rebalance":
        force_rebalance()
    else:
        run_check()
