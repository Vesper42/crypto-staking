# Crypto Staking Monitor 🐱

Portfolio staking monitor yang jalan bareng AI Trader Bot.

## Fitur

- **Portfolio Tracking** — Monitor SOL + USDT staking positions
- **DCA Alerts** — Notifikasi otomatis kalau SOL turun 5%+ dari harga beli
- **Rebalance Alerts** — Kalau porsi SOL:USDT geser >10% dari target
- **Reward Reminder** — Reminder mingguan buat klaim & restake
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

## Cron Jobs (via Hermes)

- Daily DCA check: `0 8 * * *` (08:00 WIB)
- Weekly rebalance: `0 9 * * 1` (Senin 09:00 WIB)
- Weekly reward reminder: `0 10 * * 1` (Senin 10:00 WIB)

## Architecture

```
crypto-staking/
├── config.py              # Load .env config
├── run_check.py           # Main runner (cron target)
├── src/
│   ├── price_fetcher.py   # CCXT price data (Tokocrypto)
│   ├── staking_tracker.py # Portfolio calc, alerts logic
│   ├── notifier.py        # Telegram send
│   └── storage.py         # SQLite persistence
└── logs/
    └── staking.sqlite     # Price history, alerts log
```
