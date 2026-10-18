from datetime import date

import pytest

from cost_explainer.fetch import fetch_weekly_costs, week_boundaries


def day(start, costs):
    return {
        "TimePeriod": {"Start": start, "End": start},
        "Groups": [
            {"Keys": [name], "Metrics": {"UnblendedCost": {"Amount": str(amount), "Unit": "USD"}}}
            for name, amount in costs.items()
        ],
    }


class FakeClient:
    """Stands in for boto3's Cost Explorer client and records how it was called."""

    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get_cost_and_usage(self, **kwargs):
        self.calls.append(kwargs)
        return self.pages[len(self.calls) - 1]


def test_week_boundaries_midweek():
    assert week_boundaries(date(2026, 10, 14)) == (
        date(2026, 9, 28),
        date(2026, 10, 5),
        date(2026, 10, 12),
    )


def test_week_boundaries_on_monday():
    assert week_boundaries(date(2026, 10, 12))[2] == date(2026, 10, 12)


def test_week_boundaries_on_sunday_uses_last_full_week():
    assert week_boundaries(date(2026, 10, 11)) == (
        date(2026, 9, 21),
        date(2026, 9, 28),
        date(2026, 10, 5),
    )


def test_splits_days_into_two_weeks():
    client = FakeClient(
        [
            {
                "ResultsByTime": [
                    day("2026-10-04", {"EC2": 10}),
                    day("2026-10-05", {"EC2": 4, "S3": 1}),
                    day("2026-10-06", {"EC2": 6}),
                ]
            }
        ]
    )
    previous, current, period = fetch_weekly_costs(client, today=date(2026, 10, 14))
    assert previous == {"EC2": pytest.approx(10)}
    assert current == {"EC2": pytest.approx(10), "S3": pytest.approx(1)}
    assert period == (date(2026, 10, 5), date(2026, 10, 12))


def test_follows_pagination():
    client = FakeClient(
        [
            {"ResultsByTime": [day("2026-10-04", {"EC2": 1})], "NextPageToken": "abc"},
            {"ResultsByTime": [day("2026-10-05", {"EC2": 2})]},
        ]
    )
    previous, current, _ = fetch_weekly_costs(client, today=date(2026, 10, 14))
    assert len(client.calls) == 2
    assert client.calls[1]["NextPageToken"] == "abc"
    assert previous == {"EC2": pytest.approx(1)}
    assert current == {"EC2": pytest.approx(2)}


def test_asks_for_daily_costs_grouped_by_service():
    client = FakeClient([{"ResultsByTime": []}])
    fetch_weekly_costs(client, today=date(2026, 10, 14))
    call = client.calls[0]
    assert call["Granularity"] == "DAILY"
    assert call["GroupBy"] == [{"Type": "DIMENSION", "Key": "SERVICE"}]
    assert call["TimePeriod"] == {"Start": "2026-09-28", "End": "2026-10-12"}
