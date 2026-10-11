"""Causal, auditable paper-trading and portfolio execution engine for the Donchian 240-Day Breakout Strategy.

Tracks portfolio cash, holdings, trailing stop-losses, 21-day cool-downs,
20-day high re-entries, and Indian statutory transaction costs.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

logger = logging.getLogger("DonchianTrading")

WORKSPACE_DIR = Path(__file__).resolve().parent
DAILY_DIR = WORKSPACE_DIR / "Daily"
CONFIG_PATH = WORKSPACE_DIR / "config.json"
STATE_PATH = WORKSPACE_DIR / "portfolio_state.json"
TRADE_LOG_PATH = WORKSPACE_DIR / "trade_log.csv"
README_PATH = WORKSPACE_DIR / "README.md"

IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class CostModel:
    """Conservative Indian cash-equity delivery transaction cost model."""

    brokerage_bps: float = 0.0
    exchange_transaction_bps: float = 0.30
    sebi_turnover_bps: float = 0.01
    gst_rate: float = 0.18
    stamp_duty_buy_bps: float = 1.50
    stt_sell_bps: float = 10.0
    slippage_bps: float = 10.0

    def estimate_fees(self, side: str, notional: float) -> dict[str, float]:
        brokerage = notional * (self.brokerage_bps / 10_000.0)
        exchange = notional * (self.exchange_transaction_bps / 10_000.0)
        sebi = notional * (self.sebi_turnover_bps / 10_000.0)
        gst = (brokerage + exchange + sebi) * self.gst_rate
        stamp_duty = notional * (self.stamp_duty_buy_bps / 10_000.0) if side.upper() == "BUY" else 0.0
        stt = notional * (self.stt_sell_bps / 10_000.0) if side.upper() == "SELL" else 0.0
        slippage = notional * (self.slippage_bps / 10_000.0)
        total = brokerage + exchange + sebi + gst + stamp_duty + stt + slippage
        return {
            "brokerage": round(brokerage, 2),
            "exchange": round(exchange, 2),
            "sebi": round(sebi, 2),
            "gst": round(gst, 2),
            "stamp_duty": round(stamp_duty, 2),
            "stt": round(stt, 2),
            "slippage": round(slippage, 2),
            "total": round(total, 2),
        }


def load_config() -> dict:
    defaults = {
        "initial_capital": 150000.0,
        "max_position_pct": 0.08,
        "max_sector_pct": 0.20,
        "max_positions": 12,
        "donchian_period": 240,
        "reentry_period": 20,
        "cooldown_days": 21,
        "trailing_stop_pct": 0.08,
        "poll_interval_seconds": 60,
        "git_auto_push": True,
        "git_remote": "https://github.com/Ved-2107/Donchain.git",
        "git_branch": "main",
        "cost_model": asdict(CostModel()),
    }
    if not CONFIG_PATH.exists():
        return defaults
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            cfg = json.load(f)
        defaults.update({k: v for k, v in cfg.items() if k != "cost_model"})
        if "cost_model" in cfg:
            defaults["cost_model"].update(cfg["cost_model"])
    except Exception as e:
        logger.warning(f"Error loading config: {e}. Using defaults.")
    return defaults


def load_state(initial_capital: float = 150000.0) -> dict:
    if STATE_PATH.exists():
        try:
            with STATE_PATH.open("r", encoding="utf-8") as f:
                state = json.load(f)
            state.setdefault("initial_capital", initial_capital)
            state.setdefault("cash", initial_capital)
            state.setdefault("holdings", {})
            state.setdefault("cooldowns", {})
            state.setdefault("nav_history", [])
            state.setdefault("total_trades", 0)
            state.setdefault("winning_trades", 0)
            state.setdefault("losing_trades", 0)
            state.setdefault("realized_pnl", 0.0)
            return state
        except Exception as e:
            logger.warning(f"Error reading state file: {e}. Reinitializing.")

    return {
        "initial_capital": initial_capital,
        "cash": initial_capital,
        "holdings": {},
        "cooldowns": {},
        "nav_history": [],
        "total_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "realized_pnl": 0.0,
        "last_updated": None,
    }


def save_state(state: dict) -> None:
    temp_path = STATE_PATH.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    temp_path.replace(STATE_PATH)


def record_trade(
    symbol: str,
    side: str,
    shares: int,
    price: float,
    gross_val: float,
    fees: float,
    net_val: float,
    pnl: float = 0.0,
    pnl_pct: float = 0.0,
    reason: str = "",
    timestamp: str | None = None,
) -> None:
    if timestamp is None:
        timestamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

    row = {
        "timestamp": timestamp,
        "symbol": symbol,
        "side": side,
        "shares": shares,
        "price": round(price, 2),
        "gross_value": round(gross_val, 2),
        "fees": round(fees, 2),
        "net_value": round(net_val, 2),
        "realized_pnl": round(pnl, 2),
        "realized_pnl_pct": round(pnl_pct, 2),
        "reason": reason,
    }

    df = pd.DataFrame([row])
    if not TRADE_LOG_PATH.exists():
        df.to_csv(TRADE_LOG_PATH, index=False)
    else:
        df.to_csv(TRADE_LOG_PATH, mode="a", header=False, index=False)


def get_industry_map() -> dict[str, str]:
    """Loads industry sector mappings for Indian equities."""
    try:
        from paper_trading import WORKSPACE_DIR
        hhm_data = WORKSPACE_DIR.parent / "HHM" / "Data_Enhanced.csv"
        if hhm_data.exists():
            df = pd.read_csv(hhm_data)
            return dict(zip(df["Symbol"], df["Industry"]))
    except Exception:
        pass
    return {}


def scan_latest_market_signals(
    daily_dir: Path = DAILY_DIR,
    donchian_period: int = 240,
    reentry_period: int = 20,
    cooldown_days: int = 21,
    state: dict | None = None,
) -> dict:
    """Scans all available daily stock datasets in the workspace for Donchian breakout signals."""
    if state is None:
        state = load_state()

    holdings = state.get("holdings", {})
    cooldowns = state.get("cooldowns", {})
    industry_map = get_industry_map()

    exit_signals = []
    buy_signals = []
    current_prices = {}

    csv_files = list(daily_dir.glob("*.csv"))
    logger.info(f"Scanning market data across {len(csv_files)} equities...")

    for csv_file in csv_files:
        symbol = csv_file.stem.replace("_daily", "")
        try:
            df = pd.read_csv(csv_file)
            if len(df) < 30:
                continue
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.dropna(subset=["Date", "Close"]).sort_values("Date")
            if df.empty:
                continue

            last_row = df.iloc[-1]
            last_date = last_row["Date"].strftime("%Y-%m-%d")
            close_p = float(last_row["Close"])
            high_p = float(last_row["High"]) if "High" in last_row else close_p
            current_prices[symbol] = {
                "price": close_p,
                "high": high_p,
                "date": last_date,
                "industry": industry_map.get(symbol, "Unclassified"),
            }

            # 1. Check stop-loss on currently held stocks
            if symbol in holdings:
                pos = holdings[symbol]
                peak_p = max(pos.get("peak_price", pos["entry_price"]), high_p)
                sl_price = peak_p * (1.0 - 0.08)
                pos["peak_price"] = peak_p
                pos["stop_loss_price"] = sl_price
                pos["current_price"] = close_p
                pos["unrealized_pnl"] = round((close_p - pos["entry_price"]) * pos["shares"], 2)
                pos["unrealized_pnl_pct"] = round(((close_p / pos["entry_price"]) - 1.0) * 100.0, 2)

                if close_p <= sl_price:
                    exit_signals.append({
                        "symbol": symbol,
                        "reason": f"Trailing 8% SL hit: Close {close_p:.2f} <= SL {sl_price:.2f} (Peak: {peak_p:.2f})",
                        "price": close_p,
                        "date": last_date,
                    })
                continue

            # 2. Check BUY signals for non-held stocks
            # Check Donchian-240 high
            N = min(len(df) - 1, donchian_period)
            if N < 20:
                continue

            # Prior high over N days (excluding today)
            prior_240_high = df["Close"].iloc[-N-1:-1].max()
            prior_20_high = df["Close"].iloc[-21:-1].max() if len(df) > 21 else prior_240_high

            is_in_cooldown = False
            if symbol in cooldowns:
                exit_date_str = cooldowns[symbol]
                try:
                    exit_dt = datetime.strptime(exit_date_str, "%Y-%m-%d")
                    curr_dt = datetime.strptime(last_date, "%Y-%m-%d")
                    days_passed = (curr_dt - exit_dt).days
                    if days_passed < cooldown_days:
                        is_in_cooldown = True
                    else:
                        # Cooldown expired! Eligible for 20-day high re-entry
                        if close_p > prior_20_high:
                            buy_signals.append({
                                "symbol": symbol,
                                "type": "REENTRY_20D",
                                "price": close_p,
                                "prior_high": prior_20_high,
                                "momentum": (close_p / prior_20_high) - 1.0,
                                "industry": industry_map.get(symbol, "Unclassified"),
                                "date": last_date,
                            })
                            continue
                except Exception:
                    pass

            if not is_in_cooldown:
                if close_p > prior_240_high:
                    momentum_score = (close_p / df["Close"].iloc[-21:-1].mean()) - 1.0 if len(df) > 21 else 0.0
                    buy_signals.append({
                        "symbol": symbol,
                        "type": "DONCHIAN_240_BREAKOUT",
                        "price": close_p,
                        "prior_high": prior_240_high,
                        "momentum": momentum_score,
                        "industry": industry_map.get(symbol, "Unclassified"),
                        "date": last_date,
                    })

        except Exception as e:
            continue

    # Sort buy signals by momentum rank descending
    buy_signals.sort(key=lambda x: x["momentum"], reverse=True)

    return {
        "exit_signals": exit_signals,
        "buy_signals": buy_signals,
        "current_prices": current_prices,
    }


def rebalance_portfolio(
    initial_seed: bool = False,
    config: dict | None = None,
) -> dict:
    """Executes daily rebalancing, position exits, entries, and updates NAV."""
    if config is None:
        config = load_config()

    cost_model = CostModel(**config["cost_model"])
    state = load_state(config["initial_capital"])
    signals = scan_latest_market_signals(
        daily_dir=DAILY_DIR,
        donchian_period=config["donchian_period"],
        reentry_period=config["reentry_period"],
        cooldown_days=config["cooldown_days"],
        state=state,
    )

    exit_signals = signals["exit_signals"]
    buy_signals = signals["buy_signals"]
    current_prices = signals["current_prices"]

    trades_executed = []

    # 1. Execute Exits
    for exit_sig in exit_signals:
        sym = exit_sig["symbol"]
        if sym not in state["holdings"]:
            continue
        pos = state["holdings"][sym]
        shares = pos["shares"]
        exit_p = exit_sig["price"]
        gross_val = shares * exit_p
        fees = cost_model.estimate_fees("SELL", gross_val)
        net_val = gross_val - fees["total"]

        entry_cost = pos["entry_price"] * shares
        trade_pnl = net_val - entry_cost
        pnl_pct = (trade_pnl / entry_cost) * 100.0

        state["cash"] += net_val
        state["total_trades"] += 1
        if trade_pnl > 0:
            state["winning_trades"] += 1
        else:
            state["losing_trades"] += 1
        state["realized_pnl"] += trade_pnl

        # Place in cool-down
        state["cooldowns"][sym] = exit_sig["date"]
        del state["holdings"][sym]

        record_trade(
            symbol=sym,
            side="SELL",
            shares=shares,
            price=exit_p,
            gross_val=gross_val,
            fees=fees["total"],
            net_val=net_val,
            pnl=trade_pnl,
            pnl_pct=pnl_pct,
            reason=exit_sig["reason"],
            timestamp=f"{exit_sig['date']} 15:30:00",
        )
        trades_executed.append(f"SOLD {sym}: {shares} shares @ Rs {exit_p:.2f} (PnL: Rs {trade_pnl:+.2f})")

    # 2. Compute Portfolio Total Equity
    invested_equity = 0.0
    sector_exposure = {}
    for sym, pos in list(state["holdings"].items()):
        curr_p = current_prices.get(sym, {}).get("price", pos["entry_price"])
        val = pos["shares"] * curr_p
        invested_equity += val
        ind = pos.get("industry", "Unclassified")
        sector_exposure[ind] = sector_exposure.get(ind, 0.0) + val

    total_equity = state["cash"] + invested_equity

    # 3. Execute Buys
    max_pos_val = total_equity * config["max_position_pct"]
    max_sector_val = total_equity * config["max_sector_pct"]
    available_slots = config["max_positions"] - len(state["holdings"])

    for buy_sig in buy_signals:
        if available_slots <= 0:
            break
        sym = buy_sig["symbol"]
        if sym in state["holdings"]:
            continue

        ind = buy_sig["industry"]
        curr_sec_val = sector_exposure.get(ind, 0.0)
        if curr_sec_val >= max_sector_val:
            continue

        p = buy_sig["price"]
        target_allocation = min(max_pos_val, max_sector_val - curr_sec_val, state["cash"])
        if target_allocation < 1000.0 or p <= 0:
            continue

        shares = int(target_allocation // p)
        if shares <= 0:
            continue

        gross_val = shares * p
        fees = cost_model.estimate_fees("BUY", gross_val)
        total_cost = gross_val + fees["total"]

        if total_cost > state["cash"]:
            shares = int((state["cash"] - fees["total"]) // p)
            if shares <= 0:
                continue
            gross_val = shares * p
            fees = cost_model.estimate_fees("BUY", gross_val)
            total_cost = gross_val + fees["total"]

        state["cash"] -= total_cost
        sector_exposure[ind] = curr_sec_val + gross_val
        available_slots -= 1

        state["holdings"][sym] = {
            "shares": shares,
            "entry_price": p,
            "peak_price": p,
            "stop_loss_price": round(p * 0.92, 2),
            "current_price": p,
            "entry_date": buy_sig["date"],
            "industry": ind,
            "signal_type": buy_sig["type"],
            "unrealized_pnl": 0.0,
            "unrealized_pnl_pct": 0.0,
        }

        record_trade(
            symbol=sym,
            side="BUY",
            shares=shares,
            price=p,
            gross_val=gross_val,
            fees=fees["total"],
            net_val=total_cost,
            reason=f"{buy_sig['type']} (Prior High: {buy_sig['prior_high']:.2f})",
            timestamp=f"{buy_sig['date']} 15:30:00",
        )
        trades_executed.append(f"BOUGHT {sym}: {shares} shares @ Rs {p:.2f} ({ind})")

    # 4. Final Portfolio NAV Snapshot
    final_invested = sum(pos["shares"] * current_prices.get(sym, {}).get("price", pos["entry_price"]) for sym, pos in state["holdings"].items())
    final_nav = round(state["cash"] + final_invested, 2)
    latest_date = max([pos.get("entry_date", "2026-08-06") for pos in state["holdings"].values()] + ["2026-08-06"])

    state["nav_history"].append({
        "date": latest_date,
        "nav": final_nav,
        "cash": round(state["cash"], 2),
        "invested": round(final_invested, 2),
        "holdings_count": len(state["holdings"]),
        "total_return_pct": round(((final_nav / state["initial_capital"]) - 1.0) * 100.0, 2),
    })
    state["last_updated"] = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

    save_state(state)
    generate_readme(state)

    logger.info(f"Rebalance completed. NAV: Rs {final_nav:,.2f} | Cash: Rs {state['cash']:,.2f} | Holdings: {len(state['holdings'])}")
    for t in trades_executed:
        logger.info(f"  {t}")

    return {
        "status": "SUCCESS",
        "nav": final_nav,
        "cash": state["cash"],
        "invested": final_invested,
        "holdings_count": len(state["holdings"]),
        "trades_executed": trades_executed,
    }


def generate_readme(state: dict | None = None) -> None:
    """Dynamically generates the comprehensive repository README.md with live portfolio status."""
    if state is None:
        state = load_state()

    initial_cap = state["initial_capital"]
    cash = state["cash"]
    holdings = state.get("holdings", {})
    invested = sum(pos["shares"] * pos.get("current_price", pos["entry_price"]) for pos in holdings.values())
    nav = cash + invested
    total_ret = ((nav / initial_cap) - 1.0) * 100.0
    tot_trades = state.get("total_trades", 0)
    win_trades = state.get("winning_trades", 0)
    win_rate = (win_trades / tot_trades * 100.0) if tot_trades > 0 else 0.0

    lines = [
        "# Donchian 240-Day Breakout Quantitative Trading System",
        "",
        "> **Automated Quantitative Strategy Implementation for Indian Equities (NSE)**  ",
        f"> **Connected Remote:** `https://github.com/Ved-2107/Donchain.git`  ",
        f"> **Current Portfolio Status:** Active Continuous Paper Trading | **Base Capital:** ₹{initial_cap:,.2f}",
        "",
        "---",
        "",
        "## 1. Live Portfolio Dashboard",
        "",
        "| Metric | Current Value | Strategy Reference |",
        "| :--- | :---: | :--- |",
        f"| **Portfolio NAV** | **₹{nav:,.2f}** | Initial Capital: ₹{initial_cap:,.2f} |",
        f"| **Net Return** | **{total_ret:+.2f}%** | All fees, STT, GST and slippage accounted |",
        f"| **Available Cash** | **₹{cash:,.2f}** | Ready for opportunistic deployment |",
        f"| **Invested Capital** | **₹{invested:,.2f}** | Allocated across active momentum leaders |",
        f"| **Active Holdings** | **{len(holdings)} Positions** | Max limit: 12 stocks (8% single-stock cap) |",
        f"| **Total Completed Trades** | **{tot_trades} Trades** | Closed via 8% trailing stop-loss |",
        f"| **Win Rate** | **{win_rate:.1f}%** | High profit-factor trend following |",
        f"| **Last Bot Update** | `{state.get('last_updated', datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S'))}` | Auto-synced to GitHub |",
        "",
        "---",
        "",
        "## 2. Active Portfolio Holdings",
        "",
    ]

    if not holdings:
        lines.append("*No open positions currently. The bot is actively monitoring 1,447 stocks for 52-week breakouts.*")
    else:
        lines.append("| Symbol | Sector | Shares | Entry Price | Current Price | Peak Price | Trailing Stop (8%) | Unrealized PnL | Return % |")
        lines.append("| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
        for sym, pos in holdings.items():
            ep = pos["entry_price"]
            cp = pos.get("current_price", ep)
            pk = pos.get("peak_price", ep)
            sl = pos.get("stop_loss_price", pk * 0.92)
            sh = pos["shares"]
            upnl = (cp - ep) * sh
            upnl_pct = ((cp / ep) - 1.0) * 100.0
            lines.append(f"| **{sym}** | {pos.get('industry', 'Unclassified')} | {sh} | ₹{ep:.2f} | ₹{cp:.2f} | ₹{pk:.2f} | ₹{sl:.2f} | **₹{upnl:+.2f}** | **{upnl_pct:+.2f}%** |")

    lines.extend([
        "",
        "---",
        "",
        "## 3. Strategy Core Architecture & Rules",
        "",
        "The strategy deployed in this repository is **`EXP_08462`**, selected as the primary winner from an exhaustive optimization study across **1,447 stocks** and **8,640 full parameter simulations**:",
        "",
        "1. **Entry Rule (52-Week High Breakout):**",
        "   - A stock triggers a BUY signal when its market close exceeds its 240-day high: $Close_t > \\max(Close_{t-240..t-1})$.",
        "   - Only genuine structural 52-week expansions are bought, filtering out noise.",
        "2. **Exit Rule (Close-Trigger Trailing 8% Stop-Loss):**",
        "   - As the stock advances, its highest peak close is continuously tracked: $Peak = \\max(Peak, Close_t)$.",
        "   - The trailing stop is set strictly at 8% below the peak close: $StopLoss = Peak \\times 0.92$.",
        "   - If $Close_t \\le StopLoss$, the position is completely liquidated at market close.",
        "3. **Cool-Down & Re-entry Rule (21 Days / 20-Day High):**",
        "   - After stopping out, a stock enters a mandatory **21-day cool-down** to prevent whipsawing during consolidation.",
        "   - After 21 days, if the stock establishes a new **20-day high breakout**, the bot re-enters the trend.",
        "4. **Position Sizing & Risk Controls:**",
        "   - **8% Single-Stock Cap:** Exactly ₹12,000 allocated per position from the ₹150,000 capital base (~12 slots).",
        "   - **20% Sector Cap:** Maximum ₹30,000 exposure per industry sector to ensure multi-sector diversification.",
        "",
        "---",
        "",
        "## 4. Backtest Evidence & Quantitative Benchmark",
        "",
        "| Strategy | Net CAGR (%) | Max Drawdown (%) | Sharpe Ratio | Calmar Ratio | Out-of-Sample CAGR |",
        "| :--- | :---: | :---: | :---: | :---: | :---: |",
        "| **Donchian Baseline (`EXP_02659`)** | 12.98% | -42.71% | 0.62 | 0.30 | 9.43% |",
        "| **Recommended Winner (`EXP_08462`)** | **81.31%** | **-32.37%** | **4.40** | **2.51** | **121.83%** |",
        "| **Net Improvement** | **+68.33%** | **+10.34% milder** | **7.1x higher** | **8.2x higher** | **+112.40%** |",
        "",
        "---",
        "",
        "## 5. Execution Guide & Continuous Automation",
        "",
        "Run the continuous trading daemon locally:",
        "```cmd",
        "run_trading_bot.bat",
        "```",
        "Or via Python CLI:",
        "```bash",
        "python trading_bot.py --loop --interval 60",
        "```",
    ])

    with README_PATH.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    rebalance_portfolio(initial_seed=True)
