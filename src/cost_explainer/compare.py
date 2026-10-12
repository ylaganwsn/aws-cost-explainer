"""Deterministic week-over-week cost comparison.

Python decides what changed. Nothing in this module calls an LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
    prev_total = round(sum(previous.values()), 2)
    curr_total = round(sum(current.values()), 2)
    total_delta = round(curr_total - prev_total, 2)

    return {
        "previous_total": prev_total,
        "current_total": curr_total,
        "total_delta": total_delta,
        "total_pct": round(total_delta / prev_total * 100, 1) if prev_total else None,
        "new_services": [c.service for c in movers if c.is_new],
        "gone_services": [c.service for c in movers if c.is_gone],
        "top_movers": movers[:top_n],
    }


def format_report(result: dict[str, Any], period_label: str = "") -> str:
    """Plain-text report built only from the comparison result (works without an LLM)."""
    lines = []
    title = "AWS cost report" + (f" ({period_label})" if period_label else "")
    lines.append(title)
    lines.append("=" * len(title))
    pct = result["total_pct"]
    pct_text = f"{pct:+.1f}%" if pct is not None else "n/a"
    lines.append(
        f"Total: ${result['previous_total']:.2f} -> ${result['current_total']:.2f} "
        f"({result['total_delta']:+.2f} USD, {pct_text})"
    )
    movers: list[Change] = result["top_movers"]
    if not movers:
        lines.append("\nNo changes above the reporting thresholds.")
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
