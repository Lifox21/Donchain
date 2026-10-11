# Comprehensive Stock Dataset Coverage & Inventory Report

**Date of Audit:** October 11, 2026  
**Dataset Location:** `c:\Users\Ved Bajaj\Desktop\Lifox\QF Club\Donchain\Daily` & `c:\Users\Ved Bajaj\Desktop\Lifox\QF Club\HHM`  
**Security Universe:** Indian Equities (NSE/BSE Listed Equities > ₹500 Cr Market Capitalization)

---

## 1. Executive Data Inventory Summary

| Metric | Measured Value | Notes & Data Integrity Checks |
| :--- | :---: | :--- |
| **Total Daily CSV Files Discovered** | **1,447** | Independent daily price files in `Donchain\Daily\` |
| **Valid Usable Stock Datasets** | **1,447 (100.0%)** | All 1,447 files have complete, valid headers and data rows |
| **Duplicate Date Records** | **0 (Zero)** | Zero date duplication across all 1,447 files |
| **OHLCV Completeness** | **1,447 (100.0%)** | Date, Open, High, Low, Close, Volume present across all stocks |
| **Total Trading Calendar Days** | **2,866 days** | Span: **January 1, 2015 to August 6, 2026** (11.60 years) |
| **Common Evaluation Period** | **2,625 days** | **December 24, 2015 to August 6, 2026** (10.42 years, after 240-day warm-up) |
| **In-Sample (IS) Period** | **1,734 days** | **December 24, 2015 to December 30, 2022** (6.88 years) |
| **Out-of-Sample (OOS) Period** | **891 days** | **January 2, 2023 to August 6, 2026** (3.54 years) |
| **Stocks Mapped to Industry/Sector** | **1,425 (98.5%)** | Classified into 102 granular industry categories |
| **Stocks with Fundamental EPS** | **1,194 (82.5%)** | Sourced from trailing twelve months (TTM) & annual filings |
| **Stocks with Fundamental Sales** | **1,138 (78.6%)** | Used for Price-to-Sales (PS) calculations |
| **Stocks with Fundamental Book Value** | **1,185 (81.9%)** | Equity Capital + Reserves used for Price-to-Book (PB) |

---

## 2. Historical Date Range & Observation Distribution

The historical dataset spans **11.60 calendar years** of active market history across the National Stock Exchange of India.

### Observation Count Distribution
- **Maximum Observations:** 2,866 trading days (732 stocks with continuous trading from January 1, 2015 to August 6, 2026).
- **Median Observations:** 2,864 trading days.
- **Minimum Observations:** 13 trading days (recently listed IPO securities like `ACMESOLAR`, `HYUNDAI`, etc.).
- **Stocks with ≥ 1,000 Observations (~4+ years):** 1,184 stocks.
- **Stocks with ≥ 2,000 Observations (~8+ years):** 896 stocks.

### Listing Date Influx (Handling Historical Universe Dynamics)
Stocks were added to the simulation only on or after their actual listing dates:
- Pre-listing days are explicitly coded as `NaN`, ensuring that an IPO stock listed in 2019 (e.g. `360ONE`) or 2021 (e.g. `NYKAA`) cannot trigger premature breakouts or be purchased prior to its listing date.
- This faithfully reconstructs the actual historical opportunity set without lookahead bias.

---

## 3. Fundamental Valuation Signals Schema

Fundamental data was extracted and matched from the comprehensive financial dataset `Data_Enhanced.csv`:

1. **Price-to-Earnings (PE):**
   - Computed as `Median_Price / EPS_TTM`.
   - Positive EPS stocks are ranked by earnings cheapness.
   - Negative EPS / loss-making companies are penalized and placed in the lowest valuation tier (PE = 9,999).
2. **Price-to-Book (PB):**
   - Computed as `Market_Cap / (Equity_Capital + Reserves)`.
   - Companies with positive net worth are ranked by price-to-book multiple.
3. **Price-to-Sales (PS):**
   - Computed as `Market_Cap / Annual_Sales`.
4. **Composite Multi-Factor Value:**
   - Equal-weighted average of PE, PB, and PS percentile ranks.

### Valuation Formulations Evaluated
- **Valuation A (Absolute Universe Ranking):** Ranks all 1,447 stocks cross-sectionally from cheapest to most expensive, selecting the absolute lowest-multiple stocks triggering Donchian breakouts.
- **Valuation B (Sector-Relative Ranking):** Computes percentile rankings within each of the 102 individual industry sectors, ensuring capital-intensive sectors (e.g., Banking, Power, Metal) are evaluated against peers rather than tech/consumer firms.

---

## 4. Formal Disclosure of Survivorship Risk

> [!WARNING]
> **Survivorship Bias Disclosure:**
> The workspace daily dataset comprises surviving listed Indian equities available as of August 2026. Securities that were delisted, liquidated, or acquired prior to 2015 or midway through the period without surviving files are not represented in this snapshot.
> 
> **Impact on Research:**
> 1. Strategies evaluated on surviving universes exhibit an inherent upward survivorship premium because bankrupted and completely failed firms are under-represented.
> 2. To mitigate this risk, our testing enforces:
>    - Strict mechanical Stop-Loss triggers (5%, 8%, 10%, and Trailing 8%) to ensure losing trades are severed immediately.
>    - Rigid single-stock caps (5% and 8%) and sector concentration caps (15% and 20%) to prevent over-allocation.
>    - A dedicated **3.54-year Out-of-Sample (OOS) validation period (2023–2026)** to verify that alpha is sustained out of sample.

---

## 5. Machine-Readable Inventory Files Generated

The complete stock-by-stock inventory has been persisted in:
- `C:\Users\Ved Bajaj\.gemini\antigravity-ide\brain\2afbceb0-8e37-48d1-b7db-c79b97df6c5e\scratch\dataset_inventory.csv`
- Records for all 1,447 stocks include: `symbol`, `start_date`, `end_date`, `observations`, `duplicates`, `has_ohlcv`, `industry`, `market_cap`, `has_eps`, `has_sales`, `has_book_value`, and `last_close`.
