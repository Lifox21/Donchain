"""
Donchian Quantitative System: Complete Daily Dataset Updater & Market Rescan
Fetches missing historical bars from 2026-08-07 to 2026-10-13 for all 1,447 equities,
updates Daily/*.csv files, and rescans the 240-day Donchian Breakout strategy.
"""

import os
import glob
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import yfinance as yf

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DataUpdater")

DAILY_DIR = Path("Daily")

def update_all_datasets(batch_size: int = 75, start_date: str | None = None) -> dict:
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    csv_files = list(DAILY_DIR.glob("*_daily.csv"))
    logger.info(f"Checking updates for {len(csv_files)} local daily CSV files from {start_date}...")
    
    symbols = [f.stem.replace("_daily", "") for f in csv_files]
    updated_count = 0
    failed_symbols = []
    
    total_batches = (len(symbols) + batch_size - 1) // batch_size
    
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i : i + batch_size]
        batch_num = (i // batch_size) + 1
        logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} symbols)...")
        
        tickers = [f"{s}.NS" for s in batch]
        try:
            data = yf.download(tickers, start=start_date, progress=False, threads=True)
            if data.empty:
                logger.warning(f"Batch {batch_num} returned empty data.")
                continue
                
            for s in batch:
                t_str = f"{s}.NS"
                csv_path = DAILY_DIR / f"{s}_daily.csv"
                try:
                    # Extract single-stock slice
                    if isinstance(data.columns, pd.MultiIndex):
                        if ("Close", t_str) not in data.columns:
                            continue
                        sub = pd.DataFrame({
                            "Open": data["Open"][t_str],
                            "High": data["High"][t_str],
                            "Low": data["Low"][t_str],
                            "Close": data["Close"][t_str],
                            "Volume": data["Volume"][t_str] if ("Volume", t_str) in data.columns else 0
                        }).dropna(subset=["Close"])
                    else:
                        sub = data[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
                        
                    if sub.empty:
                        continue
                        
                    sub = sub.reset_index()
                    sub["Date"] = pd.to_datetime(sub["Date"]).dt.strftime("%Y-%m-%d")
                    sub = sub[["Date", "Open", "High", "Low", "Close", "Volume"]]
                    
                    # Read existing CSV
                    df_old = pd.read_csv(csv_path)
                    df_old["Date"] = pd.to_datetime(df_old["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
                    df_old = df_old.dropna(subset=["Date", "Close"])
                    
                    # Filter sub to only rows newer than existing last date
                    last_old_date = df_old["Date"].iloc[-1]
                    new_rows = sub[sub["Date"] > last_old_date]
                    
                    if not new_rows.empty:
                        df_combined = pd.concat([df_old, new_rows], ignore_index=True)
                        df_combined = df_combined.drop_duplicates(subset=["Date"]).sort_values("Date")
                        df_combined.to_csv(csv_path, index=False)
                        updated_count += 1
                except Exception as e:
                    failed_symbols.append((s, str(e)))
        except Exception as e:
            logger.error(f"Error downloading batch {batch_num}: {e}")
            
    logger.info(f"Dataset update complete! Successfully updated {updated_count}/{len(symbols)} CSV files.")
    return {"updated": updated_count, "failed": failed_symbols}

if __name__ == "__main__":
    t0 = time.time()
    res = update_all_datasets(batch_size=75)
    t1 = time.time()
    logger.info(f"Total time elapsed: {t1 - t0:.2f} seconds.")
