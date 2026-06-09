#!/usr/bin/env python3
"""Run LangGraph multi-agent analysis on a 10-K and earnings transcript."""

import argparse
import os
import sys
from pathlib import Path

from edgar import Company, set_identity

from analysis.graph import run_analysis, save_reports

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = Path("output")
DEFAULT_EDGAR_IDENTITY = "Sara Cheakdkaipejchara saracheak@gmail.com"


def get_edgar_identity() -> str:
    return os.environ.get("EDGAR_IDENTITY", DEFAULT_EDGAR_IDENTITY)


def default_transcript_path(ticker: str) -> Path:
    return DEFAULT_OUTPUT_DIR / ticker.upper() / f"{ticker.upper()}_earnings_transcript.txt"


def load_text(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    return path.read_text(encoding="utf-8")


def fetch_latest_10k_text(ticker: str) -> str:
    set_identity(get_edgar_identity())
    company = Company(ticker)
    filing = company.get_filings(form="10-K").latest()
    return filing.text()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run 10-K Analyst and Transcript Analyst workers to produce "
            "two structured JSON reports."
        )
    )
    parser.add_argument("ticker", help="Stock ticker symbol, e.g. UBER")
    parser.add_argument(
        "--ten-k-file",
        type=Path,
        default=None,
        help="Path to a 10-K text file (default: fetch latest 10-K from SEC EDGAR)",
    )
    parser.add_argument(
        "--transcript-file",
        type=Path,
        default=None,
        help="Path to earnings transcript text (default: output/<TICKER>/<TICKER>_earnings_transcript.txt)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for JSON reports (default: output/<TICKER>/reports)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ticker = args.ticker.upper()
    output_dir = args.output_dir or (DEFAULT_OUTPUT_DIR / ticker / "reports")
    transcript_file = args.transcript_file or default_transcript_path(ticker)

    print(f"Loading earnings transcript from {transcript_file}...")
    transcript_text = load_text(transcript_file)

    if args.ten_k_file:
        print(f"Loading 10-K from {args.ten_k_file}...")
        ten_k_text = load_text(args.ten_k_file)
    else:
        print(f"Fetching latest 10-K for {ticker} from SEC EDGAR...")
        ten_k_text = fetch_latest_10k_text(ticker)

    print("Running 10-K Analyst and Transcript Analyst workers in parallel...")
    result = run_analysis(
        ticker=ticker,
        ten_k_text=ten_k_text,
        transcript_text=transcript_text,
    )

    ten_k_path, transcript_path = save_reports(result, output_dir)
    print(f"Saved 10-K report to {ten_k_path}")
    print(f"Saved transcript report to {transcript_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
