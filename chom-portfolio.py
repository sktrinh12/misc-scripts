#!/usr/bin/env python3
"""
Chom's Portfolio Tracker
Pulls live prices from Yahoo Finance (no API key needed).
Requires: pip install requests
"""

import sys
import requests
from datetime import datetime

# Your half of joint-era gains owed to her, not yet transferred
PRE_MERGE_CREDIT = 1963.34

# ── CONFIGURATION ──────────────────────────────────────────────────────────────
# To remove a position when sold, just comment it out or delete the line.
# cost_basis = your average price paid per share (check Fidelity → Positions tab)
# Set cost_basis=None if you don't have it yet — gains will show as N/A.

HOLDINGS = [
    # ticker      shares    cost_basis (per share)
    ("XSHD",     10.0465,  15.18),
    ("QQQM",      4.5,     200.14),
    ("SCHG",     75.0,     25.62),
    ("VOO",      12.0,     517.07),
    ("VTI",       3.0,     337.69),
]

# ── COLORS (auto-disabled if not a real terminal) ──────────────────────────────
USE_COLOR = sys.stdout.isatty()

class C:
    RED    = "\033[0;31m"   if USE_COLOR else ""
    GREEN  = "\033[0;32m"   if USE_COLOR else ""
    YELLOW = "\033[1;33m"   if USE_COLOR else ""
    CYAN   = "\033[0;36m"   if USE_COLOR else ""
    BOLD   = "\033[1m"      if USE_COLOR else ""
    DIM    = "\033[2m"      if USE_COLOR else ""
    RESET  = "\033[0m"      if USE_COLOR else ""

# ── PRICE FETCHER ──────────────────────────────────────────────────────────────
def fetch_price(ticker: str) -> float | None:
    """Fetch the latest market price for a ticker from Yahoo Finance."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"interval": "1d", "range": "1d"}
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        meta = data["chart"]["result"][0]["meta"]
        # prefer regularMarketPrice, fall back to previous close
        price = meta.get("regularMarketPrice") or meta.get("chartPreviousClose")
        return float(price) if price else None
    except Exception:
        return None

# ── FORMATTING HELPERS ─────────────────────────────────────────────────────────
def fmt_usd(val: float) -> str:
    return f"${val:,.2f}"

def fmt_gain(gain: float, pct: float) -> str:
    sign = "+" if gain >= 0 else ""
    color = C.GREEN if gain >= 0 else C.RED
    return f"{color}{sign}{fmt_usd(gain)} ({sign}{pct:.1f}%){C.RESET}"

# ── MAIN ───────────────────────────────────────────────────────────────────────
def main():
    now = datetime.now().strftime("%A, %B %-d %Y at %-I:%M %p")

    print()
    print(f"{C.BOLD}{C.CYAN}╔══════════════════════════════════════════════════════════╗{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}║           📊  Chom's Portfolio Tracker                   ║{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}╚══════════════════════════════════════════════════════════╝{C.RESET}")
    print(f"{C.DIM}  Updated: {now}{C.RESET}")
    print()

    col = f"{C.BOLD}  {{:<6}}  {{:>9}}  {{:>10}}  {{:>11}}  {{:>11}}  {{:<28}}{C.RESET}"
    print(col.format("TICKER", "SHARES", "PRICE", "VALUE", "COST BASIS", "GAIN / LOSS"))
    print("  " + "─" * 80)

    total_value       = 0.0
    total_cost        = 0.0
    total_cost_valid  = True
    any_error         = False
    missing_basis     = False

    for ticker, shares, cost_basis in HOLDINGS:
        price = fetch_price(ticker)

        if price is None:
            print(f"  {C.RED}{ticker:<6}  {shares:>9.4f}  {'N/A':>10}  {'N/A':>11}  {'—':>11}  —{C.RESET}")
            any_error = True
            continue

        value = shares * price
        total_value += value

        if cost_basis is not None:
            cost_total = shares * cost_basis
            total_cost += cost_total
            gain       = value - cost_total
            pct        = (gain / cost_total) * 100 if cost_total else 0
            cost_str   = fmt_usd(cost_total)
            gain_str   = fmt_gain(gain, pct)
        else:
            cost_str   = f"{C.DIM}N/A{C.RESET}"
            gain_str   = f"{C.DIM}N/A  (set cost_basis){C.RESET}"
            total_cost_valid = False
            missing_basis    = True

        print(
            f"  {C.BOLD}{ticker:<6}{C.RESET}  "
            f"{shares:>9.4f}  "
            f"{fmt_usd(price):>10}  "
            f"{fmt_usd(value):>11}  "
            f"{cost_str:>11}  "
            f"{gain_str}"
        )

    # ── Summary ──
    print("  " + "─" * 80)
    print(f"  {C.BOLD}{'TOTAL':<31}  {fmt_usd(total_value):>11}{C.RESET}")
    print(f"  {C.BOLD}{'TOTAL + PRE-MERGE CREDIT':<31}  {fmt_usd(total_value + PRE_MERGE_CREDIT):>11}{C.RESET}")

    if total_cost_valid and total_cost > 0:
        total_gain = total_value - total_cost
        total_pct  = (total_gain / total_cost) * 100
        label = "Total Gain" if total_gain >= 0 else "Total Loss"
        print(f"\n  {C.BOLD}{label}:  {fmt_gain(total_gain, total_pct)}{C.RESET}")
        print(f"  {C.YELLOW}{C.BOLD}Pre-merge credit (gift):  +{fmt_usd(PRE_MERGE_CREDIT)}{C.RESET}")
        combined = total_gain + PRE_MERGE_CREDIT
        combined_pct = (combined / total_cost) * 100
        print(f"  {C.BOLD}Total earnings:  {fmt_gain(combined, combined_pct)}{C.RESET}")

    if missing_basis:
        print(f"\n  {C.YELLOW}⚠  Fill in cost_basis values in HOLDINGS to see total gain/loss.{C.RESET}")
        print(f"  {C.YELLOW}   Find them in Fidelity → Positions, or your original broker.{C.RESET}")

    if any_error:
        print(f"\n  {C.RED}⚠  One or more tickers failed. Check your connection or the symbol.{C.RESET}")

    print()

if __name__ == "__main__":
    main()
