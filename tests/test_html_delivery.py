from cost_explainer import handler


class FakeCe:
    def get_cost_and_usage(self, **kwargs):
        return {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2026-10-05", "End": "2026-10-06"},
                    "Groups": [
                        {"Keys": ["EC2"], "Metrics": {"UnblendedCost": {"Amount": "30"}}}
                    ],
                }
            ]
        }


class FakeSes:
    def send_email(self, **kwargs):
        self.kwargs = kwargs
        return {"MessageId": "ses-id"}


class FakeSts:
    def get_caller_identity(self):
        return {"Account": "123456789012"}


class FakeSns:
    def __init__(self):
        self.calls = []

    def publish(self, **kwargs):
        self.calls.append(kwargs)
        return {"MessageId": "sns-id"}


LABEL = "2026-10-05 to 2026-10-11"
COSTS = ({"EC2": 10.0}, {"EC2": 30.0}, LABEL)
ENV = {
    "SES_SENDER": "a@example.com",
    "SES_RECIPIENT": "b@example.com",
    "SNS_TOPIC_ARN": "arn:aws:sns:us-east-1:123456789012:t",
    "USE_LLM": "false",
}


def run_with(monkeypatch, env, html_fn=None):
    monkeypatch.setattr(handler, "get_costs", lambda use_sample, ce_client=None: COSTS)
    if html_fn:
        monkeypatch.setattr(handler, "send_html_email", html_fn)
    sns = FakeSns()
    return handler.run(env, sns_client=sns), sns


def test_send_html_email_puts_account_in_html_only():
    ses = FakeSes()
    result = handler.compare({"EC2": 10.0}, {"EC2": 30.0})
    report = handler.format_report(result, LABEL)
    message_id = handler.send_html_email(ENV, result, LABEL, report, None, FakeCe(), ses, FakeSts())
    body = ses.kwargs["Content"]["Simple"]["Body"]
    assert message_id == "ses-id"
    assert "123456789012" in body["Html"]["Data"]
    assert "123456789012" not in report
    assert ses.kwargs["FromEmailAddress"] == "a@example.com"


def test_run_uses_ses_when_it_works(monkeypatch):
    outcome, sns = run_with(monkeypatch, ENV, lambda *a, **k: "ses-id")
    assert outcome["channel"] == "ses"
    assert outcome["message_id"] == "ses-id"
    assert sns.calls == []


def test_run_falls_back_to_sns_when_ses_fails(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("ses down")

    outcome, sns = run_with(monkeypatch, ENV, boom)
    assert outcome["channel"] == "sns"
    assert len(sns.calls) == 1


def test_run_uses_sns_when_ses_not_configured(monkeypatch):
    env = {"SNS_TOPIC_ARN": ENV["SNS_TOPIC_ARN"], "USE_LLM": "false"}
    outcome, sns = run_with(monkeypatch, env)
    assert outcome["channel"] == "sns"
    assert len(sns.calls) == 1