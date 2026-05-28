"""Staking portfolio tracker — rewards, rebalance, DCA alerts."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

from config import CONFIG
from src import storage
from src.price_fetcher import fetch_sol_price


@dataclass
class PortfolioSnapshot:
    sol_price_usd: float
    sol_value_idr: float
    usdt_value_idr: float
    total_value_idr: float
    sol_pct: float
    sol_change_from_entry_pct: float
    sol_daily_reward_idr: float
    usdt_daily_reward_idr: float
    total_monthly_reward_idr: float
    total_yearly_reward_idr: float


def calc_portfolio() -> PortfolioSnapshot:
    """Calculate current portfolio state."""
    sol_price = fetch_sol_price()

    # SOL value: original IDR stake adjusted by price change
    price_change = 0.0
    if CONFIG.sol_entry_price > 0:
        price_change = (sol_price - CONFIG.sol_entry_price) / CONFIG.sol_entry_price
    sol_value = CONFIG.sol_amount * (1 + price_change)

    usdt_value = CONFIG.usdt_amount  # stablecoin = no price change
    total = sol_value + usdt_value

    sol_pct = (sol_value / total) if total > 0 else 0

    # Staking rewards
    sol_daily = (CONFIG.sol_amount * CONFIG.sol_apy) / 365
    usdt_daily = (CONFIG.usdt_amount * CONFIG.usdt_apy) / 365
    monthly = (sol_daily + usdt_daily) * 30
    yearly = (sol_daily + usdt_daily) * 365

    return PortfolioSnapshot(
        sol_price_usd=sol_price,
        sol_value_idr=sol_value,
        usdt_value_idr=usdt_value,
        total_value_idr=total,
        sol_pct=sol_pct,
        sol_change_from_entry_pct=price_change,
        sol_daily_reward_idr=sol_daily,
        usdt_daily_reward_idr=usdt_daily,
        total_monthly_reward_idr=monthly,
        total_yearly_reward_idr=yearly,
    )


@dataclass
class Alert:
    type: str  # dca, rebalance, reward_reminder
    emoji: str
    title: str
    message: str
    action: str  # recommended action


def check_dca_alert(snap: PortfolioSnapshot) -> Alert | None:
    """Alert if SOL dropped significantly from entry price (buy the dip)."""
    if CONFIG.sol_entry_price <= 0:
        return None

    drop_pct = -snap.sol_change_from_entry_pct
    if drop_pct >= CONFIG.dca_dip_pct:
        # Suggest DCA amount based on drop severity
        suggested_idr = min(100_000, CONFIG.sol_amount * 0.2)  # 20% of current, max 100k
        if drop_pct >= 0.10:
            suggested_idr = min(200_000, CONFIG.sol_amount * 0.3)

        return Alert(
            type="dca",
            emoji="📉",
            title="SOL TURUN — DCA Opportunity!",
            message=(
                f"SOL turun {drop_pct*100:.1f}% dari harga beli kamu!\n"
                f"Harga beli: ${CONFIG.sol_entry_price:.2f}\n"
                f"Harga sekarang: ${snap.sol_price_usd:.2f}\n"
                f"Rekomendasi: tambah DCA ~Rp {suggested_idr:,.0f}"
            ),
            action=f"Beli SOL Rp {suggested_idr:,.0f} di Tokocrypto",
        )
    return None


def check_rebalance_alert(snap: PortfolioSnapshot) -> Alert | None:
    """Alert if portfolio allocation drifted too far from target."""
    target = CONFIG.target_sol_pct
    drift = abs(snap.sol_pct - target)

    if drift >= CONFIG.rebalance_threshold_pct:
        direction = "kelebihan SOL" if snap.sol_pct > target else "kekurangan SOL"
        total = snap.total_value_idr
        ideal_sol = total * target
        diff = abs(snap.sol_value_idr - ideal_sol)

        return Alert(
            type="rebalance",
            emoji="⚖️",
            title="Portfolio Imbalanced!",
            message=(
                f"SOL: {snap.sol_pct*100:.1f}% (target: {target*100:.0f}%)\n"
                f"{direction} sekitar Rp {diff:,.0f}\n"
                f"SOL value: Rp {snap.sol_value_idr:,.0f}\n"
                f"USDT value: Rp {snap.usdt_value_idr:,.0f}"
            ),
            action=f"Rebalance: {'jual' if snap.sol_pct > target else 'beli'} SOL ~Rp {diff:,.0f}",
        )
    return None


def check_reward_reminder(snap: PortfolioSnapshot) -> Alert | None:
    """Weekly reminder to claim and restake rewards."""
    now = datetime.now(timezone.utc)
    # Only fire on Mondays (weekday=0)
    if now.weekday() != 0:
        return None

    if storage.was_alert_sent_today("reward_reminder"):
        return None

    return Alert(
        type="reward_reminder",
        emoji="💰",
        title="Weekly Staking Reward Reminder",
        message=(
            f"Estimasi reward minggu ini:\n"
            f"SOL: ~Rp {snap.sol_daily_reward_idr * 7:,.0f}\n"
            f"USDT: ~Rp {snap.usdt_daily_reward_idr * 7:,.0f}\n"
            f"Total: ~Rp {(snap.sol_daily_reward_idr + snap.usdt_daily_reward_idr) * 7:,.0f}\n\n"
            f"Jangan lupa klaim & restake ya!"
        ),
        action="Klaim reward di Tokocrypto Earn, lalu stake ulang",
    )


def run_all_checks() -> list[Alert]:
    """Run all monitoring checks and return active alerts."""
    snap = calc_portfolio()

    # Log price
    storage.record_price("SOL/USDT", snap.sol_price_usd, snap.sol_change_from_entry_pct)

    # Update staking positions in DB
    storage.upsert_position("SOL", CONFIG.sol_amount, CONFIG.sol_entry_price, CONFIG.sol_apy)
    storage.upsert_position("USDT", CONFIG.usdt_amount, 0, CONFIG.usdt_apy)

    # Accumulate daily rewards
    storage.update_reward("SOL", snap.sol_daily_reward_idr)
    storage.update_reward("USDT", snap.usdt_daily_reward_idr)

    alerts = []
    for checker in [check_dca_alert, check_rebalance_alert, check_reward_reminder]:
        alert = checker(snap)
        if alert:
            alerts.append(alert)

    return alerts


def format_portfolio_report(snap: PortfolioSnapshot) -> str:
    """Format a human-readable portfolio status."""
    pnl_emoji = "📈" if snap.sol_change_from_entry_pct >= 0 else "📉"
    lines = [
        f"{'='*40}",
        f"🏦 STAKING PORTFOLIO REPORT",
        f"{'='*40}",
        f"",
        f"SOL @ ${snap.sol_price_usd:.2f}",
        f"  Entry: ${CONFIG.sol_entry_price:.2f} ({pnl_emoji} {snap.sol_change_from_entry_pct*100:+.1f}%)",
        f"  Staked: Rp {CONFIG.sol_amount:,.0f} → Rp {snap.sol_value_idr:,.0f}",
        f"  APY: {CONFIG.sol_apy*100:.2f}%",
        f"",
        f"USDT",
        f"  Staked: Rp {CONFIG.usdt_amount:,.0f}",
        f"  APY: {CONFIG.usdt_apy*100:.1f}%",
        f"",
        f"{'—'*40}",
        f"Total Value: Rp {snap.total_value_idr:,.0f}",
        f"Allocation: SOL {snap.sol_pct*100:.1f}% / USDT {(1-snap.sol_pct)*100:.1f}%",
        f"Target: SOL {CONFIG.target_sol_pct*100:.0f}% / USDT {(1-CONFIG.target_sol_pct)*100:.0f}%",
        f"",
        f"💰 REWARDS",
        f"  Daily: Rp {snap.sol_daily_reward_idr + snap.usdt_daily_reward_idr:,.0f}",
        f"  Monthly: Rp {snap.total_monthly_reward_idr:,.0f}",
        f"  Yearly: Rp {snap.total_yearly_reward_idr:,.0f}",
    ]
    return "\n".join(lines)
