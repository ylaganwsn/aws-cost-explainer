"""AWS Lambda entry point: fetch -> compare -> explain -> deliver.

Settings come from environment variables, so Terraform can change them without code changes:
  SNS_TOPIC_ARN         where to send the plain-text email
  GEMINI_API_KEY        read by llm.py (in AWS it is fetched from SSM, see below)
  GEMINI_KEY_PARAMETER  name of the SSM SecureString parameter that holds the Gemini key
  USE_SAMPLE_DATA       "true" = use examples/sample_cost_data.json instead of calling AWS
  USE_LLM               "false" = skip the LLM explanation (default: on)
  DRY_RUN               "true" = print the report instead of sending it
  SES_SENDER, SES_RECIPIENT  both set = send the HTML email through SES (falls back to SNS)
  ACCOUNT_NAME          optional friendly name shown next to the account number
  MIN_ABS_CHANGE, MIN_PCT_CHANGE, TOP_N   report thresholds
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable, Mapping, MutableMapping
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from . import deliver, fetch, llm, monthly, report_html
from .compare import compare, format_report, parse_costs
from .redact import redact

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE = Path(__file__).resolve().parents[2] / "examples" / "sample_cost_data.json"


def load_sample(path: str | Path | None = None) -> tuple[dict[str, float], dict[str, float], str]:
    """Load the fake Cost Explorer response and return (previous, current, period_label)."""
    sample_path = Path(path or os.environ.get("SAMPLE_DATA_PATH") or DEFAULT_SAMPLE)
    response = json.loads(sample_path.read_text())
    previous, current = parse_costs(response)[-2:]
    period = response["ResultsByTime"][-1]["TimePeriod"]
    return previous, current, f"{period['Start']} to {period['End']}"


def get_costs(
    use_sample: bool, ce_client: Any = None
) -> tuple[dict[str, float], dict[str, float], str]:
    """Return (previous_week, current_week, period_label) from the sample file or AWS."""
    if use_sample:
        return load_sample()
    previous, current, (start, end) = fetch.fetch_weekly_costs(ce_client)
    return previous, current, f"{start} to {end - timedelta(days=1)}"


def build_subject(result: dict[str, Any], label: str) -> str:
    pct = result["total_pct"]
    pct_text = f"{pct:+.1f}%" if pct is not None else "n/a"
    return f"AWS cost report {label}: ${result['current_total']:.2f} ({pct_text})"


def send_html_email(
    env: Mapping[str, str],
    result: dict[str, Any],
    label: str,
    report: str,
    explanation: str | None,
    ce_client: Any = None,
    ses_client: Any = None,
    sts_client: Any = None,
) -> str:
    """Build the month-to-date table and send the HTML email through SES."""
    last = date.fromisoformat(label.split(" to ")[-1])
    first, end = monthly.month_bounds(last)
    if ce_client is None:
        import boto3

        ce_client = boto3.client("ce", region_name="us-east-1")
    days = monthly.get_daily_by_service(ce_client, first, end)
    table = monthly.build_month_table(days, first, last)
    html = report_html.render_html(
        account=deliver.get_account_id(sts_client),
        month_table=table,
        result=result,
        week_label=label,
        explanation=redact(explanation) if explanation else None,
        account_name=env.get("ACCOUNT_NAME") or None,
    )
    return deliver.send_html_report(
        sender=env["SES_SENDER"],
        recipient=env["SES_RECIPIENT"],
        subject=build_subject(result, label),
        html=html,
        text=deliver.build_message(report, explanation),
        client=ses_client,
    )


def run(
    env: Mapping[str, str],
    ce_client: Any = None,
    sns_client: Any = None,
    explain_fn: Callable[[str], str | None] = llm.explain,
) -> dict[str, Any]:
    """Do the whole job and return a summary of what happened."""
    use_sample = env.get("USE_SAMPLE_DATA", "").lower() == "true"
    use_llm = env.get("USE_LLM", "true").lower() != "false"
    dry_run = env.get("DRY_RUN", "").lower() == "true"

    previous, current, label = get_costs(use_sample, ce_client)
    result = compare(
        previous,
        current,
        min_abs_change=float(env.get("MIN_ABS_CHANGE", "1.0")),
        min_pct_change=float(env.get("MIN_PCT_CHANGE", "20.0")),
        top_n=int(env.get("TOP_N", "5")),
    )
    report = format_report(result, label)
    explanation = explain_fn(report) if use_llm else None

    message_id = None
    channel = None
    if dry_run:
        print(report)
        if explanation:
            print(f"\nWhat this means\n---------------\n{explanation}")
    else:
        if env.get("SES_SENDER") and env.get("SES_RECIPIENT") and not use_sample:
            try:
                message_id = send_html_email(env, result, label, report, explanation, ce_client)
                channel = "ses"
            # Deliberately broad: if the HTML email fails, the plain-text report must still go out.
            except Exception as exc:  # noqa: BLE001
                logger.warning("HTML email failed (%s); falling back to SNS", type(exc).__name__)
        if message_id is None:
            message_id = deliver.send_report(
                env.get("SNS_TOPIC_ARN", ""),
                build_subject(result, label),
                report,
                explanation,
                client=sns_client,
            )
            channel = "sns"
    return {
        "report": report,
        "explanation": explanation,
        "message_id": message_id,
        "channel": channel,
        "used_sample_data": use_sample,
    }


def fetch_api_key_from_ssm(parameter_name: str, client: Any = None) -> str | None:
    """Read the Gemini key from SSM Parameter Store. Return None on any failure."""
    try:
        if client is None:
            import boto3  # imported here so local runs and tests don't need AWS

            client = boto3.client("ssm")
        response = client.get_parameter(Name=parameter_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    # Deliberately broad: a missing key must never stop the report from being sent.
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read the Gemini key from SSM (%s)", type(exc).__name__)
        return None


def load_api_key(env: MutableMapping[str, str], ssm_client: Any = None) -> None:
    """If no key is set but an SSM parameter name is, fetch the key into env."""
    if env.get("GEMINI_API_KEY") or env.get("USE_LLM", "true").lower() == "false":
        return
    parameter_name = env.get("GEMINI_KEY_PARAMETER")
    if not parameter_name:
        return
    key = fetch_api_key_from_ssm(parameter_name, ssm_client)
    if key:
        env["GEMINI_API_KEY"] = key


def handler(event: dict[str, Any] | None, context: Any) -> dict[str, Any]:
    """The function AWS Lambda calls."""
    logging.getLogger().setLevel(logging.INFO)
    load_api_key(os.environ)
    outcome = run(os.environ)
    logger.info(
        "Report done: message_id=%s, channel=%s, used_llm=%s, used_sample_data=%s",
        outcome["message_id"],
        outcome["channel"],
        outcome["explanation"] is not None,
        outcome["used_sample_data"],
    )
    return {
        "statusCode": 200,
        "message_id": outcome["message_id"],
        "channel": outcome["channel"],
        "used_llm": outcome["explanation"] is not None,
    }