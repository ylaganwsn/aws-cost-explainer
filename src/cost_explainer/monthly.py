"""Month-to-date costs by service, grouped into Monday-Sunday weeks clipped to the month."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .compare import is_usage


def month_bounds(last_day: date) -> tuple[date, date]:
    """First day of last_day's month, and the day after last_day (Cost Explorer End is exclusive)."""
    return last_day.replace(day=1), last_day + timedelta(days=1)


def week_ranges(first: date, last: date) -> list[tuple[date, date]]:
    """Monday-Sunday weeks between first and last (inclusive), clipped to that range."""
    ranges = []
    start = first
    while start <= last:
        sunday = start + timedelta(days=6 - start.weekday())
        end = min(sunday, last)
        ranges.append((start, end))
        start = end + timedelta(days=1)
    return ranges


def week_label(start: date, end: date) -> str:
    """'Oct 5-11' for a full week; partial weeks carry their day count, e.g. 'Oct 1-4 (4 days)'."""
    label = f"{start:%b} {start.day}" if start == end else f"{start:%b} {start.day}-{end.day}"
    days = (end - start).days + 1
    if days < 7:
        label += f" ({days} day{'s' if days != 1 else ''})"
    return label


def get_daily_by_service(client: Any, start: date, end: date) -> dict[date, dict[str, float]]:
    """Return {day: {service: cost}} for start <= day < end, following pagination."""
    days: dict[date, dict[str, float]] = {}
    token = None
    while True:
        kwargs: dict[str, Any] = {
            "TimePeriod": {"Start": start.isoformat(), "End": end.isoformat()},
            "Granularity": "DAILY",
            "Metrics": ["UnblendedCost"],
            "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}],
        }
        if token:
            kwargs["NextPageToken"] = token
        response = client.get_cost_and_usage(**kwargs)
        for period in response.get("ResultsByTime", []):
            day = date.fromisoformat(period["TimePeriod"]["Start"])
            costs = days.setdefault(day, {})
            for group in period.get("Groups", []):
                service = group["Keys"][0]
                amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                costs[service] = costs.get(service, 0.0) + amount
        token = response.get("NextPageToken")
        if not token:
            return days


def build_month_table(
    days: dict[date, dict[str, float]], first: date, last: date, top_n: int = 8
) -> dict[str, Any]:
    """Group daily costs into weeks. Returns week labels, one row per service, and totals."""
    weeks = week_ranges(first, last)
    per_week: list[dict[str, float]] = []
    totals: dict[str, float] = {}
    for start, end in weeks:
        week_costs: dict[str, float] = {}
        day = start
        while day <= end:
            for service, amount in days.get(day, {}).items():
                week_costs[service] = week_costs.get(service, 0.0) + amount
            day += timedelta(days=1)
        per_week.append(week_costs)
        for service, amount in week_costs.items():
            totals[service] = totals.get(service, 0.0) + amount

    ranked = [s for s in sorted(totals, key=lambda s: totals[s], reverse=True) if totals[s] != 0]
    usage = [s for s in ranked if is_usage(s)]
    shown, rest = usage[:top_n], usage[top_n:]
    # Tax is never folded into "Other": it always gets its own row, last, just above Total.
    non_usage = [s for s in ranked if not is_usage(s)]

    def row(s: str) -> dict[str, Any]:
        return {
            "service": s,
            "weeks": [round(w.get(s, 0.0), 2) for w in per_week],
            "total": round(totals[s], 2),
        }

    rows = [row(s) for s in shown]
    if rest:
        rows.append(
            {
                "service": "Other",
                "weeks": [round(sum(w.get(s, 0.0) for s in rest), 2) for w in per_week],
                "total": round(sum(totals[s] for s in rest), 2),
            }
        )
    rows += [row(s) for s in non_usage]
    week_totals = [round(sum(w.values()), 2) for w in per_week]
    return {
        "labels": [week_label(s, e) for s, e in weeks],
        "rows": rows,
        "week_totals": week_totals,
        "total": round(sum(week_totals), 2),
        "month": f"{first:%B %Y}",
        "through": last.isoformat(),
    }
