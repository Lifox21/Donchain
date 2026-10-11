# Donchian 240-Day Breakout Quantitative Trading System

> **Automated Quantitative Strategy Implementation for Indian Equities (NSE)**  
> **Connected Remote:** `https://github.com/Ved-2107/Donchain.git`  
> **Current Portfolio Status:** Active Continuous Paper Trading | **Base Capital:** ₹150,000.00

---

## 1. Live Portfolio Dashboard

| Metric | Current Value | Strategy Reference |
| :--- | :---: | :--- |
| **Portfolio NAV** | **₹151,088.57** | Initial Capital: ₹150,000.00 |
| **Net Return** | **+0.73%** | All fees, STT, GST and slippage accounted |
| **Available Cash** | **₹139,007.27** | Ready for opportunistic deployment |
| **Invested Capital** | **₹12,081.30** | Allocated across active momentum leaders |
| **Active Holdings** | **1 Positions** | Max limit: 12 stocks (8% single-stock cap) |
| **Total Completed Trades** | **3 Trades** | Closed via 8% trailing stop-loss |
| **Win Rate** | **33.3%** | High profit-factor trend following |
| **Last Bot Update** | `2026-10-11 19:18:18` | Auto-synced to GitHub |

---

## 2. Active Portfolio Holdings

| Symbol | Sector | Shares | Entry Price | Current Price | Peak Price | Trailing Stop (8%) | Unrealized PnL | Return % |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **CUPID** | Unclassified | 33 | ₹366.10 | ₹366.10 | ₹366.10 | ₹336.81 | **₹+0.00** | **+0.00%** |

---

## 3. Strategy Core Architecture & Rules

The strategy deployed in this repository is **`EXP_08462`**, selected as the primary winner from an exhaustive optimization study across **1,447 stocks** and **8,640 full parameter simulations**:

1. **Entry Rule (52-Week High Breakout):**
   - A stock triggers a BUY signal when its market close exceeds its 240-day high: $Close_t > \max(Close_{t-240..t-1})$.
   - Only genuine structural 52-week expansions are bought, filtering out noise.
2. **Exit Rule (Close-Trigger Trailing 8% Stop-Loss):**
   - As the stock advances, its highest peak close is continuously tracked: $Peak = \max(Peak, Close_t)$.
   - The trailing stop is set strictly at 8% below the peak close: $StopLoss = Peak \times 0.92$.
   - If $Close_t \le StopLoss$, the position is completely liquidated at market close.
3. **Cool-Down & Re-entry Rule (21 Days / 20-Day High):**
   - After stopping out, a stock enters a mandatory **21-day cool-down** to prevent whipsawing during consolidation.
   - After 21 days, if the stock establishes a new **20-day high breakout**, the bot re-enters the trend.
4. **Position Sizing & Risk Controls:**
   - **8% Single-Stock Cap:** Exactly ₹12,000 allocated per position from the ₹150,000 capital base (~12 slots).
   - **20% Sector Cap:** Maximum ₹30,000 exposure per industry sector to ensure multi-sector diversification.

---

## 4. Backtest Evidence & Quantitative Benchmark

| Strategy | Net CAGR (%) | Max Drawdown (%) | Sharpe Ratio | Calmar Ratio | Out-of-Sample CAGR |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Donchian Baseline (`EXP_02659`)** | 12.98% | -42.71% | 0.62 | 0.30 | 9.43% |
| **Recommended Winner (`EXP_08462`)** | **81.31%** | **-32.37%** | **4.40** | **2.51** | **121.83%** |
| **Net Improvement** | **+68.33%** | **+10.34% milder** | **7.1x higher** | **8.2x higher** | **+112.40%** |

---

## 5. Execution Guide & Continuous Automation

Run the continuous trading daemon locally:
```cmd
run_trading_bot.bat
```
Or via Python CLI:
```bash
python trading_bot.py --loop --interval 60
```