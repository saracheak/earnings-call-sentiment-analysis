#!/usr/bin/env python3
"""Run the Fact Checker agent against Red Flag hypotheses and raw source documents."""

import argparse
import json
import sys
from pathlib import Path

from edgar import Company, set_identity

from analysis.discrepancy_schemas import RedFlagReport
from analysis.fact_checker import run_fact_checker
from analysis.markdown_report import render_audit_markdown

DEFAULT_OUTPUT_DIR = Path("output")
DEFAULT_EDGAR_IDENTITY = "Sara Cheakdkaipejchara saracheak@gmail.com"


def get_edgar_identity() -> str:
    import os

    return os.environ.get("EDGAR_IDENTITY", DEFAULT_EDGAR_IDENTITY)


def default_ticker_dir(ticker: str) -> Path:
    return DEFAULT_OUTPUT_DIR / ticker.upper()


def default_reports_dir(ticker: str) -> Path:
    return default_ticker_dir(ticker) / "reports"


def default_transcript_path(ticker: str) -> Path:
    return default_ticker_dir(ticker) / f"{ticker.upper()}_earnings_transcript.txt"


def load_text(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    return path.read_text(encoding="utf-8")


def load_red_flag_report(path: Path) -> RedFlagReport:
    if not path.is_file():
        raise FileNotFoundError(f"Red flag report not found: {path}")
    return RedFlagReport.model_validate(json.loads(path.read_text(encoding="utf-8")))


def resolve_ten_k_path(ticker: str, explicit_path: Path | None) -> tuple[Path, str]:
    if explicit_path:
        return explicit_path.resolve(), load_text(explicit_path)

    ticker_dir = default_ticker_dir(ticker)
    cached_files = sorted(ticker_dir.glob(f"{ticker.upper()}_10-K*.txt"))
    if cached_files:
        path = cached_files[-1]
        return path.resolve(), load_text(path)

    set_identity(get_edgar_identity())
    company = Company(ticker)
    filing = company.get_filings(form="10-K").latest()
    text = filing.text()
    path = (ticker_dir / f"{ticker.upper()}_10-K_{filing.filing_date}.txt").resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path, text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fact Checker agent: verify Red Flag hypotheses against raw 10-K and "
            "transcript source files and produce an audit-ready Markdown report."
        )
    )
    parser.add_argument("ticker", help="Stock ticker symbol, e.g. UBER")
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=None,
        help="Directory containing red_flag_report.json (default: output/<TICKER>/reports)",
    )
    parser.add_argument(
        "--ten-k-file",
        type=Path,
        default=None,
        help="Path to raw 10-K text (default: cached file or fetch from SEC EDGAR)",
    )
    parser.add_argument(
        "--transcript-file",
        type=Path,
        default=None,
        help="Path to raw transcript text (default: output/<TICKER>/<TICKER>_earnings_transcript.txt)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Markdown output path (default: <reports-dir>/fact_check_audit_report.md)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ticker = args.ticker.upper()
    reports_dir = args.reports_dir or default_reports_dir(ticker)
    transcript_path = (args.transcript_file or default_transcript_path(ticker)).resolve()
    output_path = args.output or (reports_dir / "fact_check_audit_report.md")

    red_flag_report = load_red_flag_report(reports_dir / "red_flag_report.json")
    ten_k_path, ten_k_text = resolve_ten_k_path(ticker, args.ten_k_file)
    transcript_text = load_text(transcript_path)

    print(f"Running Fact Checker for {ticker}...")
    fact_check_report = run_fact_checker(
        red_flag_report=red_flag_report,
        ten_k_text=ten_k_text,
        transcript_text=transcript_text,
        ten_k_path=ten_k_path,
        transcript_path=transcript_path,
    )

    markdown = render_audit_markdown(fact_check_report, output_dir=reports_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")

    verified_json_path = reports_dir / "fact_check_report.json"
    verified_json_path.write_text(fact_check_report.model_dump_json(indent=2), encoding="utf-8")

    print(fact_check_report.summary)
    print(f"Saved audit Markdown report to {output_path}")
    print(f"Saved fact check JSON to {verified_json_path}")
    print(f"Verified: {len(fact_check_report.verified_flags)} | Discarded: {len(fact_check_report.discarded_flags)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FileNotFoundError as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
