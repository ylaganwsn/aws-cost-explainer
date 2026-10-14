"""AWS Lambda entry point: fetch -> compare -> explain -> deliver.

Settings come from environment variables, so Terraform can change them without code changes:
  SNS_TOPIC_ARN    where to send the email
  GEMINI_API_KEY   read by llm.py (in AWS it will come from SSM)
  USE_SAMPLE_DATA  "true" = use examples/sample_cost_data.json instead of calling AWS
  USE_LLM          "false" = skip the LLM explanation (default: on)
  DRY_RUN          "true" = print the report instead of sending it
  MIN_ABS_CHANGE, MIN_PCT_CHANGE, TOP_N   report thresholds
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable, Mapping
from datetime import timedelta
from pathlib import Path
from typing import Any

from . import deliver, fetch, llm
from .compare import compare, format_report, parse_costs

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
    if dry_run:
        print(report)
        if explanation:
            print(f"\nWhat this means\n---------------\n{explanation}")
    else:
        message_id = deliver.send_report(
            env.get("SNS_TOPIC_ARN", ""),
            build_subject(result, label),
            report,
            explanation,
            client=sns_client,
        )
    return {
        "report": report,
        "explanation": explanation,
        "message_id": message_id,
        "used_sample_data": use_sample,
    }


def handler(event: dict[str, Any] | None, context: Any) -> dict[str, Any]:
    """The function AWS Lambda calls."""
    logging.getLogger().setLevel(logging.INFO)
    outcome = run(os.environ)
    logger.info(
        "Report done: message_id=%s, used_llm=%s, used_sample_data=%s",
        outcome["message_id"],
        outcome["explanation"] is not None,
        outcome["used_sample_data"],
    )
    return {
        "statusCode": 200,
        "message_id": outcome["message_id"],
        "used_llm": outcome["explanation"] is not None,
    }