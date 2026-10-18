import json
from pathlib import Path

import pytest

from cost_explainer.compare import (
    Change,
    compare,
    format_report,
    is_usage,
    parse_costs,
    steady_message,
)

SAMPLE = Path(__file__).resolve().parents[1] / "examples" / "sample_cost_data.json"


@pytest.fixture
def periods():
    return parse_costs(json.loads(SAMPLE.read_text()))


def test_parse_costs_returns_two_periods(periods):
    assert len(periods) == 2
    assert periods[1]["Amazon Bedrock"] == pytest.approx(4.75)
    assert "Amazon Bedrock" not in periods[0]


def test_detects_spike_and_new_service(periods):
    result = compare(*periods)
    names = [c.service for c in result["top_movers"]]
    assert names[0] == "Amazon CloudWatch"  # +5.85
    assert "Amazon Bedrock" in names
    assert result["new_services"] == ["Amazon Bedrock"]


def test_percent_change(periods):
    result = compare(*periods)
    cw = next(c for c in result["top_movers"] if c.service == "Amazon CloudWatch")
    assert cw.pct == pytest.approx(557.14, abs=0.01)


def test_new_service_has_no_percent(periods):
    result = compare(*periods)
    bedrock = next(c for c in result["top_movers"] if c.service == "Amazon Bedrock")
    assert bedrock.is_new and bedrock.pct is None


def test_threshold_filters_small_changes(periods):
    result = compare(*periods)
    names = [c.service for c in result["top_movers"]]
    assert "Amazon Elastic Compute Cloud - Compute" not in names  # +0.15, below $1
    assert "AWS Lambda" not in names
    assert "Amazon Relational Database Service" not in names  # unchanged


def test_percent_threshold_filters_large_but_proportionally_small_changes():
    prev = {"EC2": 1000.0}
    curr = {"EC2": 1010.0}  # +$10 but only 1%
    assert compare(prev, curr)["top_movers"] == []
    assert len(compare(prev, curr, min_pct_change=0.5)["top_movers"]) == 1


def test_gone_service():
    result = compare({"A": 5.0}, {"A": 0.0})
    assert result["gone_services"] == ["A"]


def test_top_n_limit():
    prev = {f"S{i}": 1.0 for i in range(10)}
    curr = {f"S{i}": 10.0 + i for i in range(10)}
    assert len(compare(prev, curr, top_n=3)["top_movers"]) == 3


def test_totals(periods):
    result = compare(*periods)
    assert result["previous_total"] == pytest.approx(28.80)
    assert result["current_total"] == pytest.approx(40.32)
    assert result["total_delta"] == pytest.approx(11.52)


def test_zero_previous_total():
    result = compare({}, {"A": 3.0})
    assert result["total_pct"] is None
    assert result["new_services"] == ["A"]


def test_report_works_without_llm(periods):
    text = format_report(compare(*periods), "test")
    assert "Amazon CloudWatch" in text
    assert "NEW" in text


def test_empty_report():
    text = format_report(compare({"A": 1.0}, {"A": 1.0}))
    assert "Usage was steady: no service changed by both more than $1.00 and 20%" in text


def test_rise_past_dollar_but_not_percent_threshold_is_steady():
    result = compare({"EC2": 100.0}, {"EC2": 105.0})  # +$5 but only +5%
    assert result["top_movers"] == []
    assert result["usage_steady"] is True
    assert "Usage was steady" in format_report(result)


def test_usage_totals_exclude_tax(periods):
    result = compare(*periods)
    assert result["usage_previous"] == pytest.approx(26.20)
    assert result["usage_current"] == pytest.approx(37.02)
    assert result["usage_delta"] == pytest.approx(10.82)
    assert result["usage_pct"] == pytest.approx(41.3)


def test_is_usage_is_case_insensitive():
    assert not is_usage("Tax") and not is_usage("TAX ")
    assert is_usage("Amazon EC2")
    assert not Change("tax", 1.0, 2.0).is_usage


def test_tax_only_change_is_steady_usage():
    result = compare({"EC2": 10.0, "Tax": 1.0}, {"EC2": 10.0, "Tax": 41.0})
    assert result["usage_steady"] is True
    assert result["usage_delta"] == 0
    assert result["total_delta"] == pytest.approx(40.0)
    text = format_report(result)
    assert "Usage was steady" in text
    assert "Top movers" not in text


def test_usage_and_tax_movers_both_listed():
    result = compare({"EC2": 10.0, "Tax": 1.0}, {"EC2": 30.0, "Tax": 41.0})
    assert result["usage_steady"] is False
    assert [c.service for c in result["top_movers"]] == ["Tax", "EC2"]


def test_report_puts_usage_before_total(periods):
    text = format_report(compare(*periods))
    assert "Usage (excluding tax): $26.20 -> $37.02" in text
    assert text.index("Usage (excluding tax)") < text.index("Total (including tax)")


def test_steady_message_uses_thresholds():
    result = compare({"A": 1.0}, {"A": 1.0}, min_abs_change=5, min_pct_change=12.5)
    assert steady_message(result) == (
        "Usage was steady: no service changed by both more than $5.00 and 12.5%"
    )


def test_change_dataclass():
    c = Change("X", 10.0, 15.0)
    assert c.delta == 5.0 and c.pct == 50.0
