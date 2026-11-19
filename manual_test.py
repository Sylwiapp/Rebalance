"""Manual report for the output table printed by rebalance.py.

Pipe the program output in and read the report:

    py rebalance.py | py manual_test.py
    py rebalance.py 100000 example_book.csv | py manual_test.py

With no pipe, this runs rebalance.py once, with no arguments.
The printed table includes the account total, the weights, and the prices.
"""

from __future__ import annotations

import subprocess
import sys
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from pathlib import Path

from rebalance import Security, variance

ROOT = Path(__file__).resolve().parent
REBALANCE = ROOT / "rebalance.py"
CENT = Decimal("0.01")
SHARE_STEP = Decimal("0.000001")


def cash(shares: Decimal, price: Decimal, buy: bool) -> Decimal:
    rounding = ROUND_CEILING if buy else ROUND_FLOOR
    return (shares * price).quantize(CENT, rounding=rounding)


def dollar_gap(security: Security, account: Decimal) -> Decimal:
    current_value = (security.current_percent / 100 * account).quantize(CENT)
    target_value = (security.target_percent / 100 * account).quantize(CENT)
    return abs(target_value - current_value)


def read_table() -> str:
    """Table from the pipe, or from rebalance.py with no arguments."""
    if not sys.stdin.isatty():
        return sys.stdin.read()
    completed = subprocess.run(
        [sys.executable, str(REBALANCE)],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if completed.returncode != 0 or completed.stderr.strip():
        print(completed.stderr.strip() or f"rebalance.py exited with code {completed.returncode}", file=sys.stderr)
        raise SystemExit(completed.returncode or 1)
    return completed.stdout


def parse_table(text: str) -> tuple[Decimal, tuple[Security, ...], list[tuple[Decimal, Decimal]]] | str:
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 2 or lines[0].split()[0] != "Total":
        return "the table has no account total"
    try:
        account = Decimal(lines[0].split()[1]).quantize(CENT)
    except Exception:
        return "cannot read the account total"
    if lines[1].split() != ["Security", "Buy", "Sell", "Target", "Current", "Price"]:
        return "the table header is missing weights or prices"
    securities = []
    shares = []
    for line in lines[2:]:
        cells = line.split()
        if len(cells) != 6:
            return f"cannot read row: {line}"
        name, buy, sell, target, current, price = cells
        try:
            securities.append(Security(name, Decimal(target), Decimal(current), Decimal(price)))
            shares.append((Decimal(buy), Decimal(sell)))
        except Exception:
            return f"cannot read shares: {line}"
    if not securities:
        return "the table has no securities"
    return account, tuple(securities), shares


def row_problem(security: Security, buy: Decimal, sell: Decimal, account: Decimal) -> str | None:
    dollars = dollar_gap(security, account)
    buy_cash = cash(buy, security.price, buy=True)
    sell_cash = cash(sell, security.price, buy=False)
    gap = security.target_variance
    if buy * sell != 0:
        return "both a buy and a sell"
    if gap < 0:
        if buy <= 0 or sell != 0 or buy_cash != dollars:
            return f"expected a buy of {dollars}"
        if cash(buy + SHARE_STEP, security.price, buy=True) <= dollars:
            return "buy can be one share-step larger"
    elif gap > 0:
        if sell <= 0 or buy != 0 or sell_cash != dollars:
            return f"expected a sell of {dollars}"
        smaller = sell - SHARE_STEP
        if smaller > 0 and cash(smaller, security.price, buy=False) >= dollars:
            return "sell can be one share-step smaller"
    elif buy != 0 or sell != 0:
        return "expected no trade"
    current_value = (security.current_percent / 100 * account).quantize(CENT)
    target_value = (security.target_percent / 100 * account).quantize(CENT)
    new_value = current_value + buy_cash - sell_cash
    if new_value != target_value:
        return f"value after trade {new_value}, target {target_value}"
    return None


def main() -> int:
    parsed = parse_table(read_table())
    if isinstance(parsed, str):
        print(f"FAIL: {parsed}", file=sys.stderr)
        return 1
    account, securities, shares = parsed

    print(f"Manual test: account {account} USD")
    print(f"{'Security':<8} {'Buy':>12} {'Sell':>12} {'After USD':>12} {'Target USD':>12} {'Result':>8}")

    problems = []
    deviations = []
    for security, (buy, sell) in zip(securities, shares):
        current_value = (security.current_percent / 100 * account).quantize(CENT)
        target_value = (security.target_percent / 100 * account).quantize(CENT)
        new_value = (
            current_value
            + cash(buy, security.price, buy=True)
            - cash(sell, security.price, buy=False)
        )
        problem = row_problem(security, buy, sell, account)
        if problem is not None:
            problems.append(f"{security.name}: {problem}")
        deviations.append(new_value - target_value)
        print(
            f"{security.name:<8} "
            f"{buy:12.6f} "
            f"{sell:12.6f} "
            f"{new_value:12.2f} "
            f"{target_value:12.2f} "
            f"{'FAIL' if problem else 'PASS':>8}"
        )

    result = variance(deviations) if deviations else None
    print()
    print(f"variance of target gaps: {result}")
    variance_ok = result == 0
    print(f"variance = 0: {'PASS' if variance_ok else 'FAIL'}")
    ok = not problems and variance_ok
    print(f"manual test: {'PASS' if ok else 'FAIL'}")
    for problem in problems:
        print(problem, file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
