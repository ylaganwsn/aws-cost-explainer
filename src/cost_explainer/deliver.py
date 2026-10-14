"""Send the finished report by email through an SNS topic.

Unlike the LLM step, delivery is essential: errors are raised, not swallowed.
"""

from __future__ import annotations

from typing import Any

from .redact import redact

SUBJECT_MAX = 100  # SNS email subjects must be one line and at most 100 characters


def make_client() -> Any:
    """Create a real SNS client. boto3 is imported here so tests don't need AWS."""
    import boto3

    return boto3.client("sns")


def clean_subject(subject: str) -> str:
    """Make the subject a single line, capped at the SNS limit."""
    return " ".join(subject.split())[:SUBJECT_MAX]


def build_message(report: str, explanation: str | None) -> str:
    """Combine the report with the optional explanation, redacting anything sensitive."""
    if explanation:
        text = f"{report}\n\nWhat this means\n---------------\n{explanation}\n"
    else:
        text = f"{report}\n"
    return redact(text)


def send_report(
    topic_arn: str,
    subject: str,
    report: str,
    explanation: str | None = None,
    client: Any = None,
) -> str:
    """Publish the report to the SNS topic and return the message ID."""
    if not topic_arn:
        raise ValueError("topic_arn is required")
    client = client or make_client()
    response = client.publish(
        TopicArn=topic_arn,
        Subject=clean_subject(subject),
        Message=build_message(report, explanation),
    )
    return response["MessageId"]