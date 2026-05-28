# Crypto Staking Monitor 🐱

Portfolio staking monitor yang jalan bareng AI Trader Bot.

## Posisi Staking (Aktif)

| Koin | Amount | Entry Price | APR | Duration |
|------|--------|-------------|-----|----------|
| SOL | 0.27 SOL | $81.14 | 4.95% | 120 hari |
| ATOM | 16.5 ATOM | $2.03 | 11.25% | 120 hari |

**Target Split:** 40% SOL / 60% ATOM  
**Total Modal:** ~Rp 1,000,000  
**Platform:** Tokocrypto  

## Fitur

- **Portfolio Tracking** — Monitor SOL + ATOM staking positions dengan live price
- **Auto-Compound** — Otomatis beli SOL pakai reward ATOM (kalau DRY_RUN=false)
- **DCA Alerts** — Notifikasi otomatis kalau SOL turun 5%+ dari harga beli
- **Rebalance Alerts** — Kalau porsi SOL:ATOM geser >10% dari target
- **Telegram Integration** — Kirim alerts via Telegram

## Setup

```bash
cp .env.example .env
# Edit .env dengan posisi staking kamu

python3 -m venv env
source env/bin/activate
pip install -r requirements.txt

# Init positions
python run_check.py --init

# Run check
python run_check.py

# Full report
python run_check.py --report
```

## Commands

```bash
python run_check.py              # Run all checks (compound, DCA, rebalance)
python run_check.py --report     # Full portfolio report
python run_check.py --init       # Initialize staking positions from .env
python run_check.py --compound   # Force compound check
python run_check.py --dca        # Force DCA analysis
python run_check.py --rebalance  # Force rebalance check
```

## Cron Jobs (via Hermes)

- **Daily check:** `0 8 * * *` (08:00 WIB) — compound + DCA + rebalance
- **Weekly rebalance:** `0 9 * * 1` (Senin 09:00 WIB)

## Architecture

```
crypto-staking/
├── config.py              # Load .env config
├── run_check.py           # Main runner (cron target)
├── .env.example           # Config template
├── requirements.txt       # Python deps (ccxt, requests, python-dotenv)
├── src/
│   ├── price_fetcher.py   # CCXT price data (Tokocrypto) — SOL & ATOM
│   ├── executor.py        # Trade executor (buy/sell SOL) — DRY_RUN gate
│   ├── staking_tracker.py # Portfolio calc, compound, DCA, rebalance logic
│   ├── notifier.py        # Telegram send (HTML escaped)
│   └── storage.py         # SQLite persistence
└── logs/
    └── staking.sqlite     # Price history, positions, alerts log
```

## Safety

- **DRY_RUN=true** (default) — nggak ada order real
- **TRADING_ENABLED=false** — double gate
- **MAX_TRADE_IDR=500000** — cap per trade
- **Auto-compound/DCA/Rebalance** — auto-execute OFF by default
- **.env di-gitignore** — credentials nggak ke-commit

## Estimasi Reward (per cycle 120 hari)

- SOL: +0.00417 SOL (~Rp 5,400)
- ATOM: +0.5798 ATOM (~Rp 41,700)
- **Total: ~Rp 47,100** per 120 hari

## Notes

- ATOM entry price = $2.03 (bukan $39 — harga real Mei 2026)
- ISP blocks api.binance.com → pakai Tokocrypto mirror
- Staking duration 120 hari untuk APR tertinggi
- Auto-subscribe ON di Tokocrypto (otomatis perpanjang)
