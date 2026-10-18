"""Send the finished report by email: plain text through SNS, or HTML through SES.

Also looks up the AWS account number shown in the HTML report.

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


def get_account_id(client: Any = None) -> str:
    if client is None:
        import boto3

        client = boto3.client("sts")
    return client.get_caller_identity()["Account"]


def send_html_report(
    *,
    sender: str,
    recipient: str,
    subject: str,
    html: str,
    text: str,
    client: Any = None,
) -> str:
    """Send one email with an HTML body and a plain-text fallback. Returns the SES message id."""
    if client is None:
        import boto3

        client = boto3.client("sesv2")
    response = client.send_email(
        FromEmailAddress=sender,
        Destination={"ToAddresses": [recipient]},
        Content={
            "Simple": {
                "Subject": {"Data": clean_subject(subject), "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": html, "Charset": "UTF-8"},
                    "Text": {"Data": text, "Charset": "UTF-8"},
                },
            }
        },
    )
    return response["MessageId"]