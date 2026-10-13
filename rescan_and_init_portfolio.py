"""
Rescan Donchian 240-Day Strategy across all updated equities and initialize portfolio clean from today.
"""

import json
from pathlib import Path
from datetime import datetime
import pandas as pd
from paper_trading import (
    load_config,
    save_state,
    record_trade,
    generate_readme,
    get_industry_map,
    CostModel,
    DAILY_DIR,
    STATE_PATH,
    TRADE_LOG_PATH,
)

IST = datetime.now().astimezone().tzinfo

def rescan_and_initialize(initial_capital: float = 150000.0) -> dict:
    config = load_config()
    cost_model = CostModel(**config["cost_model"])
    industry_map = get_industry_map()
    
    # 1. Reset State clean to initial capital
    state = {
        "initial_capital": initial_capital,
        "cash": initial_capital,
        "holdings": {},
        "cooldowns": {},
        "nav_history": [],
        "total_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "realized_pnl": 0.0,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    
    # 2. Reset trade_log.csv
    header = "timestamp,symbol,side,shares,price,gross_value,fees,net_value,realized_pnl,realized_pnl_pct,reason\n"
    with open(TRADE_LOG_PATH, "w", encoding="utf-8") as f:
        f.write(header)
        
    # 3. Scan all 1447 CSV files using full updated data
    csv_files = list(DAILY_DIR.glob("*_daily.csv"))
    print(f"Scanning {len(csv_files)} updated equities for genuine 240-day breakouts...")
    
    breakout_candidates = []
    donchian_period = config["donchian_period"]
    
    for f in csv_files:
        sym = f.stem.replace("_daily", "")
        try:
            df = pd.read_csv(f)
            if len(df) < 241:
                continue
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.dropna(subset=["Date", "Close"]).sort_values("Date")
            
            c_series = df["Close"]
            today_close = float(c_series.iloc[-1])
            today_date = df["Date"].iloc[-1].strftime("%Y-%m-%d")
            
            # Check 240-day high (excluding today)
            prior_240_high = float(c_series.iloc[-donchian_period-1 : -1].max())
            
            if today_close > prior_240_high:
                momentum = (today_close / c_series.iloc[-21:-1].mean()) - 1.0 if len(df) > 21 else 0.0
                breakout_candidates.append({
                    "symbol": sym,
                    "price": today_close,
                    "prior_high": prior_240_high,
                    "date": today_date,
                    "momentum": momentum,
                    "industry": industry_map.get(sym, "Unclassified"),
                })
        except Exception:
            continue
            
    print(f"Found {len(breakout_candidates)} genuine 240-day breakouts across the market today!")
    
    # Sort candidates by momentum descending
    breakout_candidates.sort(key=lambda x: x["momentum"], reverse=True)
    
    # 4. Allocate into genuine breakouts up to limits
    max_pos_val = initial_capital * config["max_position_pct"]  # 12,000
    max_sector_val = initial_capital * config["max_sector_pct"] # 30,000
    available_slots = config["max_positions"]                   # 12
    sector_exposure = {}
    
    trades_executed = []
    
    for cand in breakout_candidates:
        if available_slots <= 0:
            break
        sym = cand["symbol"]
        ind = cand["industry"]
        curr_sec_val = sector_exposure.get(ind, 0.0)
        if curr_sec_val >= max_sector_val:
            continue
            
        p = cand["price"]
        target_allocation = min(max_pos_val, max_sector_val - curr_sec_val, state["cash"])
        if target_allocation < 1000.0 or p <= 0:
            continue
            
        shares = int(target_allocation // p)
        if shares <= 0:
            continue
            
        gross_val = round(shares * p, 2)
        fees = cost_model.estimate_fees("BUY", gross_val)
        total_cost = round(gross_val + fees["total"], 2)
        
        if total_cost > state["cash"]:
            shares = int((state["cash"] - fees["total"]) // p)
            if shares <= 0:
                continue
            gross_val = round(shares * p, 2)
            fees = cost_model.estimate_fees("BUY", gross_val)
            total_cost = round(gross_val + fees["total"], 2)
            
        state["cash"] -= total_cost
        sector_exposure[ind] = curr_sec_val + gross_val
        available_slots -= 1
        
        state["holdings"][sym] = {
            "shares": shares,
            "entry_price": p,
            "peak_price": p,
            "stop_loss_price": round(p * 0.92, 2),
            "current_price": p,
            "entry_date": cand["date"],
            "industry": ind,
            "signal_type": "DONCHIAN_240_BREAKOUT",
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
            reason=f"DONCHIAN_240_BREAKOUT (Prior High: {cand['prior_high']:.2f})",
            timestamp=f"{cand['date']} 15:30:00",
        )
        trades_executed.append(f"BOUGHT {sym}: {shares} shares @ Rs {p:.2f} ({ind})")
        
    invested_equity = sum(h["shares"] * h["current_price"] for h in state["holdings"].values())
    final_nav = round(state["cash"] + invested_equity, 2)
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    state["nav_history"].append({
        "date": today_str,
        "nav": final_nav,
        "cash": round(state["cash"], 2),
        "invested": round(invested_equity, 2),
        "holdings_count": len(state["holdings"]),
        "total_return_pct": round(((final_nav / initial_capital) - 1.0) * 100.0, 2),
    })
    
    save_state(state)
    generate_readme(state)
    
    print("=" * 65)
    print("  DONCHIAN SYSTEM INITIALIZATION SUMMARY")
    print(f"  Starting Capital : Rs {initial_capital:,.2f}")
    print(f"  Current NAV      : Rs {final_nav:,.2f} ({((final_nav/initial_capital)-1)*100:+.2f}%)")
    print(f"  Available Cash   : Rs {state['cash']:,.2f}")
    print(f"  Active Holdings  : {len(state['holdings'])} positions")
    print(f"  Trades Executed  : {len(trades_executed)}")
    print("=" * 65)
    for t in trades_executed:
        print("  ->", t)
    print("=" * 65)
    
    return state

if __name__ == "__main__":
    rescan_and_initialize(150000.0)
