"""Send the HTML report through Amazon SES, and look up the AWS account number."""

from __future__ import annotations

from typing import Any

from cost_explainer.deliver import clean_subject


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