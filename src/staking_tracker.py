"""Staking portfolio tracker — auto-compound, DCA analysis, rebalance execution."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from config import CONFIG
from src import storage
from src.price_fetcher import fetch_sol_price, fetch_atom_price
from src.executor import execute_buy, execute_sell, TradeResult


@dataclass
class PortfolioSnapshot:
    sol_price_usd: float
    atom_price_usd: float
    sol_value_idr: float
    atom_value_idr: float
    total_value_idr: float
    sol_pct: float
    sol_change_from_entry_pct: float
    atom_change_from_entry_pct: float
    sol_daily_reward_idr: float
    atom_daily_reward_idr: float
    total_monthly_reward_idr: float
    total_yearly_reward_idr: float


@dataclass
class ActionResult:
    action: str          # compound / dca / rebalance / info
    emoji: str
    title: str
    message: str
    executed: bool       # True if auto-executed
    trade_result: TradeResult | None = None


def calc_portfolio() -> PortfolioSnapshot:
    """Calculate current portfolio state."""
    sol_price = fetch_sol_price()
    atom_price = fetch_atom_price()

    # SOL value with price change
    sol_price_change = 0.0
    if CONFIG.sol_entry_price > 0:
        sol_price_change = (sol_price - CONFIG.sol_entry_price) / CONFIG.sol_entry_price
    sol_value = CONFIG.sol_amount * sol_price * CONFIG.idr_usd  # coin amount × price × rate

    # ATOM value with price change
    atom_price_change = 0.0
    if CONFIG.atom_entry_price > 0:
        atom_price_change = (atom_price - CONFIG.atom_entry_price) / CONFIG.atom_entry_price
    atom_value = CONFIG.atom_amount * atom_price * CONFIG.idr_usd  # coin amount × price × rate

    total = sol_value + atom_value
    sol_pct = (sol_value / total) if total > 0 else 0

    # Daily rewards in IDR (coin_amount × price × rate × APY / 365)
    sol_daily = (CONFIG.sol_amount * sol_price * CONFIG.idr_usd * CONFIG.sol_apy) / 365
    atom_daily = (CONFIG.atom_amount * atom_price * CONFIG.idr_usd * CONFIG.atom_apy) / 365
    monthly = (sol_daily + atom_daily) * 30
    yearly = (sol_daily + atom_daily) * 365

    return PortfolioSnapshot(
        sol_price_usd=sol_price,
        atom_price_usd=atom_price,
        sol_value_idr=sol_value,
        atom_value_idr=atom_value,
        total_value_idr=total,
        sol_pct=sol_pct,
        sol_change_from_entry_pct=sol_price_change,
        atom_change_from_entry_pct=atom_price_change,
        sol_daily_reward_idr=sol_daily,
        atom_daily_reward_idr=atom_daily,
        total_monthly_reward_idr=monthly,
        total_yearly_reward_idr=yearly,
    )


# ──────────────────────────────────────────────
# 1. AUTO-COMPOUND
# ──────────────────────────────────────────────

def check_auto_compound(snap: PortfolioSnapshot) -> ActionResult | None:
    """Estimate accumulated staking rewards and suggest/auto-execute restake.

    Since Tokocrypto doesn't expose staking API via CCXT, we:
    - Track rewards in DB (accumulated daily)
    - When reward > compound_min_idr → suggest restake
    - If AUTO_COMPOUND=true AND DRY_RUN=false → auto-buy SOL with reward
    """
    if not CONFIG.auto_compound:
        return None

    # Calculate accumulated reward since last compound
    positions = storage.get_positions()
    sol_pos = next((p for p in positions if p["asset"] == "SOL"), None)
    atom_pos = next((p for p in positions if p["asset"] == "ATOM"), None)

    sol_reward = sol_pos["accumulated_reward_idr"] if sol_pos else 0
    atom_reward = atom_pos["accumulated_reward_idr"] if atom_pos else 0
    total_reward = sol_reward + atom_reward

    if total_reward < CONFIG.compound_min_idr:
        return None  # Not enough to compound yet

    # Decide what to do with the reward
    # Strategy: buy more SOL with the ATOM reward portion
    trade = None
    executed = False

    if CONFIG.auto_compound and total_reward >= CONFIG.compound_min_idr:
        # Auto-buy SOL with accumulated ATOM reward
        trade = execute_buy(atom_reward)
        executed = trade.success

        if executed:
            # Reset accumulated reward in DB
            if atom_pos:
                storage.update_reward("ATOM", -atom_reward)
            # Update SOL position
            new_sol_amount = CONFIG.sol_amount + trade.quantity * trade.price * CONFIG.idr_usd
            CONFIG.sol_amount = new_sol_amount

    msg_lines = [
        f"Accumulated rewards: Rp {total_reward:,.0f}",
        f"  SOL staking: Rp {sol_reward:,.0f}",
        f"  ATOM staking: Rp {atom_reward:,.0f}",
    ]
    if executed and trade:
        msg_lines.append(f"Auto-compound: bought {trade.quantity:.6f} SOL @ ${trade.price:.2f}")
        msg_lines.append(f"Cost: Rp {atom_reward:,.0f}")
    else:
        msg_lines.append("Suggest: klaim reward & beli SOL manual di Tokocrypto")

    return ActionResult(
        action="compound",
        emoji="🔄",
        title="Auto-Compound Reward",
        message="\n".join(msg_lines),
        executed=executed,
        trade_result=trade,
    )


# ──────────────────────────────────────────────
# 2. DCA ANALYSIS
# ──────────────────────────────────────────────

def check_dca(snap: PortfolioSnapshot) -> ActionResult | None:
    """Analyze SOL price for DCA opportunity.

    Triggers when SOL drops dca_dip_pct% from entry price.
    Suggests buy amount based on drop severity.
    Can auto-execute if DCA_AUTO_BUY=true.
    """
    if not CONFIG.dca_enabled or CONFIG.sol_entry_price <= 0:
        return None

    drop_pct = -snap.sol_change_from_entry_pct
    if drop_pct < CONFIG.dca_dip_pct:
        return None  # No dip detected

    # Scale suggestion with drop severity
    if drop_pct >= 0.15:
        suggested = min(300_000, CONFIG.dca_suggest_max_idr * 1.5)
        urgency = "TURUN BANGET! 🚨"
    elif drop_pct >= 0.10:
        suggested = min(200_000, CONFIG.dca_suggest_max_idr)
        urgency = "Turun cukup dalam 📉"
    else:
        suggested = CONFIG.dca_suggest_min_idr
        urgency = "Mulai turun 📊"

    trade = None
    executed = False

    if CONFIG.dca_auto_buy:
        trade = execute_buy(suggested)
        executed = trade.success
        if executed:
            CONFIG.sol_amount += suggested
            CONFIG.sol_entry_price = snap.sol_price_usd  # update avg entry

    msg_lines = [
        f"{urgency}",
        f"SOL turun {drop_pct*100:.1f}% dari harga beli",
        f"Entry: ${CONFIG.sol_entry_price:.2f} → Now: ${snap.sol_price_usd:.2f}",
        "",
    ]
    if executed and trade:
        msg_lines.append(f"Auto-DCA: beli {trade.quantity:.6f} SOL @ ${trade.price:.2f}")
        msg_lines.append(f"Nominal: Rp {suggested:,.0f}")
    else:
        msg_lines.append(f"Rekomendasi: tambah DCA ~Rp {suggested:,.0f}")
        msg_lines.append(f"beli SOL di Tokocrypto sekarang")

    return ActionResult(
        action="dca",
        emoji="📉",
        title="DCA Opportunity Detected!",
        message="\n".join(msg_lines),
        executed=executed,
        trade_result=trade,
    )


# ──────────────────────────────────────────────
# 3. REBALANCE
# ──────────────────────────────────────────────

def check_rebalance(snap: PortfolioSnapshot) -> ActionResult | None:
    """Check if portfolio needs rebalancing.

    Triggers when allocation drifts > threshold from target.
    Can auto-execute trades to rebalance.
    """
    if not CONFIG.rebalance_enabled:
        return None

    target = CONFIG.target_sol_pct
    drift = abs(snap.sol_pct - target)
    if drift < CONFIG.rebalance_threshold_pct:
        return None  # Within acceptable range

    # Calculate trade needed
    total = snap.total_value_idr
    ideal_sol = total * target
    diff_idr = snap.sol_value_idr - ideal_sol  # positive = too much SOL

    trade = None
    executed = False

    if CONFIG.rebalance_auto_execute:
        if diff_idr > 0:
            # Too much SOL → sell some
            sol_to_sell = diff_idr / (snap.sol_price_usd * CONFIG.idr_usd)
            trade = execute_sell(sol_to_sell)
            executed = trade.success
            if executed:
                CONFIG.sol_amount -= diff_idr
                CONFIG.atom_amount += diff_idr
        else:
            # Too little SOL → buy some
            buy_amount = abs(diff_idr)
            trade = execute_buy(buy_amount)
            executed = trade.success
            if executed:
                CONFIG.sol_amount += buy_amount
                CONFIG.atom_amount -= buy_amount

    direction = "jual SOL → ATOM" if diff_idr > 0 else "beli SOL ← ATOM"
    msg_lines = [
        f"Portfolio geser dari target!",
        f"SOL: {snap.sol_pct*100:.1f}% (target: {target*100:.0f}%)",
        f"Drift: {drift*100:.1f}%",
        f"Aksi: {direction} ~Rp {abs(diff_idr):,.0f}",
        "",
        f"SOL value: Rp {snap.sol_value_idr:,.0f}",
        f"ATOM value: Rp {snap.atom_value_idr:,.0f}",
    ]
    if executed and trade:
        msg_lines.append(f"\nAuto-rebalance: {trade.action} {trade.quantity:.6f} SOL @ ${trade.price:.2f}")
    else:
        msg_lines.append("\nSuggest: rebalance manual di Tokocrypto")

    return ActionResult(
        action="rebalance",
        emoji="⚖️",
        title="Rebalance Needed!",
        message="\n".join(msg_lines),
        executed=executed,
        trade_result=trade,
    )


# ──────────────────────────────────────────────
# RUN ALL
# ──────────────────────────────────────────────

def run_all_checks() -> list[ActionResult]:
    """Run all monitoring checks, return active results."""
    snap = calc_portfolio()

    # Log price
    storage.record_price("SOL/USDT", snap.sol_price_usd, snap.sol_change_from_entry_pct)

    # Update positions in DB
    storage.upsert_position("SOL", CONFIG.sol_amount, CONFIG.sol_entry_price, CONFIG.sol_apy)
    storage.upsert_position("ATOM", CONFIG.atom_amount, CONFIG.atom_entry_price, CONFIG.atom_apy)

    # Accumulate daily rewards
    storage.update_reward("SOL", snap.sol_daily_reward_idr)
    storage.update_reward("ATOM", snap.atom_daily_reward_idr)

    results = []
    for checker in [check_auto_compound, check_dca, check_rebalance]:
        result = checker(snap)
        if result:
            results.append(result)

    return results


def format_portfolio_report(snap: PortfolioSnapshot) -> str:
    """Human-readable portfolio status."""
    sol_pnl_emoji = "📈" if snap.sol_change_from_entry_pct >= 0 else "📉"
    atom_pnl_emoji = "📈" if snap.atom_change_from_entry_pct >= 0 else "📉"
    lines = [
        "=" * 40,
        "🏦 STAKING PORTFOLIO",
        "=" * 40,
        "",
        f"SOL @ ${snap.sol_price_usd:.2f}",
        f"  Entry: ${CONFIG.sol_entry_price:.2f} ({sol_pnl_emoji} {snap.sol_change_from_entry_pct*100:+.1f}%)",
        f"  Staked: {CONFIG.sol_amount} SOL → Rp {snap.sol_value_idr:,.0f}",
        f"  APY: {CONFIG.sol_apy*100:.2f}%",
        "",
        f"ATOM @ ${snap.atom_price_usd:.2f}",
        f"  Entry: ${CONFIG.atom_entry_price:.2f} ({atom_pnl_emoji} {snap.atom_change_from_entry_pct*100:+.1f}%)",
        f"  Staked: {CONFIG.atom_amount} ATOM → Rp {snap.atom_value_idr:,.0f}",
        f"  APY: {CONFIG.atom_apy*100:.2f}%",
        "",
        "—" * 40,
        f"Total: Rp {snap.total_value_idr:,.0f}",
        f"Split: SOL {snap.sol_pct*100:.1f}% / ATOM {(1-snap.sol_pct)*100:.1f}%",
        f"Target: SOL {CONFIG.target_sol_pct*100:.0f}% / ATOM {(1-CONFIG.target_sol_pct)*100:.0f}%",
        "",
        "💰 REWARDS",
        f"  Daily: Rp {snap.sol_daily_reward_idr + snap.atom_daily_reward_idr:,.0f}",
        f"  Monthly: Rp {snap.total_monthly_reward_idr:,.0f}",
        f"  Yearly: Rp {snap.total_yearly_reward_idr:,.0f}",
        "",
        "⚙️ FEATURES",
        f"  Auto-compound: {'ON' if CONFIG.auto_compound else 'OFF'}",
        f"  DCA alerts: {'ON' if CONFIG.dca_enabled else 'OFF'}",
        f"  Auto DCA buy: {'ON' if CONFIG.dca_auto_buy else 'OFF'}",
        f"  Rebalance: {'ON' if CONFIG.rebalance_enabled else 'OFF'}",
        f"  Auto rebalance: {'ON' if CONFIG.rebalance_auto_execute else 'OFF'}",
        f"  {'🧪 DRY RUN' if CONFIG.dry_run else '🔴 LIVE'}",
    ]
    return "\n".join(lines)
