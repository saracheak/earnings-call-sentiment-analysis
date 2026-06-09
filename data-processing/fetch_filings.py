#!/usr/bin/env python3
"""Fetch the latest earnings call transcript and 10-Q for a ticker."""

import argparse
import os
import sys
from datetime import date
from pathlib import Path

import requests
from edgar import Company, set_identity

FMP_BASE_URL = "https://financialmodelingprep.com/stable"
DEFAULT_OUTPUT_DIR = Path("output")
DEFAULT_EDGAR_IDENTITY = "Sara Cheakdkaipejchara saracheak@gmail.com"
DEFAULT_FMP_API_KEY = "7eQNl9ZJ6ebp3YRXABaK8HXshV8xwNdb"


def get_fmp_api_key() -> str:
    return os.environ.get("FMP_API_KEY", DEFAULT_FMP_API_KEY)


def get_edgar_identity() -> str:
    return os.environ.get("EDGAR_IDENTITY", DEFAULT_EDGAR_IDENTITY)


def current_calendar_quarter(today: date | None = None) -> tuple[int, int]:
    today = today or date.today()
    return today.year, (today.month - 1) // 3 + 1


def previous_quarter(year: int, quarter: int) -> tuple[int, int]:
    if quarter == 1:
        return year - 1, 4
    return year, quarter - 1


def fetch_transcript(ticker: str, year: int, quarter: int, api_key: str) -> dict | None:
    response = requests.get(
        f"{FMP_BASE_URL}/earning-call-transcript",
        params={
            "symbol": ticker,
            "year": year,
            "quarter": quarter,
            "apikey": api_key,
        },
        timeout=30,
    )

    if response.status_code == 402:
        raise RuntimeError(
            "The FMP earnings transcript endpoint requires a paid subscription. "
            "Set FMP_API_KEY to an API key with transcript access."
        )
    if response.status_code == 403:
        raise RuntimeError(
            "The FMP API key does not have access to earnings transcripts. "
            "Set FMP_API_KEY to a valid key with transcript access."
        )
    if response.status_code != 200:
        return None

    data = response.json()
    if not data or not isinstance(data, list):
        return None

    transcript = data[0]
    if not transcript.get("content"):
        return None

    return transcript


def find_most_recent_transcript(
    ticker: str, api_key: str, max_quarters: int = 12
) -> tuple[int, int, dict]:
    year, quarter = current_calendar_quarter()

    for _ in range(max_quarters):
        transcript = fetch_transcript(ticker, year, quarter, api_key)
        if transcript is not None:
            return year, quarter, transcript
        year, quarter = previous_quarter(year, quarter)

    raise RuntimeError(
        f"No earnings call transcript found for {ticker} in the last {max_quarters} quarters."
    )


def save_earnings_transcript(ticker: str, output_dir: Path, api_key: str) -> Path:
    year, quarter, transcript = find_most_recent_transcript(ticker, api_key)
    output_path = output_dir / f"{ticker}_Q{quarter}_{year}_earnings_transcript.txt"
    output_path.write_text(transcript["content"], encoding="utf-8")
    return output_path


def save_latest_10q(ticker: str, output_dir: Path) -> Path:
    set_identity(get_edgar_identity())
    company = Company(ticker)
    filing = company.get_filings(form="10-Q").latest()

    output_path = output_dir / f"{ticker}_10-Q_{filing.filing_date}.txt"
    output_path.write_text(filing.text(), encoding="utf-8")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Save the latest earnings call transcript and 10-Q for a ticker."
    )
    parser.add_argument("ticker", help="Stock ticker symbol, e.g. UBER")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory to save files (default: output/<TICKER>)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ticker = args.ticker.upper()
    output_dir = args.output_dir or (DEFAULT_OUTPUT_DIR / ticker)
    output_dir.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []

    print(f"Fetching latest 10-Q for {ticker}...")
    try:
        tenq_path = save_latest_10q(ticker, output_dir)
    except Exception as error:
        errors.append(f"10-Q: {error}")
        print(f"Failed to save 10-Q: {error}", file=sys.stderr)
    else:
        print(f"Saved 10-Q to {tenq_path}")

    print(f"Fetching most recent earnings call transcript for {ticker}...")
    try:
        transcript_path = save_earnings_transcript(ticker, output_dir, get_fmp_api_key())
    except Exception as error:
        errors.append(f"earnings transcript: {error}")
        print(f"Failed to save earnings transcript: {error}", file=sys.stderr)
    else:
        print(f"Saved earnings transcript to {transcript_path}")

    if errors:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
