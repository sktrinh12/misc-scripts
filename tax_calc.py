#!/usr/bin/env python3
"""
US Tax Calculator for 1099 Freelancers Abroad — Single Filer
Schedules: C, SE, B, D  |  Forms: 1040, 2555, 8949, 8960
Tax year auto-detected from current date; override with --tax-year.

Usage examples:
  python tax_calc.py --income 50000
  python tax_calc.py --income 50000 --expenses 1600 --ltcg 13000 --stcg 950
  python tax_calc.py --income 50000 --expenses 1600 --ltcg 13000 --no-feie --brackets
  python tax_calc.py --income 120000 --feie-income 120000 --ltcg 25000 --what-if --verbose
  python tax_calc.py --income 50000 --ltcg 13000 --headroom          # key planning view
  python tax_calc.py --income 50000 --tax-year 2026                  # use 2026 constants
"""

import argparse
import sys
from datetime import date

# ══════════════════════════════════════════════════════════════════════════════
# IRS CONSTANTS BY TAX YEAR
# ══════════════════════════════════════════════════════════════════════════════

# Each dict: ordinary_brackets, ltcg_brackets, std_deduction, feie_limit,
#            ss_wage_base, ira_limit, ira_catchup, qbi_threshold, qbi_phaseout,
#            niit_threshold, amt_threshold, ltcg_0pct_ceil, ltcg_15pct_ceil

TAX_TABLES = {
    2024: dict(
        ordinary_brackets = [
            (0,        11_600,       0.10),
            (11_600,   47_150,       0.12),
            (47_150,   100_525,      0.22),
            (100_525,  191_950,      0.24),
            (191_950,  243_725,      0.32),
            (243_725,  609_350,      0.35),
            (609_350,  float("inf"), 0.37),
        ],
        ltcg_brackets = [
            (0,        47_025,       0.00),
            (47_025,   518_900,      0.15),
            (518_900,  float("inf"), 0.20),
        ],
        std_deduction  = 14_600,
        feie_limit     = 126_500,
        ss_wage_base   = 168_600,
        ira_limit      = 7_000,
        ira_catchup    = 8_000,
        qbi_threshold  = 191_950,
        qbi_phaseout   = 50_000,
        niit_threshold = 200_000,
        amt_threshold  = 200_000,
    ),
    2025: dict(
        ordinary_brackets = [
            (0,        11_925,       0.10),
            (11_925,   48_475,       0.12),
            (48_475,   103_350,      0.22),
            (103_350,  197_300,      0.24),
            (197_300,  250_525,      0.32),
            (250_525,  626_350,      0.35),
            (626_350,  float("inf"), 0.37),
        ],
        ltcg_brackets = [
            (0,        48_350,       0.00),
            (48_350,   533_400,      0.15),
            (533_400,  float("inf"), 0.20),
        ],
        std_deduction  = 15_000,
        feie_limit     = 130_000,
        ss_wage_base   = 176_100,
        ira_limit      = 7_000,
        ira_catchup    = 8_000,
        qbi_threshold  = 197_300,
        qbi_phaseout   = 50_000,
        niit_threshold = 200_000,
        amt_threshold  = 200_000,
    ),
    # 2026 — estimated/projected (IRS has not published official figures yet)
    # Based on ~2.5% CPI inflation adjustments; update once IRS releases Rev. Proc.
    2026: dict(
        ordinary_brackets = [
            (0,        12_200,       0.10),
            (12_200,   49_600,       0.12),
            (49_600,   105_800,      0.22),
            (105_800,  201_900,      0.24),
            (201_900,  256_400,      0.32),
            (256_400,  641_100,      0.35),
            (641_100,  float("inf"), 0.37),
        ],
        ltcg_brackets = [
            (0,        49_500,       0.00),
            (49_500,   546_200,      0.15),
            (546_200,  float("inf"), 0.20),
        ],
        std_deduction  = 15_350,
        feie_limit     = 133_500,
        ss_wage_base   = 180_300,
        ira_limit      = 7_000,
        ira_catchup    = 8_000,
        qbi_threshold  = 201_900,
        qbi_phaseout   = 50_000,
        niit_threshold = 200_000,
        amt_threshold  = 200_000,
    ),
}

SUPPORTED_YEARS = sorted(TAX_TABLES.keys())

# Always-fixed constants (not inflation-adjusted)
CAPITAL_LOSS_CAP = 3_000
QBI_RATE         = 0.20
NIIT_RATE        = 0.038
AMT_RATE         = 0.009
SE_NET_FACTOR    = 0.9235

def _current_tax_year():
    """Default tax year = current calendar year (filing the year's return)."""
    return date.today().year

def _resolve_year(requested: int | None) -> tuple[int, bool]:
    """
    Returns (year, is_estimated).
    Falls back to nearest known year if requested year is unsupported.
    """
    if requested is None:
        y = _current_tax_year()
    else:
        y = requested
    if y in TAX_TABLES:
        return y, (y >= 2026)
    # Clamp to nearest supported year
    nearest = min(SUPPORTED_YEARS, key=lambda k: abs(k - y))
    return nearest, True

def load_constants(year: int, overrides: dict) -> dict:
    """Merge year table with any CLI overrides, return flat constants dict."""
    base = dict(TAX_TABLES[year])
    for k, v in overrides.items():
        if v is not None:
            base[k] = v
    return base


# ══════════════════════════════════════════════════════════════════════════════
# ANSI COLOR SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

import os, re

# Detect if terminal supports color (respect NO_COLOR env var)
_COLOR = os.isatty(1) and os.environ.get("NO_COLOR") is None

def _c(*codes):
    return f"\033[{';'.join(str(c) for c in codes)}m" if _COLOR else ""

def _strip(s):
    """Strip ANSI codes for length calculation."""
    return re.sub(r"\033\[[0-9;]*m", "", s)

RST  = _c(0)           # reset

# Text styles
BOLD = _c(1)
DIM  = _c(2)
ITAL = _c(3)

# Foreground colors
BLACK   = _c(30)
RED     = _c(31)
GREEN   = _c(32)
YELLOW  = _c(33)
BLUE    = _c(34)
MAGENTA = _c(35)
CYAN    = _c(36)
WHITE   = _c(37)
GRAY    = _c(90)

# Bright foreground
BRED    = _c(91)
BGREEN  = _c(92)
BYELLOW = _c(93)
BBLUE   = _c(94)
BMAGENTA= _c(95)
BCYAN   = _c(96)
BWHITE  = _c(97)

# Background colors (for header bands)
BG_BLUE    = _c(44)
BG_CYAN    = _c(46)
BG_GREEN   = _c(42)
BG_YELLOW  = _c(43)
BG_MAGENTA = _c(45)
BG_RED     = _c(41)
BG_BLACK   = _c(40)
BG_GRAY    = _c(100)

# Semantic aliases — tweak these to retheme the whole output
C_HDR_FG   = BOLD + BWHITE          # header text
C_HDR_INCM = BG_BLUE   + BOLD + BWHITE   # income section band
C_HDR_FEIE = BG_CYAN   + BOLD + BLACK    # FEIE band
C_HDR_ATL  = BG_GREEN  + BOLD + BLACK    # above-the-line band
C_HDR_DED  = BG_GREEN  + BOLD + BLACK    # deductions band
C_HDR_TAX  = BG_RED    + BOLD + BWHITE   # tax computation band
C_HDR_RATE = BG_MAGENTA+ BOLD + BWHITE   # effective rates band
C_HDR_BKT  = BG_BLUE   + BOLD + BWHITE   # bracket headroom band
C_HDR_WHIF = BG_GRAY   + BOLD + BWHITE   # what-if band
C_HDR_END  = BG_BLACK  + BOLD + BWHITE   # end band

