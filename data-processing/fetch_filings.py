#!/usr/bin/env python3
"""Fetch the latest earnings call transcript and 10-Q for a ticker."""

import argparse
import sys
from pathlib import Path

from edgar import Company, set_identity
from pypdf import PdfReader

from config import get_edgar_identity

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = Path("output")


def default_transcript_pdf(ticker: str) -> Path:
    return REPO_ROOT / "assets" / f"{ticker.lower()}-earnings-call-transcript.pdf"


def earnings_call_pdf_to_txt(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def save_earnings_transcript(ticker: str, output_dir: Path, pdf_path: Path) -> Path:
    if not pdf_path.is_file():
        raise FileNotFoundError(
            f"No earnings call transcript PDF found at {pdf_path}. "
            f"Place a PDF at assets/{ticker.lower()}-earnings-call-transcript.pdf "
            "or pass --transcript-pdf."
        )

    output_path = output_dir / f"{ticker}_earnings_transcript.txt"
    output_path.write_text(earnings_call_pdf_to_txt(pdf_path), encoding="utf-8")
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
    parser.add_argument(
        "--transcript-pdf",
        type=Path,
        default=None,
        help="Path to earnings call transcript PDF (default: assets/<ticker>-earnings-call-transcript.pdf)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ticker = args.ticker.upper()
    output_dir = args.output_dir or (DEFAULT_OUTPUT_DIR / ticker)
    output_dir.mkdir(parents=True, exist_ok=True)
    transcript_pdf = args.transcript_pdf or default_transcript_pdf(ticker)

    errors: list[str] = []

    print(f"Fetching latest 10-Q for {ticker}...")
    try:
        tenq_path = save_latest_10q(ticker, output_dir)
    except Exception as error:
        errors.append(f"10-Q: {error}")
        print(f"Failed to save 10-Q: {error}", file=sys.stderr)
    else:
        print(f"Saved 10-Q to {tenq_path}")

    print(f"Extracting earnings call transcript for {ticker} from {transcript_pdf}...")
    try:
        transcript_path = save_earnings_transcript(ticker, output_dir, transcript_pdf)
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
