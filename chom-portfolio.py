#!/usr/bin/env python3
"""
Chom's Portfolio Tracker
Pulls live prices from Yahoo Finance (no API key needed).
Requires: pip install requests pillow
Usage:
  python3 portfolio.py          -> Prints to console
  python3 portfolio.py --export -> Prints to console AND exports portfolio_summary.png
"""

import sys
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# Your half of joint-era gains owed to her, not yet transferred
PRE_MERGE_CREDIT = 1963.34

# ── CONFIGURATION ──────────────────────────────────────────────────────────────
HOLDINGS = [
    # ticker     shares    cost_basis (per share)
    ("XSHD",     10.0465,  15.18),
    ("QQQM",      4.5,     200.14),
    ("SCHG",     75.0,     25.62),
    ("VOO",      12.0,     517.07),
    ("VTI",       3.0,     337.69),
]

# ── COLORS (Terminal) ──────────────────────────────────────────────────────────
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

# ── PNG EXPORT FUNCTION ────────────────────────────────────────────────────────
def export_mobile_png(data: list, total_val: float, total_cost: float, total_cost_valid: bool, filename="portfolio_summary.png"):
    """Generates a mobile-friendly PNG image designed for WhatsApp/messaging."""
    width, height = 1080, 1920
    bg_color = (15, 23, 42)      # Dark slate blue
    card_color = (30, 41, 59)    # Lighter slate blue
    text_white = (248, 250, 252)
    text_muted = (148, 163, 184)
    green_color = (34, 197, 94)
    red_color = (239, 68, 68)

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Load default font
    try:
        # Tries to load standard system fonts for clean rendering
        title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 48)
        sub_font = ImageFont.truetype("DejaVuSans.ttf", 28)
        header_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 30)
        row_font = ImageFont.truetype("DejaVuSans.ttf", 32)
        bold_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 34)
    except OSError:
        title_font = sub_font = header_font = row_font = bold_font = ImageFont.load_default()

    # Title Card
    draw.rounded_rectangle([40, 60, width - 40, 220], radius=20, fill=card_color)
    draw.text((80, 85), " Chom's Portfolio Tracker", fill=text_white, font=title_font)
    now_str = datetime.now().strftime("%a, %b %-d, %Y at %-I:%M %p")
    draw.text((80, 150), f"Updated: {now_str}", fill=text_muted, font=sub_font)

    # Summary Cards
    draw.rounded_rectangle([40, 240, 520, 380], radius=15, fill=card_color)
    draw.text((60, 260), "Total Portfolio Value", fill=text_muted, font=sub_font)
    draw.text((60, 305), fmt_usd(total_val), fill=text_white, font=bold_font)

    draw.rounded_rectangle([560, 240, width - 40, 380], radius=15, fill=card_color)
    draw.text((580, 260), "Total + Credit", fill=text_muted, font=sub_font)
    draw.text((580, 305), fmt_usd(total_val + PRE_MERGE_CREDIT), fill=text_white, font=bold_font)

    # Holdings Table Header
    y_offset = 420
    draw.text((60, y_offset), "TICKER", fill=text_muted, font=header_font)
    draw.text((250, y_offset), "SHARES", fill=text_muted, font=header_font)
    draw.text((450, y_offset), "PRICE", fill=text_muted, font=header_font)
    draw.text((650, y_offset), "VALUE", fill=text_muted, font=header_font)
    draw.text((850, y_offset), "GAIN/LOSS", fill=text_muted, font=header_font)

    y_offset += 40
    draw.line([(40, y_offset), (width - 40, y_offset)], fill=text_muted, width=2)
    y_offset += 20

    # Holdings Rows
    for row in data:
        ticker, shares, price, val, gain, pct, err = row
        
        draw.text((60, y_offset), ticker, fill=text_white, font=bold_font)
        draw.text((250, y_offset), f"{shares:.2f}", fill=text_white, font=row_font)
        
        if err:
            draw.text((450, y_offset), "N/A", fill=red_color, font=row_font)
        else:
            draw.text((450, y_offset), fmt_usd(price), fill=text_white, font=row_font)
            draw.text((650, y_offset), fmt_usd(val), fill=text_white, font=row_font)
            
            if gain is not None:
                sign = "+" if gain >= 0 else ""
                g_color = green_color if gain >= 0 else red_color
                draw.text((850, y_offset), f"{sign}{fmt_usd(gain)}", fill=g_color, font=row_font)
            else:
                draw.text((850, y_offset), "N/A", fill=text_muted, font=row_font)

        y_offset += 65

    # Overall Summary
    if total_cost_valid and total_cost > 0:
        y_offset += 20
        draw.line([(40, y_offset), (width - 40, y_offset)], fill=text_muted, width=2)
        y_offset += 30

        total_gain = total_val - total_cost
        total_pct = (total_gain / total_cost) * 100
        combined = total_gain + PRE_MERGE_CREDIT
        combined_pct = (combined / total_cost) * 100

        tg_color = green_color if total_gain >= 0 else red_color
        comb_color = green_color if combined >= 0 else red_color

        draw.text((60, y_offset), "Total Gain:", fill=text_white, font=bold_font)
        sign = "+" if total_gain >= 0 else ""
        draw.text((400, y_offset), f"{sign}{fmt_usd(total_gain)} ({sign}{total_pct:.1f}%)", fill=tg_color, font=bold_font)

        y_offset += 55
        draw.text((60, y_offset), "Pre-merge Credit:", fill=text_white, font=bold_font)
        draw.text((400, y_offset), f"+{fmt_usd(PRE_MERGE_CREDIT)}", fill=(234, 179, 8), font=bold_font)

        y_offset += 55
        draw.text((60, y_offset), "Total Earnings:", fill=text_white, font=bold_font)
        sign_c = "+" if combined >= 0 else ""
        draw.text((400, y_offset), f"{sign_c}{fmt_usd(combined)} ({sign_c}{combined_pct:.1f}%)", fill=comb_color, font=bold_font)

    img.save(filename)
    print(f"\n{C.GREEN} Image exported successfully to: {filename}{C.RESET}")

