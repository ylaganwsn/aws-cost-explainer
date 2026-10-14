import pytest

from cost_explainer.compare import compare
from cost_explainer.fetch import week_boundaries
from cost_explainer.handler import build_subject, handler, run


class FakeSNS:
    def __init__(self):
        self.calls = []

    def publish(self, **kwargs):
        self.calls.append(kwargs)
        return {"MessageId": "abc-123"}


class FakeCE:
    def __init__(self, days):
        self.days = days
        self.calls = 0

    def get_cost_and_usage(self, **kwargs):
        self.calls += 1
        return {"ResultsByTime": self.days}


def day(start, costs):
    return {
        "TimePeriod": {"Start": start, "End": start},
        "Groups": [
            {"Keys": [name], "Metrics": {"UnblendedCost": {"Amount": str(amount), "Unit": "USD"}}}
            for name, amount in costs.items()
        ],
    }


def fake_explain(report):
    return "Because reasons."


def no_explain(report):
    return None


def test_sample_dry_run_builds_report_and_does_not_publish(capsys):
    outcome = run(
        {"USE_SAMPLE_DATA": "true", "DRY_RUN": "true"}, sns_client=FakeSNS(), explain_fn=fake_explain
    )
    assert "Amazon CloudWatch" in outcome["report"]
    assert outcome["message_id"] is None
    assert "Amazon CloudWatch" in capsys.readouterr().out


def test_publishes_to_sns_with_report_and_explanation():
    sns = FakeSNS()
    env = {"USE_SAMPLE_DATA": "true", "SNS_TOPIC_ARN": "arn:topic"}
    outcome = run(env, sns_client=sns, explain_fn=fake_explain)
    assert outcome["message_id"] == "abc-123"
    call = sns.calls[0]
    assert call["TopicArn"] == "arn:topic"
    assert "Amazon CloudWatch" in call["Message"]
    assert "Because reasons." in call["Message"]


def test_report_still_sent_when_llm_fails():
    sns = FakeSNS()
    env = {"USE_SAMPLE_DATA": "true", "SNS_TOPIC_ARN": "arn:topic"}
    run(env, sns_client=sns, explain_fn=no_explain)
    message = sns.calls[0]["Message"]
    assert "Amazon CloudWatch" in message
    assert "What this means" not in message


def test_use_llm_false_skips_the_llm():
    def must_not_run(report):
        raise AssertionError("LLM should not be called")

    env = {"USE_SAMPLE_DATA": "true", "DRY_RUN": "true", "USE_LLM": "false"}
    outcome = run(env, explain_fn=must_not_run)
    assert outcome["explanation"] is None


def test_missing_topic_without_dry_run_raises():
    env = {"USE_SAMPLE_DATA": "true", "USE_LLM": "false"}
    with pytest.raises(ValueError):
        run(env, sns_client=FakeSNS())


def test_real_fetch_path_uses_cost_explorer_client():
    prev_start, curr_start, _ = week_boundaries()
    ce = FakeCE(
        [day(prev_start.isoformat(), {"EC2": 10.0}), day(curr_start.isoformat(), {"EC2": 20.0})]
    )
    outcome = run({"DRY_RUN": "true", "USE_LLM": "false"}, ce_client=ce)
    assert ce.calls == 1
    assert "EC2" in outcome["report"]
    assert outcome["used_sample_data"] is False


def test_subject_summarises_total_and_percent():
    subject = build_subject(compare({"A": 28.8}, {"A": 40.32}), "2026-10-05 to 2026-10-11")
    assert "$40.32" in subject
    assert "+40.0%" in subject


def test_handler_returns_summary(monkeypatch):
    monkeypatch.setenv("USE_SAMPLE_DATA", "true")
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("USE_LLM", "false")
    result = handler({}, None)
    assert result["statusCode"] == 200
    assert result["used_llm"] is False