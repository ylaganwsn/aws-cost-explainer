"""Deterministic week-over-week cost comparison.

Python decides what changed. Nothing in this module calls an LLM.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

# Cost Explorer SERVICE keys that are not usage. Only Tax is billed as its own "service";
# credits and refunds are netted into each service, so they cannot be separated here.
NON_USAGE_SERVICES = {"tax"}


def is_usage(service: str) -> bool:
    return service.strip().lower() not in NON_USAGE_SERVICES


@dataclass(frozen=True)
class Change:
    service: str
    previous: float
    current: float

    @property
    def delta(self) -> float:
        return self.current - self.previous

    @property
    def pct(self) -> float | None:
        """Percent change, or None when the service is new (previous == 0)."""
        if self.previous == 0:
            return None
        return self.delta / self.previous * 100

    @property
    def is_new(self) -> bool:
        return self.previous == 0 and self.current > 0

    @property
    def is_gone(self) -> bool:
        return self.previous > 0 and self.current == 0

    @property
    def is_usage(self) -> bool:
        return is_usage(self.service)


def parse_costs(response: dict[str, Any]) -> list[dict[str, float]]:
    """Turn a Cost Explorer get_cost_and_usage response into one {service: cost} dict per period."""
    periods = []
    for period in response.get("ResultsByTime", []):
        costs: dict[str, float] = {}
        for group in period.get("Groups", []):
            service = group["Keys"][0]
            amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
            costs[service] = costs.get(service, 0.0) + amount
        periods.append(costs)
    return periods


def compare(
    previous: dict[str, float],
    current: dict[str, float],
    min_abs_change: float = 1.0,
    min_pct_change: float = 20.0,
    top_n: int = 5,
) -> dict[str, Any]:
    """Compare two periods and return the changes worth reporting.

    A service is reported when its absolute change is at least ``min_abs_change`` dollars AND
    (it is new, gone, or its percent change is at least ``min_pct_change``).
    """
    changes = [
        Change(s, round(previous.get(s, 0.0), 2), round(current.get(s, 0.0), 2))
        for s in sorted(set(previous) | set(current))
    ]

    def noteworthy(c: Change) -> bool:
        if abs(c.delta) < min_abs_change:
            return False
        return c.is_new or c.is_gone or abs(c.pct or 0) >= min_pct_change

    movers = sorted((c for c in changes if noteworthy(c)), key=lambda c: abs(c.delta), reverse=True)
    total = _totals(previous.values(), current.values())
    usage = _totals(
        (v for s, v in previous.items() if is_usage(s)),
        (v for s, v in current.items() if is_usage(s)),
    )

    return {
        "previous_total": total[0],
        "current_total": total[1],
        "total_delta": total[2],
        "total_pct": total[3],
        "usage_previous": usage[0],
        "usage_current": usage[1],
        "usage_delta": usage[2],
        "usage_pct": usage[3],
        "usage_steady": not any(c.is_usage for c in movers),
        "min_abs_change": min_abs_change,
        "min_pct_change": min_pct_change,
        "new_services": [c.service for c in movers if c.is_new],
        "gone_services": [c.service for c in movers if c.is_gone],
        "top_movers": movers[:top_n],
    }


def _totals(
    previous: Iterable[float], current: Iterable[float]
) -> tuple[float, float, float, float | None]:
    """(previous, current, delta, pct) rounded for display; pct is None when previous is 0."""
    prev = round(sum(previous), 2)
    curr = round(sum(current), 2)
    delta = round(curr - prev, 2)
    return prev, curr, delta, round(delta / prev * 100, 1) if prev else None


def steady_message(result: dict[str, Any]) -> str:
    return (
        "Usage was steady: no service changed by both more than "
        f"${result['min_abs_change']:.2f} and {result['min_pct_change']:g}%"
    )


def _summary_line(name: str, prev: float, curr: float, delta: float, pct: float | None) -> str:
    pct_text = f"{pct:+.1f}%" if pct is not None else "n/a"
    return f"{name}: ${prev:.2f} -> ${curr:.2f} ({delta:+.2f} USD, {pct_text})"


def format_report(result: dict[str, Any], period_label: str = "") -> str:
    """Plain-text report built only from the comparison result (works without an LLM)."""
    lines = []
    title = "AWS cost report" + (f" ({period_label})" if period_label else "")
    lines.append(title)
    lines.append("=" * len(title))
    lines.append(
        _summary_line(
            "Usage (excluding tax)",
            result["usage_previous"],
            result["usage_current"],
            result["usage_delta"],
            result["usage_pct"],
        )
    )
    lines.append(
        _summary_line(
            "Total (including tax)",
            result["previous_total"],
            result["current_total"],
            result["total_delta"],
            result["total_pct"],
        )
    )
    movers: list[Change] = result["top_movers"]
    if result["usage_steady"]:
        lines.append(f"\n{steady_message(result)}.")
        return "\n".join(lines)
    lines.append("\nTop movers:")
    for c in movers:
        if c.is_new:
            detail = "NEW"
        elif c.is_gone:
            detail = "GONE"
        else:
            detail = f"{c.pct:+.1f}%"
        lines.append(
            f"  - {c.service}: ${c.previous:.2f} -> ${c.current:.2f} ({c.delta:+.2f}, {detail})"
        )
    return "\n".join(lines)