# ── MAIN ───────────────────────────────────────────────────────────────────────
def main():
    export_requested = "--export" in sys.argv

    now = datetime.now().strftime("%A, %B %-d %Y at %-I:%M %p")

    print()
    print(f"{C.BOLD}{C.CYAN}╔══════════════════════════════════════════════════════════╗{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}║            📊  Chom's Portfolio Tracker                  ║{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}╚══════════════════════════════════════════════════════════╝{C.RESET}")
    print(f"{C.DIM}  Updated: {now}{C.RESET}\n")

    col = f"{C.BOLD}  {{:<6}}  {{:>9}}  {{:>10}}  {{:>11}}  {{:>11}}  {{:<28}}{C.RESET}"
    print(col.format("TICKER", "SHARES", "PRICE", "VALUE", "COST BASIS", "GAIN / LOSS"))
    print("  " + "─" * 80)

    total_value       = 0.0
    total_cost        = 0.0
    total_cost_valid  = True
    any_error         = False
    missing_basis     = False

    export_data = []

    for ticker, shares, cost_basis in HOLDINGS:
        price = fetch_price(ticker)

        if price is None:
            print(f"  {C.RED}{ticker:<6}  {shares:>9.4f}  {'N/A':>10}  {'N/A':>11}  {'—':>11}  —{C.RESET}")
            any_error = True
            export_data.append((ticker, shares, 0, 0, None, None, True))
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
            export_data.append((ticker, shares, price, value, gain, pct, False))
        else:
            cost_str   = f"{C.DIM}N/A{C.RESET}"
            gain_str   = f"{C.DIM}N/A  (set cost_basis){C.RESET}"
            total_cost_valid = False
            missing_basis    = True
            export_data.append((ticker, shares, price, value, None, None, False))

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

    if any_error:
        print(f"\n  {C.RED}⚠  One or more tickers failed. Check your connection or the symbol.{C.RESET}")

    print()

    # Trigger PNG export if argument passed
    if export_requested:
        export_mobile_png(export_data, total_value, total_cost, total_cost_valid)

if __name__ == "__main__":
    main()
