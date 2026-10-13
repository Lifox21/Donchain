"""Continuous Donchian 240-Day Breakout Trading Bot for Indian Equities (NSE).

Continuously monitors live prices, executes trailing 8% stop-losses,
evaluates 52-week structural breakouts, and automatically pushes updates to GitHub.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd

from paper_trading import (
    CONFIG_PATH,
    README_PATH,
    STATE_PATH,
    TRADE_LOG_PATH,
    WORKSPACE_DIR,
    generate_readme,
    load_config,
    load_state,
    rebalance_portfolio,
    save_state,
)

# Windows terminal encoding compatibility
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

IST = ZoneInfo("Asia/Kolkata")

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("DonchianBot")


def git_sync_pull() -> bool:
    """Automatically pulls latest remote updates from GitHub if any exist."""
    try:
        res = subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=WORKSPACE_DIR, capture_output=True, text=True)
        if res.returncode == 0 and "Already up to date." not in res.stdout:
            logger.info("Git: Pulled latest cloud updates from GitHub.")
            return True
        return False
    except Exception as e:
        logger.debug(f"Git pull error: {e}")
        return False


def git_sync_push(commit_msg: str = "Auto-update Donchian portfolio metrics and holdings") -> bool:
    """Automatically commit and push portfolio state, trade logs, and README to GitHub."""
    try:
        tracked_files = [
            "portfolio_state.json",
            "trade_log.csv",
            "README.md",
            "config.json",
            "paper_trading.py",
            "trading_bot.py",
            "run_trading_bot.bat",
        ]
        existing = [f for f in tracked_files if (WORKSPACE_DIR / f).exists()]
        if not existing:
            return False

        # 1. Stage tracked files
        subprocess.run(["git", "add"] + existing, cwd=WORKSPACE_DIR, check=True, capture_output=True, text=True)

        # 2. Check if there are cached diffs
        diff_res = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=WORKSPACE_DIR, capture_output=True)
        if diff_res.returncode == 0:
            logger.info("Git: No changes detected to push.")
            return False

        # 3. Pull rebase to avoid merge conflicts
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=WORKSPACE_DIR, capture_output=True, text=True)

        # 4. Commit with [skip ci]
        full_msg = f"{commit_msg} [skip ci]"
        subprocess.run(["git", "commit", "-m", full_msg], cwd=WORKSPACE_DIR, check=True, capture_output=True, text=True)

        # 5. Push to GitHub
        push_res = subprocess.run(["git", "push", "-u", "origin", "main"], cwd=WORKSPACE_DIR, capture_output=True, text=True)
        if push_res.returncode == 0:
            logger.info(f"Successfully pushed updates to GitHub ({WORKSPACE_DIR.name})")
            return True
        else:
            logger.warning(f"Git push warning: {push_res.stderr.strip()}")
            return False

    except Exception as e:
        logger.error(f"Failed to auto-sync to GitHub: {e}")
        return False


def is_market_open(dt: datetime | None = None) -> bool:
    """Checks if the Indian Equity Cash Market (NSE) is currently in regular session (09:15 to 15:30 IST, Mon-Fri)."""
    if dt is None:
        dt = datetime.now(IST)
    if dt.weekday() >= 5:  # Saturday or Sunday
        return False
    market_open = dtime(9, 15)
    market_close = dtime(15, 30)
    current_time = dt.time()
    return market_open <= current_time <= market_close


def print_status() -> None:
    state = load_state()
    nav_hist = state.get("nav_history", [])
    latest_nav = nav_hist[-1]["nav"] if nav_hist else state["cash"]
    holdings = state.get("holdings", {})
    init_cap = state["initial_capital"]
    ret_pct = ((latest_nav / init_cap) - 1.0) * 100.0

    print("=" * 65)
    print("  DONCHIAN 240-DAY BREAKOUT PORTFOLIO STATUS")
    print(f"  Initial Capital : Rs {init_cap:,.2f}")
    print(f"  Current NAV     : Rs {latest_nav:,.2f} ({ret_pct:+.2f}%)")
    print(f"  Available Cash  : Rs {state['cash']:,.2f}")
    print(f"  Active Holdings : {len(holdings)} positions")
    print("=" * 65)
    if holdings:
        print(f"{'SYMBOL':<12} {'SECTOR':<22} {'SHARES':<8} {'ENTRY':<10} {'CURRENT':<10} {'SL (8%)':<10} {'PnL (Rs)':<10}")
        print("-" * 85)
        for s, pos in holdings.items():
            ep = pos["entry_price"]
            cp = pos.get("current_price", ep)
            sl = pos.get("stop_loss_price", ep * 0.92)
            upnl = (cp - ep) * pos["shares"]
            print(f"{s:<12} {pos.get('industry', 'Unclassified')[:20]:<22} {pos['shares']:<8} Rs {ep:<7.2f} Rs {cp:<7.2f} Rs {sl:<7.2f} {upnl:+8.2f}")
    print("=" * 65)


def run_continuous_bot(poll_interval: int = 60, git_push_enabled: bool = True) -> None:
    """Runs continuous polling loop, executes trailing stops and rebalances, pushes to GitHub."""
    logger.info("Starting Donchian continuous trading engine...")
    logger.info(f"Target Polling Interval: {poll_interval}s | Git Auto-Push: {git_push_enabled}")

    # Initial sync from GitHub at startup
    git_sync_pull()

    last_rebalance_date = None

    while True:
        try:
            now = datetime.now(IST)
            today_str = now.strftime("%Y-%m-%d")

            if is_market_open(now):
                logger.info(f"Market is OPEN ({now.strftime('%H:%M:%S')} IST). Monitoring prices & stop-losses...")

                # If near market close (after 15:15 IST) and haven't rebalanced today
                if now.time() >= dtime(15, 15) and last_rebalance_date != today_str:
                    logger.info("Market close auction window reached. Executing full daily rebalance...")
                    git_sync_pull()
                    res = rebalance_portfolio()
                    last_rebalance_date = today_str
                    if git_push_enabled:
                        git_sync_push(f"EOD Rebalance {today_str}: NAV Rs {res['nav']:,.2f} ({len(res['trades_executed'])} trades)")
                else:
                    # In-session trailing stop loss monitor for held positions
                    holdings = load_state().get("holdings", {})
                    if holdings:
                        try:
                            import yfinance as yf
                            tickers = [f"{s}.NS" for s in holdings.keys()]
                            data = yf.download(tickers, period="5d", progress=False, threads=True)
                            for s, pos in list(holdings.items()):
                                t_str = f"{s}.NS"
                                c_series, h_series = pd.Series(dtype=float), pd.Series(dtype=float)
                                if isinstance(data.columns, pd.MultiIndex):
                                    if ("Close", t_str) in data.columns:
                                        c_series = data["Close"][t_str].dropna()
                                        h_series = data["High"][t_str].dropna() if ("High", t_str) in data.columns else c_series
                                else:
                                    if "Close" in data:
                                        c_series = data["Close"].dropna()
                                        h_series = data["High"].dropna() if "High" in data else c_series

                                if not c_series.empty:
                                    curr_p = float(c_series.iloc[-1])
                                    high_p = float(h_series.iloc[-1]) if not h_series.empty else curr_p
                                    peak_p = max(pos.get("peak_price", pos["entry_price"]), high_p)
                                    sl_price = peak_p * (1.0 - 0.08)
                                    pos["peak_price"] = peak_p
                                    pos["stop_loss_price"] = sl_price
                                    pos["current_price"] = curr_p
                                    if curr_p <= sl_price:
                                        logger.warning(f"IN-SESSION STOP LOSS HIT: {s} @ Rs {curr_p:.2f} <= SL Rs {sl_price:.2f}! Executing exit...")
                                        rebalance_portfolio()
                                        if git_push_enabled:
                                            git_sync_push(f"Stop-Loss Exit {s}: Sold @ Rs {curr_p:.2f} [skip ci]")
                                        break
                        except Exception as e:
                            logger.debug(f"Live in-session price check note: {e}")

                time.sleep(poll_interval)
            else:
                # Market is closed - calculate wait time until 09:15 AM
                # Check minutes until 09:15 AM IST today
                open_today = datetime(now.year, now.month, now.day, 9, 15, tzinfo=IST)
                if now.weekday() < 5 and now.time() < dtime(9, 15):
                    mins_to_open = int((open_today - now).total_seconds() / 60.0)
                    logger.info(f"Market CLOSED ({now.strftime('%a %H:%M:%S')} IST). Opening bell at 09:15 AM IST (in {mins_to_open} mins). Standing by...")
                else:
                    logger.info(f"Market CLOSED ({now.strftime('%a %H:%M:%S')} IST). Waiting for next trading session...")

                # Sync any remote updates from GitHub Actions
                git_sync_pull()
                time.sleep(min(poll_interval * 5, 300))

        except KeyboardInterrupt:
            logger.info("Bot manually stopped by user.")
            break
        except Exception as e:
            logger.error(f"Unexpected bot loop error: {e}", exc_info=True)
            time.sleep(poll_interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Donchian 240-Day Breakout Trading Bot")
    parser.add_argument("--loop", action="store_true", help="Run continuous trading loop")
    parser.add_argument("--interval", type=int, default=60, help="Poll interval in seconds")
    parser.add_argument("--rebalance-now", action="store_true", help="Force immediate rebalance and exit")
    parser.add_argument("--status", action="store_true", help="Print current portfolio status and exit")
    parser.add_argument("--git-push", action="store_true", help="Force git add, commit, and push")

    args = parser.parse_args()
    config = load_config()

    if args.status:
        print_status()
        return

    if args.git_push:
        git_sync_push("Manual git sync push")
        return

    if args.rebalance_now:
        logger.info("Executing immediate on-demand portfolio rebalance...")
        res = rebalance_portfolio(config=config)
        print_status()
        if config.get("git_auto_push", True):
            git_sync_push(f"On-demand Rebalance: NAV Rs {res['nav']:,.2f}")
        return

    if args.loop:
        run_continuous_bot(
            poll_interval=args.interval,
            git_push_enabled=config.get("git_auto_push", True),
        )
    else:
        # Default action: run status or prompt
        print_status()
        print("\nTo start continuous monitoring, run:")
        print("  python trading_bot.py --loop --interval 60")
        print("Or force immediate rebalance:")
        print("  python trading_bot.py --rebalance-now")


if __name__ == "__main__":
    main()
