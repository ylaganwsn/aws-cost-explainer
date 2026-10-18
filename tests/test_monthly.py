from datetime import date

from cost_explainer.monthly import (
    build_month_table,
    get_daily_by_service,
    month_bounds,
    week_label,
    week_ranges,
)


class FakeCe:
    """Stands in for the boto3 Cost Explorer client; returns the given pages in order."""

    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def get_cost_and_usage(self, **kwargs):
        self.calls.append(kwargs)
        return self.pages[len(self.calls) - 1]


def result_day(day, costs):
    return {
        "TimePeriod": {"Start": day, "End": day},
        "Groups": [
            {"Keys": [service], "Metrics": {"UnblendedCost": {"Amount": str(amount)}}}
            for service, amount in costs.items()
        ],
    }


def test_month_bounds_end_is_exclusive():
    assert month_bounds(date(2026, 10, 11)) == (date(2026, 10, 1), date(2026, 10, 12))


def test_week_ranges_are_clipped_to_the_month():
    assert week_ranges(date(2026, 10, 1), date(2026, 10, 11)) == [
        (date(2026, 10, 1), date(2026, 10, 4)),
        (date(2026, 10, 5), date(2026, 10, 11)),
    ]


def test_week_ranges_single_day():
    assert week_ranges(date(2026, 11, 1), date(2026, 11, 1)) == [
        (date(2026, 11, 1), date(2026, 11, 1))
    ]


def test_week_label_marks_partial_weeks_with_day_count():
    assert week_label(date(2026, 10, 1), date(2026, 10, 4)) == "Oct 1-4 (4 days)"
    assert week_label(date(2026, 10, 5), date(2026, 10, 11)) == "Oct 5-11"
    assert week_label(date(2026, 10, 12), date(2026, 10, 17)) == "Oct 12-17 (6 days)"
    assert week_label(date(2026, 11, 1), date(2026, 11, 1)) == "Nov 1 (1 day)"


def test_get_daily_by_service_follows_pages_and_sums():
    page1 = {
        "ResultsByTime": [result_day("2026-10-01", {"EC2": 1.0, "Tax": 5.0})],
        "NextPageToken": "t",
    }
    page2 = {"ResultsByTime": [result_day("2026-10-02", {"EC2": 2.0})]}
    ce = FakeCe([page1, page2])
    days = get_daily_by_service(ce, date(2026, 10, 1), date(2026, 10, 3))
    assert days == {
        date(2026, 10, 1): {"EC2": 1.0, "Tax": 5.0},
        date(2026, 10, 2): {"EC2": 2.0},
    }
    assert len(ce.calls) == 2
    assert ce.calls[1]["NextPageToken"] == "t"
    assert ce.calls[0]["TimePeriod"] == {"Start": "2026-10-01", "End": "2026-10-03"}
    assert ce.calls[0]["Granularity"] == "DAILY"


def test_build_month_table_groups_weeks_and_other():
    days = {
        date(2026, 10, 1): {"EC2": 10.0, "Tax": 5.0},
        date(2026, 10, 5): {"EC2": 20.0, "S3": 1.0},
        date(2026, 10, 6): {"EC2": 20.0},
    }
    table = build_month_table(days, date(2026, 10, 1), date(2026, 10, 11), top_n=1)
    assert table["labels"] == ["Oct 1-4 (4 days)", "Oct 5-11"]
    assert table["rows"] == [
        {"service": "EC2", "weeks": [10.0, 40.0], "total": 50.0},
        {"service": "Other", "weeks": [0.0, 1.0], "total": 1.0},
        {"service": "Tax", "weeks": [5.0, 0.0], "total": 5.0},
    ]
    assert table["week_totals"] == [15.0, 41.0]
    assert table["total"] == 56.0
    assert table["month"] == "October 2026"
    assert table["through"] == "2026-10-11"


def test_tax_is_listed_last_even_when_largest():
    days = {date(2026, 10, 1): {"Tax": 90.0, "EC2": 3.0, "S3": 2.0}}
    table = build_month_table(days, date(2026, 10, 1), date(2026, 10, 4), top_n=1)
    assert [r["service"] for r in table["rows"]] == ["EC2", "Other", "Tax"]


def test_build_month_table_drops_zero_services():
    days = {date(2026, 10, 1): {"EC2": 3.0, "SES": 0.0}}
    table = build_month_table(days, date(2026, 10, 1), date(2026, 10, 4))
    assert [r["service"] for r in table["rows"]] == ["EC2"]
