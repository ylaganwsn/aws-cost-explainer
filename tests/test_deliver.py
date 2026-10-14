import pytest

from cost_explainer.deliver import SUBJECT_MAX, build_message, clean_subject, send_report


class FakeSNS:
    """Stands in for boto3's SNS client and records how it was called."""

    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def publish(self, **kwargs):
        if self.error:
            raise self.error
        self.calls.append(kwargs)
        return {"MessageId": "abc-123"}


def test_message_includes_explanation_when_present():
    message = build_message("REPORT", "It went up.")
    assert "REPORT" in message
    assert "What this means" in message
    assert "It went up." in message


def test_message_without_explanation_is_just_the_report():
    message = build_message("REPORT", None)
    assert "REPORT" in message
    assert "What this means" not in message


def test_message_is_redacted():
    assert "123456789012" not in build_message("Account 123456789012 spent more", None)


def test_subject_is_one_line_and_capped():
    subject = clean_subject("line one\nline two " + "x" * 300)
    assert "\n" not in subject
    assert len(subject) == SUBJECT_MAX


def test_send_report_publishes_to_topic_and_returns_id():
    sns = FakeSNS()
    message_id = send_report("arn:aws:sns:us-east-1:111111111111:topic", "Weekly", "REPORT", client=sns)
    assert message_id == "abc-123"
    call = sns.calls[0]
    assert call["TopicArn"] == "arn:aws:sns:us-east-1:111111111111:topic"
    assert call["Subject"] == "Weekly"
    assert "REPORT" in call["Message"]


def test_missing_topic_raises():
    with pytest.raises(ValueError):
        send_report("", "Weekly", "REPORT", client=FakeSNS())


def test_publish_errors_are_not_swallowed():
    with pytest.raises(RuntimeError):
        send_report("arn", "Weekly", "REPORT", client=FakeSNS(error=RuntimeError("boom")))