C_LABEL    = WHITE                   # plain label text
C_INCOME   = BOLD + BWHITE          # income line value
C_DEDUCT   = BOLD + BGREEN          # deduction value (saves money → green)
C_TAX_VAL  = BOLD + BYELLOW         # individual tax line values
C_TOTAL    = BOLD + BRED            # total tax liability
C_SUBTOTAL = BOLD + BWHITE          # subtotals (AGI, taxable income, gross)
C_NOTE     = DIM  + GRAY            # bracketed notes
C_WARN     = BOLD + BYELLOW         # ⚠ warnings
C_INFO     = CYAN                   # ℹ info lines
C_HERE     = BOLD + BCYAN           # "you are here" marker
C_GOOD     = BOLD + BGREEN          # 0% LTCG bracket, good news
C_DIV      = GRAY                   # divider lines
C_PAREN    = DIM  + WHITE           # tree lines (├─ └─)
C_PCT_LOW  = BOLD + BGREEN          # effective rate < 15%
C_PCT_MID  = BOLD + BYELLOW         # effective rate 15–25%
C_PCT_HIGH = BOLD + BRED            # effective rate > 25%
C_SCENARIO = CYAN                   # scenario name in what-if
C_DIM_VAL  = GRAY                   # dim values in what-if rows


# ══════════════════════════════════════════════════════════════════════════════
# FORMATTING HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def D(n):
    sign = "-" if n < 0 else " "
    return f"{sign}${abs(n):>12,.2f}"

def P(n):
    return f"{n * 100:.1f}%"

def rate_color(rate):
    if rate < 0.15: return C_PCT_LOW
    if rate < 0.25: return C_PCT_MID
    return C_PCT_HIGH

W = 66  # visual width of the full output line

