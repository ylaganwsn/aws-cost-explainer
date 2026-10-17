from cost_explainer.deliver_html import get_account_id, send_html_report


class FakeSes:
    def __init__(self):
        self.calls = []

    def send_email(self, **kwargs):
        self.calls.append(kwargs)
        return {"MessageId": "abc"}


class FakeSts:
    def get_caller_identity(self):
        return {"Account": "123456789012"}


def test_send_html_report_builds_request():
    ses = FakeSes()
    message_id = send_html_report(
        sender="a@example.com",
        recipient="b@example.com",
        subject="Weekly\nreport",
        html="<p>hi</p>",
        text="hi",
        client=ses,
    )
    assert message_id == "abc"
    call = ses.calls[0]
    assert call["FromEmailAddress"] == "a@example.com"
    assert call["Destination"] == {"ToAddresses": ["b@example.com"]}
    simple = call["Content"]["Simple"]
    assert "\n" not in simple["Subject"]["Data"]
    assert simple["Body"]["Html"]["Data"] == "<p>hi</p>"
    assert simple["Body"]["Text"]["Data"] == "hi"


def test_get_account_id():
    assert get_account_id(FakeSts()) == "123456789012"