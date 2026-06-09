#!/usr/bin/env python3
"""Generate a Red Flag report by cross-referencing 10-K and transcript JSON reports."""

import argparse
import json
import sys
from pathlib import Path

from analysis.discrepancy_detector import generate_red_flag_report
from analysis.discrepancy_schemas import DiscrepancyInput
from analysis.schemas import AnalystFindings

DEFAULT_OUTPUT_DIR = Path("output")


def default_reports_dir(ticker: str) -> Path:
    return DEFAULT_OUTPUT_DIR / ticker.upper() / "reports"


def load_report(path: Path) -> AnalystFindings:
    if not path.is_file():
        raise FileNotFoundError(f"Report not found: {path}")
    return AnalystFindings.model_validate(json.loads(path.read_text(encoding="utf-8")))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Cross-reference 10-K and transcript analyst JSON reports using a "
            "Discrepancy Taxonomy to produce a Red Flag report."
        )
    )
    parser.add_argument("ticker", help="Stock ticker symbol, e.g. UBER")
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=None,
        help="Directory containing ten_k_report.json and transcript_report.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path for red flag report (default: <reports-dir>/red_flag_report.json)",
    )
    parser.add_argument(
        "--max-flags",
        type=int,
        default=5,
        help="Maximum number of red flags to include (default: 5)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ticker = args.ticker.upper()
    reports_dir = args.reports_dir or default_reports_dir(ticker)
    output_path = args.output or (reports_dir / "red_flag_report.json")

    ten_k_report = load_report(reports_dir / "ten_k_report.json")
    transcript_report = load_report(reports_dir / "transcript_report.json")

    print(f"Cross-referencing reports for {ticker}...")
    report = generate_red_flag_report(
        DiscrepancyInput(
            ticker=ticker,
            ten_k_report=ten_k_report,
            transcript_report=transcript_report,
        ),
        max_flags=args.max_flags,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(f"Saved Red Flag report to {output_path}")
    print(report.summary)
    for index, flag in enumerate(report.red_flags, start=1):
        print(
            f"{index}. [{flag.discrepancy_type.value}] (severity {flag.severity}) {flag.title}"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FileNotFoundError as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
