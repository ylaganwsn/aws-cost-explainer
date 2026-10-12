"""CLI: ``python -m cost_explainer --sample`` prints the report from bundled sample data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .compare import compare, format_report, parse_costs
from .redact import redact

DEFAULT_SAMPLE = Path(__file__).resolve().parents[2] / "examples" / "sample_cost_data.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cost_explainer", description=__doc__)
    parser.add_argument("--sample", action="store_true", help="use the bundled sample data")
    parser.add_argument("--file", type=Path, help="path to a Cost Explorer JSON response")
    parser.add_argument("--min-abs", type=float, default=1.0, help="min absolute change in USD")
    parser.add_argument("--min-pct", type=float, default=20.0, help="min percent change")
    parser.add_argument("--top", type=int, default=5, help="max movers to show")
    args = parser.parse_args(argv)

    if args.file:
        path = args.file
    elif args.sample:
        path = DEFAULT_SAMPLE
    else:
        parser.error("Phase 1 supports only --sample or --file (AWS fetching comes in Phase 2)")

    response = json.loads(path.read_text())
    periods = parse_costs(response)
    if len(periods) < 2:
        print("Need at least two periods of data.", file=sys.stderr)
        return 1
    result = compare(
        periods[-2],
        periods[-1],
        min_abs_change=args.min_abs,
        min_pct_change=args.min_pct,
        top_n=args.top,
    )
    start = response["ResultsByTime"][-1]["TimePeriod"]["Start"]
    end = response["ResultsByTime"][-1]["TimePeriod"]["End"]
    print(redact(format_report(result, f"{start} to {end}")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
