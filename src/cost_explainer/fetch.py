"""Fetch two weeks of AWS costs from Cost Explorer (the only module that talks to AWS)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

# Cost Explorer's API endpoint lives in us-east-1, wherever the Lambda runs.
CE_REGION = "us-east-1"


def week_boundaries(today: date | None = None) -> tuple[date, date, date]:
    """Return (previous_week_start, current_week_start, end) for the last two full weeks.

    Weeks run Monday to Sunday. ``end`` is exclusive: Cost Explorer ignores its End date.
    """
    today = today or date.today()
    this_monday = today - timedelta(days=today.weekday())
    return this_monday - timedelta(days=14), this_monday - timedelta(days=7), this_monday


def make_client() -> Any:
    """Create a real Cost Explorer client. boto3 is imported here so tests don't need AWS."""
    import boto3

    return boto3.client("ce", region_name=CE_REGION)


def get_daily_costs(client: Any, start: date, end: date) -> list[dict[str, Any]]:
    """Ask Cost Explorer for daily costs grouped by service, following pagination."""
    results: list[dict[str, Any]] = []
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
        results.extend(response.get("ResultsByTime", []))
        token = response.get("NextPageToken")
        if not token:
            return results


def split_weeks(
    daily: list[dict[str, Any]], current_week_start: date
) -> tuple[dict[str, float], dict[str, float]]:
    """Add up the daily costs into {service: cost} for the previous and current week."""
    previous: dict[str, float] = {}
    current: dict[str, float] = {}
    cutoff = current_week_start.isoformat()
    for day in daily:
        target = current if day["TimePeriod"]["Start"] >= cutoff else previous
        for group in day.get("Groups", []):
            service = group["Keys"][0]
            amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
            target[service] = target.get(service, 0.0) + amount
    return previous, current


def fetch_weekly_costs(
    client: Any = None, today: date | None = None
) -> tuple[dict[str, float], dict[str, float], tuple[date, date]]:
    """Return (previous_week, current_week, (current_start, end)) as {service: cost} dicts."""
    prev_start, curr_start, end = week_boundaries(today)
    client = client or make_client()
    daily = get_daily_costs(client, prev_start, end)
    previous, current = split_weeks(daily, curr_start)
    return previous, current, (curr_start, end)
