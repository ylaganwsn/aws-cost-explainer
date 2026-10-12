import json
from pathlib import Path

import pytest

from cost_explainer.compare import Change, compare, format_report, parse_costs

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
    assert "No changes" in text


def test_change_dataclass():
    c = Change("X", 10.0, 15.0)
    assert c.delta == 5.0 and c.pct == 50.0
