import json
import urllib.error

from cost_explainer.compare import compare, format_report
from cost_explainer.llm import (
    MAX_INPUT_CHARS,
    MAX_OUTPUT_TOKENS,
    build_request,
    explain,
    extract_text,
)

GOOD = {
    "steps": [
        {"type": "thought"},
        {"type": "model_output", "content": [{"type": "text", "text": "CloudWatch rose."}]},
    ]
}


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


def ok_opener(payload, seen=None):
    def opener(request, timeout):
        if seen is not None:
            seen["request"] = request
            seen["timeout"] = timeout
        return FakeResponse(json.dumps(payload).encode())

    return opener


def failing_opener(error):
    def opener(request, timeout):
        raise error

    return opener


def test_extract_text_skips_thought_step():
    assert extract_text(GOOD) == "CloudWatch rose."


def test_extract_text_returns_none_when_missing():
    assert extract_text({}) is None
    assert extract_text({"steps": [{"type": "thought"}]}) is None


def test_explain_returns_text_and_sends_key_in_header():
    seen = {}
    result = explain("report", api_key="k", opener=ok_opener(GOOD, seen))
    assert result == "CloudWatch rose."
    assert seen["request"].get_header("X-goog-api-key") == "k"
    assert seen["timeout"] > 0


def test_no_api_key_returns_none_without_calling_out(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    def opener(request, timeout):
        raise AssertionError("should not be called")

    assert explain("report", opener=opener) is None


def test_http_error_returns_none():
    error = urllib.error.HTTPError("url", 429, "Too Many Requests", {}, None)
    assert explain("report", api_key="k", opener=failing_opener(error)) is None


def test_network_error_returns_none():
    error = urllib.error.URLError("no network")
    assert explain("report", api_key="k", opener=failing_opener(error)) is None


def test_timeout_returns_none():
    assert explain("report", api_key="k", opener=failing_opener(TimeoutError())) is None


def test_invalid_json_returns_none():
    def opener(request, timeout):
        return FakeResponse(b"not json")

    assert explain("report", api_key="k", opener=opener) is None


def test_unexpected_shape_returns_none():
    assert explain("report", api_key="k", opener=ok_opener({"steps": "oops"})) is None


def test_request_is_redacted_and_capped():
    report = "Account 123456789012 " + "x" * (MAX_INPUT_CHARS * 2)
    body = build_request(report, "some-model")
    assert "123456789012" not in body["input"]
    assert len(body["input"]) < MAX_INPUT_CHARS + 50


def test_request_limits_output_and_marks_data_untrusted():
    body = build_request("report", "some-model")
    assert body["generation_config"]["max_output_tokens"] == MAX_OUTPUT_TOKENS
    assert "untrusted" in body["system_instruction"]
    assert body["model"] == "some-model"


def test_system_instruction_leads_with_usage():
    body = build_request("report", "m")
    assert "usage (excluding tax)" in body["system_instruction"]
    assert "usage was steady" in body["system_instruction"]


def test_request_carries_usage_and_total_lines():
    report = format_report(compare({"EC2": 10.0, "Tax": 1.0}, {"EC2": 10.0, "Tax": 41.0}))
    body = build_request(report, "m")
    assert "Usage (excluding tax): $10.00 -> $10.00" in body["input"]
    assert "Total (including tax): $11.00 -> $51.00" in body["input"]
    assert "Usage was steady" in body["input"]
