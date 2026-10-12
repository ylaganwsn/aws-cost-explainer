import pytest

from cost_explainer.redact import redact


@pytest.mark.parametrize(
    "text,leak",
    [
        ("Account 123456789012 spent more", "123456789012"),
        ("Account 1234-5678-9012 spent more", "1234-5678-9012"),
        ("key AKIAIOSFODNN7EXAMPLE found", "AKIAIOSFODNN7EXAMPLE"),
        ("api_key=abc123supersecret", "abc123supersecret"),
        ("password: hunter2", "hunter2"),
        ("Authorization: Bearer abcdef123456", "abcdef123456"),
        ("arn:aws:iam::123456789012:role/my-role", "123456789012"),
        ("https://hooks.slack.com/services/T000/B000/XXXX", "T000"),
        ("sk-ant-api03-abcdefghijklmnop", "abcdefghijklmnop"),
        ("AIzaSyA1234567890abcdefghijklmnop", "A1234567890abcdefghijklmnop"),
        ("ghp_abcdefghijklmnopqrstuvwxyz0123", "abcdefghijklmnopqrstuvwxyz0123"),
    ],
)
def test_redacts_sensitive_text(text, leak):
    assert leak not in redact(text)


def test_keeps_normal_report_text():
    text = "Amazon CloudWatch: $1.05 -> $6.90 (+5.85, +557.1%)"
    assert redact(text) == text


def test_does_not_redact_dollar_amounts_or_dates():
    text = "Total 40.82 USD from 2026-10-05 to 2026-10-12"
    assert redact(text) == text


def test_service_names_survive():
    text = "Amazon Elastic Compute Cloud - Compute and AWS Key Management Service"
    assert redact(text) == text
