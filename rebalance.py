"""How many shares to buy and sell so each security matches its target weight.

    Run with no arguments to rebalance account ABC ($100,000).
    Example: py rebalance.py
    
    Otherwise pass the account total and a table file.
    Example: py rebalance.py 100000 example_book.csv

    The table file must have a header: name, target_percent, current_percent, price.
    The program prints the shares to buy and sell for each security.
    The program exits with code 0 if successful, 2 if there is an error.
    The program prints errors to stderr.
    The program prints the shares to buy and sell for each security to stdout.

"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR

CENT = Decimal("0.01")
SHARE_PLACES = 6
MAX_SECURITIES = 10


@dataclass(frozen=True)
class Security:
    name: str
    target_percent: Decimal
    current_percent: Decimal
    price: Decimal

    @property
    def target_variance(self) -> Decimal:
        """Current weight minus target weight, in percentage points."""
        return self.current_percent - self.target_percent


@dataclass(frozen=True)
class Trade:
    security: str
    shares_to_buy: Decimal
    shares_to_sell: Decimal
    value_after: Decimal


# Account ABC. 100% of the $100,000 is vested.
ACCOUNT_TOTAL = Decimal("100000")
ACCOUNT_ABC = (
    Security("IBM", Decimal("20"), Decimal("10"), Decimal("150")),
    Security("MSFT", Decimal("20"), Decimal("20"), Decimal("90")),
    Security("ORCL", Decimal("20"), Decimal("30"), Decimal("220")),
    Security("AAPL", Decimal("20"), Decimal("20"), Decimal("450")),
    Security("HD", Decimal("20"), Decimal("20"), Decimal("70")),
)


def rebalance(total_assets: object, securities: tuple[Security, ...] | list[Security]) -> tuple[Trade, ...]:
    """Return shares to buy and shares to sell for each security.
    """
    total = _money(total_assets)
    if total < 0:
        raise ValueError("total assets cannot be negative")
    if not 1 <= len(securities) <= MAX_SECURITIES:
        raise ValueError("provide from 1 to 10 securities")

    trades = []
    for security in securities:
        price = _price(security.price)
        current_value = _money(security.current_percent / 100 * total)
        target_value = _money(security.target_percent / 100 * total)
        gap = target_value - current_value
        if gap > 0:
            shares = _shares_for_cash(gap, price, buy=True)
            value_after = current_value + _cash(shares, price, buy=True)
            trades.append(Trade(security.name, shares, _zero_shares(), value_after))
        elif gap < 0:
            shares = _shares_for_cash(-gap, price, buy=False)
            value_after = current_value - _cash(shares, price, buy=False)
            trades.append(Trade(security.name, _zero_shares(), shares, value_after))
        else:
            trades.append(Trade(security.name, _zero_shares(), _zero_shares(), current_value))
    return tuple(trades)


def variance(values: list[Decimal] | tuple[Decimal, ...]) -> Decimal:
    """Population variance. It is zero when every value is the same."""
    count = len(values)
    if count == 0:
        raise ValueError("variance needs at least one value")
    mean = sum(values, Decimal("0")) / count
    return sum((value - mean) ** 2 for value in values) / count


def _shares_for_cash(amount: Decimal, price: Decimal, buy: bool) -> Decimal:
    """Share count whose cent-rounded cash equals `amount`."""
    step = Decimal(1).scaleb(-SHARE_PLACES)
    shares = (amount / price).quantize(step, rounding=ROUND_DOWN)
    if buy:
        while shares > 0 and _cash(shares, price, buy=True) > amount:
            shares -= step
        while _cash(shares + step, price, buy=True) <= amount:
            shares += step
    else:
        while _cash(shares, price, buy=False) < amount:
            shares += step
        while shares > step and _cash(shares - step, price, buy=False) >= amount:
            shares -= step
    return shares.quantize(step)


def _cash(shares: Decimal, price: Decimal, buy: bool) -> Decimal:
    rounding = ROUND_CEILING if buy else ROUND_FLOOR
    return (shares * price).quantize(CENT, rounding=rounding)


def _money(value: object) -> Decimal:
    return _number(value, "amount").quantize(CENT)


def _price(value: object) -> Decimal:
    price = _number(value, "price")
    if price <= 0:
        raise ValueError("price must be greater than zero")
    return price


def _number(value: object, name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (Decimal, int, str)):
        raise TypeError(f"{name} must be a number")
    try:
        number = value if isinstance(value, Decimal) else Decimal(value)
    except Exception as exc:
        raise ValueError(f"cannot read {name}: {value!r}") from exc
    if not number.is_finite():
        raise ValueError(f"{name} must be finite")
    return number


def _zero_shares() -> Decimal:
    return Decimal(0).quantize(Decimal(1).scaleb(-SHARE_PLACES))


def _format_shares(shares: Decimal) -> str:
    return f"{shares:.6f}"


TABLE_COLUMNS = ("name", "target_percent", "current_percent", "price")


def load_securities(path: str) -> tuple[Security, ...]:
    """Read a CSV table with a header: name, target_percent, current_percent, price."""
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("the CSV file is empty")
        fields = [name.strip() for name in reader.fieldnames]
        reader.fieldnames = fields
        if fields != list(TABLE_COLUMNS):
            raise ValueError(
                "CSV header must be: name,target_percent,current_percent,price"
            )
        for line_number, record in enumerate(reader, start=2):
            if not any((record.get(column) or "").strip() for column in TABLE_COLUMNS):
                continue
            try:
                rows.append(
                    Security(
                        record["name"].strip(),
                        Decimal(record["target_percent"].strip()),
                        Decimal(record["current_percent"].strip()),
                        Decimal(record["price"].strip()),
                    )
                )
            except (AttributeError, KeyError, ValueError) as exc:
                raise ValueError(f"line {line_number}: invalid security row") from exc
    return tuple(rows)


def print_trades(
    total: Decimal,
    securities: tuple[Security, ...] | list[Security],
    trades: tuple[Trade, ...],
) -> None:
    """Print the account total, the weights, the prices, and the share counts."""
    print(f"Total {Decimal(total).quantize(CENT):.2f}")
    print(
        f"{'Security':<8} {'Buy':>12} {'Sell':>12} "
        f"{'Target':>10} {'Current':>10} {'Price':>12}"
    )
    for security, trade in zip(securities, trades):
        print(
            f"{trade.security:<8} "
            f"{_format_shares(trade.shares_to_buy):>12} "
            f"{_format_shares(trade.shares_to_sell):>12} "
            f"{format(security.target_percent, 'f'):>10} "
            f"{format(security.current_percent, 'f'):>10} "
            f"{format(security.price, 'f'):>12}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Shares to buy and sell. "
            "Without arguments, runs account ABC ($100,000). "
            "Otherwise pass the account total and a table file."
        ),
    )
    parser.add_argument("total", nargs="?", help="account total in dollars, for example 50000")
    parser.add_argument(
        "table",
        nargs="?",
        help="CSV file with columns name, target_percent, current_percent, price",
    )
    args = parser.parse_args(argv)
    if (args.total is None) != (args.table is None):
        parser.error("pass both the total and the table file, or neither")
    try:
        if args.table is None:
            total, securities = ACCOUNT_TOTAL, ACCOUNT_ABC
        else:
            total, securities = args.total, load_securities(args.table)
        trades = rebalance(total, securities)
    except (OSError, ValueError, TypeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print_trades(total, securities, trades)
    return 0


if __name__ == "__main__":
    sys.exit(main())