def hdr(title, bg=None):
    """Full-width colored header band."""
    bg = bg or C_HDR_FG
    inner = f"  {title}  "
    pad   = W - len(inner)
    band  = " " * (pad // 2) + inner + " " * (pad - pad // 2)
    return f"\n{bg}{band}{RST}"

def row(label, value, note="", style=None, val_style=None):
    """Formatted data row: label (left) + value (right) + optional note."""
    val_str  = D(value)
    note_str = f"  {C_NOTE}[{note}]{RST}" if note else ""
    lbl_col  = style or C_LABEL
    val_col  = val_style or (C_DEDUCT if value < 0 else C_INCOME)
    return f"  {lbl_col}{label:<42}{RST}{val_col}{val_str}{RST}{note_str}"

def subtotal_row(label, value, note=""):
    """Bold white subtotal row (AGI, gross, taxable)."""
    val_str  = D(value)
    note_str = f"  {C_NOTE}[{note}]{RST}" if note else ""
    return f"  {BOLD}{WHITE}{label:<42}{RST}{C_SUBTOTAL}{val_str}{RST}{note_str}"

def total_row(label, value):
    """Big bold red total row."""
    val_str = D(value)
    return f"  {BOLD}{BWHITE}{label:<42}{RST}{C_TOTAL}{val_str}{RST}"

def tax_row(label, value, note=""):
    """Yellow tax line."""
    val_str  = D(value)
    note_str = f"  {C_NOTE}[{note}]{RST}" if note else ""
    return f"  {C_LABEL}{label:<42}{RST}{C_TAX_VAL}{val_str}{RST}{note_str}"

def div():
    return f"  {C_DIV}{'─' * 62}{RST}"

def warn(msg):
    return f"  {C_WARN}⚠  {msg}{RST}"

def info(msg):
    return f"  {C_INFO}ℹ  {msg}{RST}"

def clamp(v, lo=0.0, hi=float("inf")):
    return max(lo, min(v, hi))


# ══════════════════════════════════════════════════════════════════════════════
# SCHEDULE SE
# ══════════════════════════════════════════════════════════════════════════════

def calc_se_tax(net_profit, C):
    if net_profit <= 0:
        return dict(se_tax=0, half_se=0, net_earnings=0, ss_tax=0, medicare=0)
    net_earn = net_profit * SE_NET_FACTOR
    ss_tax   = min(net_earn, C["ss_wage_base"]) * 0.124
    medicare = net_earn * 0.029
    se_tax   = ss_tax + medicare
    return dict(se_tax=se_tax, half_se=se_tax / 2,
                net_earnings=net_earn, ss_tax=ss_tax, medicare=medicare)


# ══════════════════════════════════════════════════════════════════════════════
# SCHEDULE D
# ══════════════════════════════════════════════════════════════════════════════

def calc_cap_gains(stcg, stcl, ltcg, ltcl, carryover):
    net_st = stcg - stcl
    net_lt = ltcg - ltcl - carryover

    if net_st >= 0 and net_lt >= 0:
        ordinary  = net_st
        ltcg_pref = net_lt
    elif net_st >= 0 and net_lt < 0:
        combined  = net_st + net_lt
        ordinary  = clamp(combined)
        ltcg_pref = 0.0
    elif net_st < 0 and net_lt >= 0:
        combined  = net_st + net_lt
        ltcg_pref = clamp(combined)
        ordinary  = 0.0
    else:
        combined  = net_st + net_lt
        ordinary  = clamp(combined, lo=-CAPITAL_LOSS_CAP)
        ltcg_pref = 0.0

    total_net      = net_st + net_lt
    carryover_next = abs(min(0, total_net + CAPITAL_LOSS_CAP)) if total_net < -CAPITAL_LOSS_CAP else 0

    return dict(net_st=net_st, net_lt=net_lt, total_net=total_net,
                ordinary=ordinary, ltcg_pref=ltcg_pref,
                carryover_next=carryover_next)


# ══════════════════════════════════════════════════════════════════════════════
# ORDINARY INCOME TAX
# ══════════════════════════════════════════════════════════════════════════════

def calc_ordinary_tax(taxable, C):
    tax, breakdown = 0.0, []
    for (lo, hi, rate) in C["ordinary_brackets"]:
        amount = clamp(min(taxable, hi) - lo)
        if amount <= 0:
            continue
        tax += amount * rate
        breakdown.append(dict(rate=rate, lo=lo, hi=hi, amount=amount, tax=amount * rate))
    return tax, breakdown


# ══════════════════════════════════════════════════════════════════════════════
# LTCG TAX — STACKING RULE
# ══════════════════════════════════════════════════════════════════════════════

def calc_ltcg_tax(ltcg_pref, qdiv, ordinary_taxable, C):
    preferred = ltcg_pref + qdiv
    if preferred <= 0:
        return 0.0, []
    stack_base = ordinary_taxable
    tax, breakdown, remaining = 0.0, [], preferred
    for (lo, hi, rate) in C["ltcg_brackets"]:
        bracket_size = (hi - lo) if hi != float("inf") else float("inf")
        occupied     = clamp(stack_base - lo, 0, bracket_size if hi != float("inf") else stack_base)
        available    = (bracket_size - occupied) if hi != float("inf") else remaining
        available    = clamp(available)
        taxed        = min(remaining, available)
        if taxed > 0:
            tax += taxed * rate
            breakdown.append(dict(rate=rate, amount=taxed, tax=taxed * rate))
        remaining -= taxed
        if remaining <= 0:
            break
    return tax, breakdown


# ══════════════════════════════════════════════════════════════════════════════
# QBI — SEC. 199A
# ══════════════════════════════════════════════════════════════════════════════

def calc_qbi(net_biz, taxable_ex_ltcg, C, feie_excl=0.0, us_work_pct=1.0):
    """
    Sec. 199A — 20% deduction on Qualified Business Income.

    TWO reductions apply before computing the 20%:

    1. FEIE exclusion (settled law):
       Per Reg. §1.199A-3(b)(2)(ii)(I), income excluded under Form 2555 is
       explicitly not QBI. Reduction is dollar-for-dollar.

    2. Geographic sourcing (unsettled — use --us-work-pct to model):
       Per §199A(c)(3)(B), QBI requires income "effectively connected with
       a trade or business within the United States" (§864(c)). Reg.
       §1.199A-3(b)(1)(i) applies §864(c) as if the taxpayer were a
       nonresident alien — meaning work performed abroad produces
       foreign-source income that may NOT qualify as QBI.
       IRS has not issued direct guidance for US citizens splitting time
       between US and foreign soil. The --us-work-pct flag lets you model
       both the conservative position (prorate by days on US soil) and the
       aggressive position (100% QBI, physical location irrelevant).

    The phase-out threshold uses taxable_ex_ltcg (ordinary taxable income
    before this deduction) — unaffected by FEIE since AGI is already reduced.
    """
    us_work_pct = clamp(us_work_pct, lo=0.0, hi=1.0)

    # Step 1: remove FEIE-excluded income (explicit statutory exclusion)
    after_feie = clamp(net_biz - feie_excl)

    # Step 2: prorate to US-performed work (geographic sourcing position)
    qbi_base = clamp(after_feie * us_work_pct)

    if qbi_base <= 0:
        if feie_excl >= net_biz:
            return 0.0, "No QBI — all income excluded via FEIE (Reg. §1.199A-3(b)(2)(ii)(I))"
        return 0.0, "No QBI after geographic sourcing proration"

    # Build a note explaining what reduced the base
    notes = []
    if feie_excl > 0:
        notes.append(f"FEIE excluded ${feie_excl:,.0f}")
    if us_work_pct < 1.0:
        foreign_pct = (1.0 - us_work_pct) * 100
        notes.append(f"{foreign_pct:.0f}% foreign-performed (§864(c) sourcing — see note)")
    note_suffix = f"  [{'; '.join(notes)}]" if notes else ""

    # Deduction = 20% of lesser of QBI base or ordinary taxable income
    base = clamp(min(qbi_base, taxable_ex_ltcg) * QBI_RATE)

    if taxable_ex_ltcg <= C["qbi_threshold"]:
        return base, f"Below threshold — 20% of ${qbi_base:,.2f} QBI{note_suffix}"
    if taxable_ex_ltcg >= C["qbi_threshold"] + C["qbi_phaseout"]:
        return 0.0, f"Above phaseout ceiling — no deduction{note_suffix}"
    ratio     = (taxable_ex_ltcg - C["qbi_threshold"]) / C["qbi_phaseout"]
    deduction = base * (1 - ratio)
    return clamp(deduction), f"Partial phase-out ({P(ratio)} into range){note_suffix}"


# ══════════════════════════════════════════════════════════════════════════════
# BRACKET HEADROOM
# ══════════════════════════════════════════════════════════════════════════════

def bracket_headroom_rows(taxable, C):
    rows = []
    for (lo, hi, rate) in C["ordinary_brackets"]:
        headroom = clamp(hi - max(taxable, lo)) if hi != float("inf") else float("inf")
        current  = lo <= taxable < (hi if hi != float("inf") else taxable + 1)
        rows.append(dict(rate=rate, lo=lo, hi=hi, headroom=headroom, current=current))
    return rows

def ltcg_headroom_rows(full_taxable, ordinary_taxable, C):
    rows = []
    for (lo, hi, rate) in C["ltcg_brackets"]:
        headroom = clamp(hi - max(ordinary_taxable, lo)) if hi != float("inf") else float("inf")
        current  = lo <= full_taxable < (hi if hi != float("inf") else full_taxable + 1)
        rows.append(dict(rate=rate, lo=lo, hi=hi, headroom=headroom, current=current))
    return rows


# ══════════════════════════════════════════════════════════════════════════════
# GEOGRAPHIC SOURCING — US DAY + EARNINGS COUNTER
# ══════════════════════════════════════════════════════════════════════════════

def resolve_us_periods(us_periods: list[str] | None, tax_year: int,
                       net_biz: float) -> dict:
    """
    Parse one or more period strings in the format:
        YYYY-MM-DD:YYYY-MM-DD:AMOUNT   (preferred — explicit earnings)
        YYYY-MM-DD:YYYY-MM-DD          (fallback — prorates by day count)

    Rules:
    - If ALL periods include an AMOUNT, the QBI base = sum of US amounts.
    - If ANY period omits AMOUNT, we fall back to day-count proration for
      that period and warn the user.
    - Days are clipped to the tax year; overlapping ranges are de-duped.
    - AMOUNT is the net income earned during that stint (not gross).

    Returns a dict with enough info for both calculation and display.
    """
    from datetime import date, timedelta

    year_start = date(tax_year, 1, 1)
    year_end   = date(tax_year, 12, 31)
    total_days = (year_end - year_start).days + 1

    if not us_periods:
        return dict(
            us_days=total_days, foreign_days=0, total_days=total_days,
            us_pct=1.0, us_earnings=net_biz, foreign_earnings=0.0,
            earnings_based=False, periods=[], error=None,
            note="No --us-period given — assuming 100% US work (aggressive QBI position)"
        )

    us_day_set   = set()
    parsed       = []
    us_earnings  = 0.0
    all_have_amt = True
    any_have_amt = False
    error        = None

    for period_str in us_periods:
        try:
            parts = period_str.strip().split(":")
            # Support both DATE:DATE and DATE:DATE:AMOUNT
            # Dates are YYYY-MM-DD so each is 10 chars; amount is the 3rd colon-segment
            if len(parts) == 3:
                start  = date.fromisoformat(parts[0].strip())
                end    = date.fromisoformat(parts[1].strip())
                amount = float(parts[2].replace(",", "").strip())
                has_amount = True
                any_have_amt = True
            elif len(parts) == 2:
                start  = date.fromisoformat(parts[0].strip())
                end    = date.fromisoformat(parts[1].strip())
                amount = None
                has_amount = False
                all_have_amt = False
            else:
                raise ValueError("expected format YYYY-MM-DD:YYYY-MM-DD or YYYY-MM-DD:YYYY-MM-DD:AMOUNT")

            if end < start:
                raise ValueError(f"end {end} is before start {start}")

            clipped_start = max(start, year_start)
            clipped_end   = min(end,   year_end)
            clipped_days  = 0

            if clipped_start <= clipped_end:
                d = clipped_start
                while d <= clipped_end:
                    us_day_set.add(d)
                    d += timedelta(days=1)
                clipped_days = (clipped_end - clipped_start).days + 1

            if has_amount:
                us_earnings += amount

            parsed.append(dict(
                start=start, end=end,
                clipped_days=clipped_days,
                amount=amount,
                has_amount=has_amount,
            ))

        except Exception as e:
            error = f"Could not parse --us-period '{period_str}': {e}"
            break

    us_days      = len(us_day_set)
    foreign_days = total_days - us_days

    if all_have_amt and any_have_amt:
        # Best case: every period has an explicit amount
        earnings_based   = True
        us_earnings      = min(us_earnings, net_biz)   # can't exceed total net biz
        foreign_earnings = max(0.0, net_biz - us_earnings)
        us_pct           = us_earnings / net_biz if net_biz > 0 else 0.0
    else:
        # Fallback: prorate by day count
        earnings_based   = False
        us_pct           = us_days / total_days
        us_earnings      = net_biz * us_pct
        foreign_earnings = net_biz - us_earnings

    return dict(
        us_days=us_days, foreign_days=foreign_days, total_days=total_days,
        us_pct=us_pct, us_earnings=us_earnings, foreign_earnings=foreign_earnings,
        earnings_based=earnings_based, periods=parsed, error=error, note=None,
        all_have_amt=all_have_amt, any_have_amt=any_have_amt,
    )


# ══════════════════════════════════════════════════════════════════════════════
# MAIN CALCULATION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def calculate(a, C):
    net_biz = a.income - a.expenses

    se = calc_se_tax(net_biz, C) if a.se_tax else dict(se_tax=0, half_se=0, net_earnings=0, ss_tax=0, medicare=0)

    cg = calc_cap_gains(a.stcg, a.stcl, a.ltcg, a.ltcl, a.loss_carryover)

    feie_excl = 0.0
    feie_note = "FEIE disabled"
    if a.feie:
        feie_income = a.feie_income if a.feie_income is not None else a.income
        # --feie-months: pro-rate foreign income if only part of year abroad
        if hasattr(a, "feie_months") and a.feie_months is not None:
            feie_income = feie_income * (a.feie_months / 12)
        feie_excl = min(clamp(feie_income, hi=C["feie_limit"]), feie_income)
        months_str = f" ({a.feie_months}/12 months)" if hasattr(a, "feie_months") and a.feie_months else ""
        feie_note = f"Excluding {D(feie_excl).strip()} of foreign earned income (max ${C['feie_limit']:,}){months_str}"

    gross = (net_biz + a.w2 + a.other + a.roth_conversion
             + a.interest + a.dividends + cg["ordinary"] + cg["ltcg_pref"])

    ira_limit    = C["ira_catchup"] if a.age >= 50 else C["ira_limit"]
    trad_ira     = clamp(a.trad_ira, hi=ira_limit)
    sep_ira      = clamp(a.sep_ira)
    solo_ee      = clamp(a.solo_401k)
    student_loan = clamp(a.student_loan, hi=2_500)

    above_line = se["half_se"] + trad_ira + sep_ira + solo_ee + a.health_insurance + student_loan + feie_excl
    agi        = gross - above_line

    itemized    = clamp(a.salt, hi=10_000) + a.mortgage_interest + a.charitable + a.other_itemized
    use_itemize = a.itemize or (itemized > C["std_deduction"])
    deduction   = itemized if use_itemize else C["std_deduction"]
    ded_label   = "Itemized" if use_itemize else "Standard"

    taxable_pre_qbi  = clamp(agi - deduction)
    preferred        = cg["ltcg_pref"] + a.qdiv
    ordinary_pre     = clamp(taxable_pre_qbi - preferred)

    _us = getattr(a, "us_periods", None)
    geo = resolve_us_periods(_us, C["_year"], net_biz)
    us_work_pct = geo["us_pct"]
    qbi_ded, qbi_note = calc_qbi(net_biz, ordinary_pre, C,
                                  feie_excl=feie_excl,
                                  us_work_pct=us_work_pct) if a.qbi else (0.0, "QBI disabled")

    taxable           = clamp(taxable_pre_qbi - qbi_ded)
    ordinary_tax_base = clamp(taxable - preferred)

    ord_tax,  ord_breakdown  = calc_ordinary_tax(ordinary_tax_base, C)
    ltcg_tax, ltcg_breakdown = calc_ltcg_tax(cg["ltcg_pref"], a.qdiv, ordinary_tax_base, C)

    net_inv_income = a.interest + a.dividends + cg["ltcg_pref"] + clamp(cg["net_st"])
    niit = 0.0
    if a.niit and agi > C["niit_threshold"]:
        niit = min(net_inv_income, agi - C["niit_threshold"]) * NIIT_RATE

    amt_base     = clamp(se["net_earnings"] + a.w2 - C["amt_threshold"])
    add_medicare = amt_base * AMT_RATE if a.se_tax else 0.0

    total_tax = ord_tax + ltcg_tax + se["se_tax"] + niit + add_medicare
    marginal  = next((r for (lo, hi, r) in C["ordinary_brackets"]
                      if lo <= ordinary_tax_base < (hi if hi != float("inf") else ordinary_tax_base + 1)), 0.37)

    return dict(
        income=a.income, expenses=a.expenses, net_biz=net_biz,
        w2=a.w2, other=a.other, roth_conversion=a.roth_conversion,
        interest=a.interest, dividends=a.dividends, qdiv=a.qdiv, gross=gross,
        cg=cg, se=se,
        feie_enabled=a.feie, feie_excl=feie_excl, feie_note=feie_note,
        above_line=above_line, trad_ira=trad_ira, sep_ira=sep_ira,
        solo_ee=solo_ee, health_ins=a.health_insurance, student_loan=student_loan,
        agi=agi, deduction=deduction, ded_label=ded_label,
        itemized=itemized, std_deduction=C["std_deduction"],
        qbi_ded=qbi_ded, qbi_note=qbi_note, geo=geo,
        taxable=taxable, ordinary_tax_base=ordinary_tax_base, preferred=preferred,
        ord_tax=ord_tax, ord_breakdown=ord_breakdown,
        ltcg_tax=ltcg_tax, ltcg_breakdown=ltcg_breakdown,
        niit=niit, add_medicare=add_medicare, total_tax=total_tax,
        marginal=marginal,
        eff_rate=total_tax / gross if gross > 0 else 0,
        eff_income=(ord_tax + ltcg_tax) / taxable if taxable > 0 else 0,
        ord_headroom=bracket_headroom_rows(ordinary_tax_base, C),
        ltcg_headroom=ltcg_headroom_rows(taxable, ordinary_tax_base, C),
        C=C,
    )


# ══════════════════════════════════════════════════════════════════════════════
# HEADROOM ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def calc_headroom(r):
    """
    Compute actionable planning numbers from the calculated result.
    All figures are marginal — i.e. "how much more / less before the next threshold".
    """
    C    = r["C"]
    oti  = r["ordinary_tax_base"]   # ordinary taxable income (includes STCG component)
    pref = r["preferred"]           # LTCG + qualified dividends already in play
    ti   = r["taxable"]             # total taxable income (ordinary + preferred)
    # Ordinary cap gains component already baked into oti (STCG net)
    ordinary_cg = max(0, r["cg"]["ordinary"])  # the STCG portion in ordinary income

    ord_brackets  = C["ordinary_brackets"]
    ltcg_brackets = C["ltcg_brackets"]

    # ── Ordinary income bracket ────────────────────────────────────────────────
    cur_ord_idx = next(
        (i for i, (lo, hi, _) in enumerate(ord_brackets)
         if lo <= oti < (hi if hi != float("inf") else oti + 1)), 0)
    cur_ord_lo, cur_ord_hi, cur_ord_rate = ord_brackets[cur_ord_idx]

    ord_room_up   = clamp(cur_ord_hi - oti) if cur_ord_hi != float("inf") else float("inf")
    ord_room_down = clamp(oti - cur_ord_lo)
    prev_ord_rate = ord_brackets[cur_ord_idx - 1][2] if cur_ord_idx > 0 else None

    # ── LTCG bracket ──────────────────────────────────────────────────────────
    cur_ltcg_idx = next(
        (i for i, (lo, hi, _) in enumerate(ltcg_brackets)
         if lo <= ti < (hi if hi != float("inf") else ti + 1)), 0)
    cl_lo, cl_hi, cur_ltcg_rate = ltcg_brackets[cur_ltcg_idx]

    ltcg_room_in_bracket = clamp(cl_hi - ti) if cl_hi != float("inf") else float("inf")
    ltcg_0pct_ceiling    = ltcg_brackets[0][1]
    ltcg_0pct_room       = clamp(ltcg_0pct_ceiling - ti)
    ltcg_loss_to_0pct    = clamp(ti - ltcg_0pct_ceiling) if cur_ltcg_rate > 0 else 0.0
    ltcg_15pct_ceiling   = ltcg_brackets[1][1]
    ltcg_15pct_room      = clamp(ltcg_15pct_ceiling - max(ti, ltcg_brackets[1][0]))

    return dict(
        cur_ord_rate=cur_ord_rate, cur_ord_lo=cur_ord_lo, cur_ord_hi=cur_ord_hi,
        ord_room_up=ord_room_up, ord_room_down=ord_room_down, prev_ord_rate=prev_ord_rate,
        oti=oti, ordinary_cg=ordinary_cg,
        cur_ltcg_rate=cur_ltcg_rate, cur_ltcg_idx=cur_ltcg_idx,
        ltcg_room_in_bracket=ltcg_room_in_bracket,
        ltcg_0pct_room=ltcg_0pct_room, ltcg_0pct_ceiling=ltcg_0pct_ceiling,
        ltcg_loss_to_0pct=ltcg_loss_to_0pct,
        ltcg_15pct_room=ltcg_15pct_room, ltcg_15pct_ceiling=ltcg_15pct_ceiling,
        ti=ti, pref=pref,
        ltcg_brackets=ltcg_brackets,
    )


# ══════════════════════════════════════════════════════════════════════════════
# OUTPUT
# ══════════════════════════════════════════════════════════════════════════════

def render(r, a):
    import copy
    out = []
    C        = r["C"]
    tax_year = C["_year"]
    est_flag = C.get("_estimated", False)
    est_note = f"  {BYELLOW}★ estimated — IRS has not published official {tax_year} figures{RST}" if est_flag else ""

    # ── Title banner ──────────────────────────────────────────────────────────
    out.append(hdr(f" US TAX CALCULATOR — TY {tax_year} ", C_HDR_END))
    if est_note:
        out.append(est_note)

    # ── Income ────────────────────────────────────────────────────────────────
    out.append(hdr(" INCOME  (Schedule C / B / D) ", C_HDR_INCM))
    out.append(row("1099 / Freelance Gross",    r["income"],            "Schedule C"))
    out.append(row("Business Expenses",        -r["expenses"],          "Schedule C"))
    out.append(row("Net Business Income",       r["net_biz"],
                   val_style=BOLD + BWHITE))
    if r["w2"]:
        out.append(row("W-2 Wages",             r["w2"]))
    if r["roth_conversion"]:
        out.append(row("Roth Conversion",       r["roth_conversion"],   "ordinary income",
                       val_style=BYELLOW))
    if r["other"]:
        out.append(row("Other Income",          r["other"]))
    if r["interest"]:
        out.append(row("Interest",              r["interest"],          "Schedule B"))
    if r["dividends"]:
        out.append(row("Ordinary Dividends",    r["dividends"],         "Schedule B"))
    if r["qdiv"]:
        out.append(row("Qualified Dividends",   r["qdiv"],              "preferential rate",
                       val_style=BCYAN))

    cg = r["cg"]
    if cg["net_st"] or cg["net_lt"]:
        out.append(row("Net Short-Term Gain/Loss", cg["net_st"],        "ordinary rate"))
        out.append(row("Net Long-Term Gain/Loss",  cg["net_lt"],        "preferential rate",
                       val_style=BCYAN))
        if cg["carryover_next"]:
            out.append(row("  → Loss Carryover to Next Year",           -cg["carryover_next"],
                           val_style=BGREEN))

    out.append(div())
    out.append(subtotal_row("GROSS INCOME", r["gross"]))

    # ── FEIE ─────────────────────────────────────────────────────────────────
    if r["feie_enabled"] and r["feie_excl"]:
        out.append(hdr(" FORM 2555 — FEIE ", C_HDR_FEIE))
        out.append(row("Foreign Earned Income Exclusion", -r["feie_excl"],
                       val_style=BOLD + BGREEN))
        out.append(info(r["feie_note"]))
        if r["preferred"] > 0:
            out.append(warn("Stacking rule: LTCG/QDiv taxed as if excluded income still present"))

    # ── Above-the-line deductions ─────────────────────────────────────────────
    se = r["se"]
    atl = [("½ Self-Employment Tax",   se["half_se"],     "Line 15, Sch 1"),
           ("Traditional IRA",         r["trad_ira"],     ""),
           ("SEP-IRA",                 r["sep_ira"],      ""),
           ("Solo 401(k)",             r["solo_ee"],      ""),
           ("Health Insurance",        r["health_ins"],   "self-employed"),
           ("Student Loan Interest",   r["student_loan"], "max $2,500")]
    shown = [(l, v, n) for (l, v, n) in atl if v]
    if shown:
        out.append(hdr(" ABOVE-THE-LINE DEDUCTIONS  (Schedule 1) ", C_HDR_ATL))
        for (l, v, n) in shown:
            out.append(row(l, -v, n))

    out.append(div())
    out.append(subtotal_row("ADJUSTED GROSS INCOME (AGI)", r["agi"]))

    # ── Below-the-line deductions ─────────────────────────────────────────────
    out.append(hdr(f" DEDUCTIONS  ({r['ded_label']}) ", C_HDR_DED))
    out.append(row(f"{r['ded_label']} Deduction", -r["deduction"]))
    if r["ded_label"] == "Standard" and r["itemized"] > r["std_deduction"]:
        out.append(warn(f"Itemized ({D(r['itemized']).strip()}) > standard — try --itemize"))
    if r["qbi_ded"]:
        out.append(row("QBI Deduction (Sec. 199A)", -r["qbi_ded"],
                       r["qbi_note"], val_style=BOLD + BGREEN))

    # QBI geographic sourcing display
    geo = r["geo"]
    if a.qbi and geo["error"]:
        out.append(warn(f"--us-period parse error: {geo['error']}"))
    elif a.qbi and geo["periods"]:
        basis = "earnings" if geo["earnings_based"] else "day-count proration"
        out.append(f"  {DIM}{CYAN}  ℹ  QBI geographic sourcing — {basis} (§199A(c)(3)(B), §864(c)):{RST}")
        for p in geo["periods"]:
            amt_str = f"  earned {D(p['amount']).strip()}" if p["has_amount"] else \
                      f"  {BYELLOW}no amount given — day-count fallback{RST}{CYAN}"
            out.append(f"  {CYAN}     {p['start']} → {p['end']}"
                       f"  ({p['clipped_days']}d in TY {C['_year']}){amt_str}{RST}")
        if not geo["earnings_based"] and geo["any_have_amt"]:
            out.append(warn("Mixed periods: some have amounts, some don't — "
                            "add :AMOUNT to every --us-period for exact QBI"))
        elif not geo["earnings_based"]:
            out.append(f"  {DIM}{BYELLOW}  ⚡ No amounts given — QBI prorated by day count."
                       f" Add :AMOUNT to each --us-period for exact earnings-based QBI.{RST}")
        us_pct_str  = f"{geo['us_pct']*100:.1f}%"
        fgn_pct_str = f"{(1-geo['us_pct'])*100:.1f}%"
        if geo["earnings_based"]:
            out.append(f"  {CYAN}     US earnings {D(geo['us_earnings']).strip()}"
                       f"  +  foreign {D(geo['foreign_earnings']).strip()}"
                       f"  =  {D(r['net_biz']).strip()} net  →  "
                       f"{us_pct_str} QBI / {fgn_pct_str} excluded{RST}")
        else:
            out.append(f"  {CYAN}     {geo['us_days']}d US  +  {geo['foreign_days']}d abroad"
                       f"  =  {geo['total_days']}d total  →  "
                       f"{us_pct_str} QBI / {fgn_pct_str} excluded{RST}")
    elif a.qbi and r["qbi_ded"] > 0:
        out.append(f"  {DIM}{BYELLOW}  ⚡ QBI note: §199A(c)(3)(B) may limit QBI to US-performed work only."
                   f" If you worked abroad, add --us-period YYYY-MM-DD:YYYY-MM-DD:AMOUNT.{RST}")

    out.append(div())
    out.append(subtotal_row("TAXABLE INCOME", r["taxable"]))
    if r["preferred"] > 0:
        out.append(f"  {C_PAREN}├─{RST} {WHITE}Ordinary Income:{RST}         "
                   f"{BOLD}{WHITE}{D(r['ordinary_tax_base'])}{RST}")
        out.append(f"  {C_PAREN}└─{RST} {CYAN}LTCG / Qual Div (pref):{RST}  "
                   f"{BOLD}{BCYAN}{D(r['preferred'])}{RST}")

    # ── Tax computation ───────────────────────────────────────────────────────
    out.append(hdr(" TAX COMPUTATION ", C_HDR_TAX))

    if a.verbose and r["ord_breakdown"]:
        out.append(f"  {DIM}{WHITE}Ordinary Income Brackets:{RST}")
        for b in r["ord_breakdown"]:
            hi_s = f"${b['hi']:>10,.0f}" if b["hi"] != float("inf") else "         ∞"
            rc   = rate_color(b["rate"])
            out.append(f"    {rc}{P(b['rate']):>5}{RST}  {GRAY}${b['lo']:>10,.0f} – {hi_s}"
                       f"  on {D(b['amount'])}  →{RST}  {C_TAX_VAL}{D(b['tax'])}{RST}")

    out.append(tax_row("Ordinary Income Tax", r["ord_tax"]))

    if r["preferred"] > 0:
        if a.verbose and r["ltcg_breakdown"]:
            out.append(f"  {DIM}{WHITE}LTCG / Qual Div Brackets:{RST}")
            for b in r["ltcg_breakdown"]:
                rc  = C_GOOD if b["rate"] == 0 else rate_color(b["rate"])
                out.append(f"    {rc}{P(b['rate']):>5}{RST}  {GRAY}on {D(b['amount'])}  →{RST}"
                           f"  {BCYAN}{D(b['tax'])}{RST}")
        eff = r["ltcg_tax"] / r["preferred"] if r["preferred"] else 0
        out.append(tax_row("LTCG / Qualified Div Tax", r["ltcg_tax"], f"eff. {P(eff)}"))

    if se["se_tax"]:
        out.append(tax_row("Self-Employment Tax (Sch SE)", se["se_tax"],
                           f"SS {D(se['ss_tax']).strip()} + Medicare {D(se['medicare']).strip()}"))
    if r["niit"]:
        out.append(tax_row("Net Investment Income Tax", r["niit"], "3.8%  Form 8960"))
    if r["add_medicare"]:
        out.append(tax_row("Additional Medicare Tax", r["add_medicare"], "0.9%"))

    out.append(div())
    out.append(total_row("TOTAL TAX LIABILITY", r["total_tax"]))

    # ── Effective rates ───────────────────────────────────────────────────────
    out.append(hdr(" EFFECTIVE RATES ", C_HDR_RATE))

    def rate_line(label, rate):
        rc = rate_color(rate)
        return f"  {WHITE}{label:<44}{RST}{rc}{BOLD}{P(rate)}{RST}"

    out.append(rate_line("Marginal rate (ordinary income):",  r["marginal"]))
    out.append(rate_line("Effective rate (income tax only):", r["eff_income"]))
    out.append(rate_line("Effective rate (all taxes / gross):", r["eff_rate"]))
    quarterly = r["total_tax"] / 4
    out.append(f"  {WHITE}{'Estimated quarterly payment (÷4):':<44}{RST}"
               f"{BOLD}{BYELLOW}${quarterly:,.2f}{RST}")

    # ── Bracket headroom ──────────────────────────────────────────────────────
    if a.brackets:
        out.append(hdr(" ORDINARY INCOME BRACKET HEADROOM ", C_HDR_BKT))
        out.append(f"  {DIM}{WHITE}{'Rate':<8} {'Bracket Range':>28}   {'Headroom':>14}{RST}")
        out.append(f"  {C_DIV}{'─' * 56}{RST}")
        for b in r["ord_headroom"]:
            hi_s  = f"${b['hi']:>10,.0f}" if b["hi"] != float("inf") else "         ∞"
            hd_s  = D(b["headroom"]) if b["headroom"] != float("inf") else "            ∞"
            rc    = rate_color(b["rate"])
            if b["current"]:
                flag = f"  {C_HERE}◀ you are here{RST}"
                out.append(f"  {rc}{BOLD}{P(b['rate']):<8}{RST}"
                           f" {BWHITE}${b['lo']:>10,.0f} – {hi_s}{RST}"
                           f"  {BOLD}{BWHITE}{hd_s}{RST}{flag}")
            else:
                # shade already-passed brackets
                style = GRAY if b["headroom"] == 0 else WHITE
                out.append(f"  {rc}{P(b['rate']):<8}{RST}"
                           f" {style}${b['lo']:>10,.0f} – {hi_s}{RST}"
                           f"  {style}{hd_s}{RST}")

        if r["preferred"] > 0:
            out.append("")
            out.append(f"  {CYAN}LTCG / Qualified Dividend Brackets"
                       f"  {DIM}(ordinary income floor: {D(r['ordinary_tax_base']).strip()}){RST}")
            for b in r["ltcg_headroom"]:
                hi_s = f"${b['hi']:>10,.0f}" if b["hi"] != float("inf") else "         ∞"
                hd_s = D(b["headroom"]) if b["headroom"] != float("inf") else "            ∞"
                rc   = C_GOOD if b["rate"] == 0 else rate_color(b["rate"])
                if b["current"]:
                    flag = f"  {C_HERE}◀ LTCG here{RST}"
                    out.append(f"  {rc}{BOLD}{P(b['rate']):<8}{RST}"
                               f" {BWHITE}${b['lo']:>10,.0f} – {hi_s}{RST}"
                               f"  {BOLD}{BWHITE}{hd_s}{RST}{flag}")
                else:
                    style = GRAY if b["headroom"] == 0 else CYAN
                    out.append(f"  {rc}{P(b['rate']):<8}{RST}"
                               f" {style}${b['lo']:>10,.0f} – {hi_s}{RST}"
                               f"  {style}{hd_s}{RST}")

    # ── Capital gains & income headroom ──────────────────────────────────────
    if a.headroom:
        h = calc_headroom(r)
        C_HDR_HR = _c(48) + BOLD + BLACK   # bright green bg
        out.append(hdr(" CAPITAL GAINS & INCOME HEADROOM ", C_HDR_HR))

        # ── LTCG section ─────────────────────────────────────────────────────
        out.append(f"\n  {BOLD}{BWHITE}▸ LONG-TERM CAPITAL GAINS (preferential rate){RST}")
        out.append(f"  {WHITE}  Current LTCG / QDiv in play:{RST}"
                   f"  {BOLD}{BCYAN}{D(h['pref']).strip()}{RST}"
                   f"  {GRAY}taxed at {P(h['cur_ltcg_rate'])} (stacked on "
                   f"${h['oti']:,.0f} ordinary income){RST}")

        if h["cur_ltcg_rate"] == 0.0:
            # Currently in 0% bracket — show room remaining
            if h["ltcg_0pct_room"] > 0:
                out.append(f"\n  {C_GOOD}  ✓ You are in the 0% LTCG bracket{RST}")
                out.append(f"  {WHITE}  Additional LTCG you can realize at{RST}"
                           f" {C_GOOD}{BOLD}0%{RST}{WHITE}:{RST}"
                           f"  {C_GOOD}{BOLD}{D(h['ltcg_0pct_room']).strip()}{RST}"
                           f"  {GRAY}before hitting 15%{RST}")
                out.append(f"  {WHITE}  Room in 15% bracket after that:{RST}"
                           f"  {BYELLOW}{D(h['ltcg_15pct_room']).strip()}{RST}"
                           f"  {GRAY}(up to $533,400 total taxable){RST}")
            else:
                out.append(f"\n  {BYELLOW}  ⚠ You are at the exact 0% ceiling — next dollar of LTCG hits 15%{RST}")
        else:
            # Currently in 15%+ bracket
            out.append(f"\n  {BYELLOW}  You are in the {P(h['cur_ltcg_rate'])} LTCG bracket{RST}")
            out.append(f"  {WHITE}  Room remaining in {P(h['cur_ltcg_rate'])} bracket:{RST}"
                       f"  {BYELLOW}{BOLD}{D(h['ltcg_room_in_bracket']).strip()}{RST}"
                       f"  {GRAY}more LTCG before hitting next rate{RST}")
            out.append(f"\n  {CYAN}  ↓ To get back to 0% LTCG rate, reduce total taxable income by:{RST}"
                       f"  {BOLD}{BRED}{D(h['ltcg_loss_to_0pct']).strip()}{RST}")
            out.append(f"  {GRAY}    (via harvested losses, higher deductions, lower ordinary income, or IRA contributions){RST}")

        # ── Stacking sensitivity note ─────────────────────────────────────────
        if h["ltcg_0pct_room"] > 0 and h["cur_ltcg_rate"] == 0.0:
            out.append(f"\n  {DIM}{CYAN}  ⚡ Stacking sensitivity: every $1 of extra ordinary income"
                       f" (Roth conversion, ST gain, other income){RST}")
            out.append(f"  {DIM}{CYAN}     consumes $1 of your 0% LTCG room.{RST}")
            out.append(f"  {DIM}{CYAN}     Conversely, every $1 of deduction/loss frees up $1 of 0% room.{RST}")

        out.append(f"\n  {C_DIV}{'─' * 58}{RST}")

        # ── Ordinary income section ───────────────────────────────────────────
        out.append(f"\n  {BOLD}{BWHITE}▸ ORDINARY INCOME BRACKET{RST}")
        ord_hi_str = f"${h['cur_ord_hi']:,.0f}" if h['cur_ord_hi'] != float('inf') else '∞'
        out.append(f"  {WHITE}  Ordinary taxable income:{RST}"
                   f"  {BOLD}{BWHITE}{D(h['oti']).strip()}{RST}"
                   f"  {GRAY}current bracket: {P(h['cur_ord_rate'])}"
                   f" (${h['cur_ord_lo']:,.0f} – {ord_hi_str}){RST}")

        rc_up = rate_color(h["cur_ord_rate"])
        if h["ord_room_up"] != float("inf"):
            out.append(f"\n  {WHITE}  Room until next ordinary bracket ({P(h['cur_ord_rate'])} → next):{RST}"
                       f"  {rc_up}{BOLD}{D(h['ord_room_up']).strip()}{RST}"
                       f"  {GRAY}more income before rate increases{RST}")
        else:
            out.append(f"\n  {WHITE}  You are in the top (37%) bracket.{RST}")

        if h["prev_ord_rate"] is not None:
            rc_dn = rate_color(h["prev_ord_rate"])
            out.append(f"  {WHITE}  Reduction to drop to {P(h['prev_ord_rate'])} ordinary bracket:{RST}"
                       f"  {BOLD}{BGREEN}{D(h['ord_room_down']).strip()}{RST}"
                       f"  {GRAY}via deductions, IRA contributions, or additional expenses{RST}")

        # ── Loss harvesting quick-reference ───────────────────────────────────
        out.append(f"\n  {C_DIV}{'─' * 58}{RST}")
        out.append(f"\n  {BOLD}{BWHITE}▸ LOSS HARVESTING QUICK-REFERENCE{RST}")
        out.append(f"  {GRAY}  Simulates selling additional positions at a loss on top of current numbers.{RST}")
        out.append(f"  {GRAY}  IRS ordering: losses offset gains first; only net loss (up to $3k/yr) hits ordinary income.{RST}")

        out.append(f"\n  {DIM}{WHITE}  {'Extra Losses':>18}  {'LTCG In Play':>13}  {'0% Room Left':>13}"
                   f"  {'Ord. Taxable':>13}  {'Est. Tax Δ':>11}  {'Carryover':>10}{RST}")
        out.append(f"  {C_DIV}{'─' * 84}{RST}")

        # Total gains currently in play (LTCG pref + positive STCG component)
        total_gains = h["pref"] + h["ordinary_cg"]   # both already positive
        base_oti_ex_cg = h["oti"] - h["ordinary_cg"] # ordinary income excluding CG

        loss_steps = [3_000, 5_000, 10_000, 15_000, 20_000]
        for loss in loss_steps:
            if loss <= h["pref"]:
                # Losses just reduce LTCG — no ordinary income effect yet
                new_pref     = h["pref"] - loss
                new_ord_cg   = h["ordinary_cg"]
                new_oti      = h["oti"]
                carryover    = 0.0
                delta_tax    = loss * h["cur_ltcg_rate"]   # 0 if in 0% bracket
            elif loss <= total_gains:
                # Losses wipe out all LTCG, start reducing STCG (ordinary) component
                excess       = loss - h["pref"]
                new_pref     = 0.0
                new_ord_cg   = max(0, h["ordinary_cg"] - excess)
                new_oti      = base_oti_ex_cg + new_ord_cg
                carryover    = 0.0
                delta_tax    = (h["pref"] * h["cur_ltcg_rate"]
                                + (h["ordinary_cg"] - new_ord_cg) * h["cur_ord_rate"])
            else:
                # Net loss — all gains wiped; excess offsets ordinary income up to $3k/yr
                net_loss     = loss - total_gains
                ord_deduct   = min(net_loss, CAPITAL_LOSS_CAP)
                carryover    = max(0.0, net_loss - CAPITAL_LOSS_CAP)
                new_pref     = 0.0
                new_ord_cg   = 0.0
                new_oti      = max(0, base_oti_ex_cg - ord_deduct)
                delta_tax    = (h["pref"] * h["cur_ltcg_rate"]
                                + h["ordinary_cg"] * h["cur_ord_rate"]
                                + ord_deduct * h["cur_ord_rate"])

            new_ti        = new_oti + new_pref
            new_0pct_room = clamp(h["ltcg_0pct_ceiling"] - new_ti)
            room_gained   = new_0pct_room - h["ltcg_0pct_room"]

            # Color: green if 0% room genuinely increased or taxes dropped
            improved = room_gained > 0.5 or delta_tax > 0.5
            row_col  = BGREEN if improved else WHITE
            carry_str = f"${carryover:>9,.0f}" if carryover > 0 else f"{'—':>10}"

            out.append(
                f"  {row_col}  {D(-loss).strip():>18}{RST}"
                f"  {BCYAN}{D(new_pref).strip():>13}{RST}"
                f"  {C_GOOD}{D(new_0pct_room).strip():>13}{RST}"
                f"  {WHITE}{D(new_oti).strip():>13}{RST}"
                f"  {BGREEN if delta_tax > 0.5 else GRAY}-{D(delta_tax).strip():>11}{RST}"
                f"  {GRAY}{carry_str:>10}{RST}"
            )

        out.append(f"\n  {DIM}{GRAY}  Carryover = unused net loss above $3k/yr cap; deductible in future years."
                   f"\n  Model prior-year carryovers now with --loss-carryover <amount>.{RST}")




    if a.what_if:
        out.append(hdr(" WHAT-IF SCENARIOS ", C_HDR_WHIF))
        scenarios = [
            ("Base (current flags)",  dict()),
            ("FEIE on",               dict(feie=True)),
            ("FEIE off",              dict(feie=False)),
            ("QBI off",               dict(qbi=False)),
            ("No FEIE, no QBI",       dict(feie=False, qbi=False)),
            ("Itemized deductions",   dict(itemize=True)),
        ]
        hrow = f"  {DIM}{WHITE}{'Scenario':<26} {'AGI':>14}  {'Taxable':>14}  {'Total Tax':>12}  {'Eff%':>6}{RST}"
        out.append(hrow)
        out.append(f"  {C_DIV}{'─' * 76}{RST}")

        base_tax = r["total_tax"]
        for i, (name, overrides) in enumerate(scenarios):
            a2 = copy.copy(a)
            for k, v in overrides.items():
                setattr(a2, k, v)
            r2     = calculate(a2, C)
            delta  = r2["total_tax"] - base_tax
            is_base = i == 0

            name_col  = (BOLD + BWHITE) if is_base else C_SCENARIO
            tax_col   = (BOLD + BRED) if is_base else (BGREEN if delta < -1 else BRED if delta > 1 else WHITE)
            eff_col   = rate_color(r2["eff_rate"])

            out.append(
                f"  {name_col}{name:<26}{RST}"
                f" {C_DIM_VAL}{D(r2['agi']):>14}{RST}"
                f"  {C_DIM_VAL}{D(r2['taxable']):>14}{RST}"
                f"  {tax_col}{D(r2['total_tax']):>12}{RST}"
                f"  {eff_col}{BOLD}{P(r2['eff_rate']):>6}{RST}"
            )

    out.append(hdr(" END ", C_HDR_END))
    return "\n".join(out)


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def build_parser():
    p = argparse.ArgumentParser(
        prog="tax_calc.py",
        description="US 1099 Freelancer Tax Calculator (TY 2025) — single filer abroad",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python tax_calc.py --income 50000
  python tax_calc.py --income 50000 --expenses 1600 --ltcg 13000 --brackets
  python tax_calc.py --income 50000 --expenses 1600 --ltcg 13000 --stcg 950 --roth-conversion 10000
  python tax_calc.py --income 50000 --expenses 1600 --ltcg 13000 --no-feie --brackets
  python tax_calc.py --income 120000 --feie-income 120000 --ltcg 25000 --what-if --verbose
  python tax_calc.py --income 80000 --trad-ira 7000 --sep-ira 10000 --brackets
"""
    )

    # REQUIRED
    p.add_argument("--income", type=float, required=True, metavar="$",
                   help="[REQUIRED] 1099 / freelance gross income")

    # Income
    g = p.add_argument_group("income")
    g.add_argument("--expenses",        type=float, default=0, metavar="$", help="Business expenses (Schedule C)")
    g.add_argument("--w2",              type=float, default=0, metavar="$", help="W-2 wages")
    g.add_argument("--other",           type=float, default=0, metavar="$", help="Other ordinary income")
    g.add_argument("--roth-conversion", type=float, default=0, metavar="$", help="Roth IRA conversion amount (ordinary income)")
    g.add_argument("--interest",        type=float, default=0, metavar="$", help="Interest income (Schedule B)")
    g.add_argument("--dividends",       type=float, default=0, metavar="$", help="Ordinary dividends (Schedule B)")
    g.add_argument("--qdiv",            type=float, default=0, metavar="$", help="Qualified dividends (preferential rate)")

    # Capital gains
    g = p.add_argument_group("capital gains  (Schedule D / Form 8949)")
    g.add_argument("--ltcg",          type=float, default=0, metavar="$", help="Long-term capital gains")
    g.add_argument("--ltcl",          type=float, default=0, metavar="$", help="Long-term capital losses")
    g.add_argument("--stcg",          type=float, default=0, metavar="$", help="Short-term capital gains")
    g.add_argument("--stcl",          type=float, default=0, metavar="$", help="Short-term capital losses")
    g.add_argument("--loss-carryover",type=float, default=0, metavar="$", help="Prior-year capital loss carryover")

    # FEIE
    g = p.add_argument_group("FEIE  (Form 2555)")
    feie_grp = g.add_mutually_exclusive_group()
    feie_grp.add_argument("--feie",    dest="feie", action="store_true",  default=True,  help="Enable FEIE (default: ON)")
    feie_grp.add_argument("--no-feie", dest="feie", action="store_false",                help="Disable FEIE")
    g.add_argument("--feie-income",      type=float, default=None, metavar="$",
                   help="Foreign earned income to exclude (default: same as --income)")
    g.add_argument("--feie-months",      type=float, default=None, metavar="N",
                   help="Months abroad (1–12). Pro-rates FEIE: e.g. --feie-months 6 excludes "
                        "half of --feie-income. Also reduces QBI base proportionally (Reg. 1.199A-3).")
    g.add_argument("--housing-exclusion",type=float, default=0,    metavar="$",
                   help="Housing cost exclusion (Form 2555 Part IX)")

    # Retirement
    g = p.add_argument_group("retirement contributions  (all reduce AGI)")
    g.add_argument("--trad-ira",  type=float, default=0,  metavar="$", help="Traditional IRA contribution (max $7k, $8k if 50+)")
    g.add_argument("--sep-ira",   type=float, default=0,  metavar="$", help="SEP-IRA contribution")
    g.add_argument("--solo-401k", type=float, default=0,  metavar="$", help="Solo 401(k) employee contribution")
    g.add_argument("--age",       type=int,   default=35, metavar="N", help="Your age (for catch-up limits, default 35)")

    # Deductions
    g = p.add_argument_group("deductions  (Schedule A — itemized)")
    g.add_argument("--itemize",           dest="itemize", action="store_true", default=False,
                   help="Force itemized deductions (auto-switches if itemized > standard $15k)")
    g.add_argument("--salt",              type=float, default=0, metavar="$", help="State & local taxes (SALT cap $10k)")
    g.add_argument("--mortgage-interest", type=float, default=0, metavar="$")
    g.add_argument("--charitable",        type=float, default=0, metavar="$")
    g.add_argument("--other-itemized",    type=float, default=0, metavar="$")
    g.add_argument("--health-insurance",  type=float, default=0, metavar="$",
                   help="Self-employed health insurance premiums (above-the-line)")
    g.add_argument("--student-loan",      type=float, default=0, metavar="$",
                   help="Student loan interest paid (above-the-line, max $2,500)")

    # Toggles
    g = p.add_argument_group("feature toggles")
    qbi_grp = g.add_mutually_exclusive_group()
    qbi_grp.add_argument("--qbi",    dest="qbi", action="store_true",  default=True,  help="Enable QBI deduction (default: ON)")
    qbi_grp.add_argument("--no-qbi", dest="qbi", action="store_false",                help="Disable QBI deduction")
    g.add_argument("--us-period", dest="us_periods", action="append", metavar="START:END:AMOUNT",
                   help="US work stint: YYYY-MM-DD:YYYY-MM-DD:AMOUNT (net income earned that stint). "
                        "AMOUNT is required for earnings-based QBI proration per §199A(c)(3)(B). "
                        "Omit AMOUNT to fall back to day-count proration (less accurate). "
                        "Repeat for multiple stints. "
                        "Example: --us-period 2025-01-01:2025-04-30:32000 --us-period 2025-10-01:2025-12-31:18000")
    g.add_argument("--no-niit",   dest="niit",   action="store_false", default=True,  help="Disable NIIT (3.8%)")
    g.add_argument("--no-se-tax", dest="se_tax", action="store_false", default=True,  help="Disable Schedule SE")

    # Display
    g = p.add_argument_group("display")
    g.add_argument("--brackets", action="store_true", help="Show bracket headroom (ordinary + LTCG)")
    g.add_argument("--verbose",  action="store_true", help="Show per-bracket tax breakdown")
    g.add_argument("--what-if",  action="store_true", help="Show FEIE/QBI/itemize scenario comparison")
    g.add_argument("--headroom", action="store_true",
                   help="Show capital gains planning: 0%% room, losses to shift bracket, income headroom")

    # Year & constant overrides
    g = p.add_argument_group(
        "tax year & constant overrides",
        "Year defaults to current calendar year. Override individual IRS figures as needed.")
    g.add_argument("--tax-year",     type=int,   default=None, metavar="YYYY",
                   help=f"Tax year (supported: {', '.join(str(y) for y in SUPPORTED_YEARS)}; "
                        f"default: current year = {_current_tax_year()})")
    g.add_argument("--std-deduction",type=float, default=None, metavar="$",
                   help="Override standard deduction (single filer)")
    g.add_argument("--feie-limit",   type=float, default=None, metavar="$",
                   help="Override FEIE exclusion limit (Form 2555)")
    g.add_argument("--ss-wage-base", type=float, default=None, metavar="$",
                   help="Override Social Security wage base")
    g.add_argument("--ira-limit",    type=float, default=None, metavar="$",
                   help="Override IRA contribution limit")
    g.add_argument("--qbi-threshold",type=float, default=None, metavar="$",
                   help="Override QBI deduction income threshold (Sec. 199A)")

    return p


def main():
    parser = build_parser()
    a = parser.parse_args()
    if a.income <= 0:
        parser.error("--income must be positive")

    # Resolve tax year and load constants
    tax_year, is_estimated = _resolve_year(a.tax_year)
    const_overrides = {
        "std_deduction":  a.std_deduction,
        "feie_limit":     a.feie_limit,
        "ss_wage_base":   a.ss_wage_base,
        "ira_limit":      a.ira_limit,
        "qbi_threshold":  a.qbi_threshold,
    }
    C = load_constants(tax_year, const_overrides)
    C["_year"]      = tax_year
    C["_estimated"] = is_estimated

    if a.tax_year is not None and a.tax_year not in TAX_TABLES:
        print(f"{BYELLOW}⚠  Tax year {a.tax_year} not in table — using {tax_year} constants"
              f" (nearest supported year).{RST}", file=sys.stderr)

    print(render(calculate(a, C), a))


if __name__ == "__main__":
    main()
