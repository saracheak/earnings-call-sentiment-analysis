# Earnings Call Sentiment Analysis

Compare what a company **files** in SEC disclosures with what management **says** on the earnings call. This project runs a multi-agent pipeline that extracts structured findings from a 10-K and earnings transcript, cross-references them for inconsistencies, and produces an audit-ready report with citations back to the raw source text.

No paid API keys are required.

## What it does

The pipeline answers a simple question: **does the story on the earnings call match the official filing?**

It looks for three types of inconsistencies:

| Type | Example |
|------|---------|
| **Numerical** | The 10-K reports R&D spend of `$3,109M`, but the CEO never mentions comparable figures on the call |
| **Omission** | The filing lists cybersecurity or supply-chain risks that management never addresses on the call |
| **Sentiment Shift** | The filing uses cautious language (`may`, `adversely affected`), while the CEO emphasizes momentum and confidence |

Unverified red flags are discarded by the Fact Checker to reduce false positives.

## Pipeline

```
┌─────────────────────┐     ┌─────────────────────┐
│   Raw 10-K (SEC)    │     │  Earnings Transcript │
│   via edgartools    │     │  via local PDF       │
└─────────┬───────────┘     └──────────┬──────────┘
          │                            │
          ▼                            ▼
   ┌──────────────┐            ┌──────────────────┐
   │ 10-K Analyst │            │ Transcript Analyst│
   └──────┬───────┘            └────────┬─────────┘
          │         LangGraph           │
          └────────────┬────────────────┘
                       ▼
              ┌─────────────────┐
              │  JSON Reports   │
              └────────┬────────┘
                       ▼
              ┌─────────────────┐
              │   Red Flag      │
              │   Detector      │
              └────────┬────────┘
                       ▼
              ┌─────────────────┐
              │  Fact Checker   │  ← re-reads raw sources
              └────────┬────────┘
                       ▼
              ┌─────────────────┐
              │ Audit Markdown  │
              │     Report      │
              └─────────────────┘
```

## Quick start

### 1. Add your personal details

SEC EDGAR requires a real name and email on every request. Set this before running any script that fetches filings.

```bash
cp .env.example .env
```

Edit `.env` and replace the placeholder with your information:

```bash
EDGAR_IDENTITY="Your Name your.email@example.com"
```

Load it into your shell session:

```bash
export EDGAR_IDENTITY="Your Name your.email@example.com"
```

Or source the file:

```bash
set -a && source .env && set +a
```

The `.env` file is gitignored and will not be committed.

### 2. Install dependencies

```bash
cd data-processing
pip install -r requirements.txt
```

### 3. Add a transcript PDF

Place the earnings call transcript PDF at:

```
assets/<ticker>-earnings-call-transcript.pdf
```

For example: `assets/uber-earnings-call-transcript.pdf`

### 4. Run the full pipeline

```bash
cd data-processing

# Fetch source documents (10-Q + transcript text)
python fetch_filings.py UBER

# Run analyst agents (10-K + transcript → JSON)
python run_analysis.py UBER

# Cross-reference findings → Red Flag report
python run_red_flag_report.py UBER

# Verify red flags against raw sources → audit report
python run_fact_check.py UBER
```

## Scripts

| Script | Purpose |
|--------|---------|
| `fetch_filings.py` | Fetch the latest 10-Q from SEC EDGAR and extract the earnings transcript from a local PDF |
| `run_analysis.py` | Run the **10-K Analyst** and **Transcript Analyst** agents in parallel via LangGraph |
| `run_red_flag_report.py` | Cross-reference the two JSON reports using the Discrepancy Taxonomy |
| `run_fact_check.py` | Run the **Fact Checker** agent to verify red flags against raw source documents |

All scripts take a ticker as the first argument (e.g. `UBER`).

## Agents

### 10-K Analyst

Reads the latest Form 10-K and extracts structured findings:

- Revenue guidance
- Supply chain risks
- R&D spend

Output: `output/<TICKER>/reports/ten_k_report.json`

### Transcript Analyst

Reads the earnings call transcript and extracts the same fields, prioritizing CEO and executive remarks.

Output: `output/<TICKER>/reports/transcript_report.json`

### Red Flag Detector

Compares the two JSON reports and surfaces the top 3–5 most critical inconsistencies across the three discrepancy types.

Output: `output/<TICKER>/reports/red_flag_report.json`

### Fact Checker

Treats each red flag as a **hypothesis** and re-examines the raw 10-K and transcript files. It locates the exact supporting sentence (with line numbers and page markers) or discards the flag if the claim cannot be verified.

Outputs:

- `output/<TICKER>/reports/fact_check_audit_report.md` — audit-ready Markdown with clickable citations
- `output/<TICKER>/reports/fact_check_report.json` — structured verified/discarded results

## Output structure

```
output/
└── UBER/
    ├── UBER_earnings_transcript.txt
    ├── UBER_10-Q_2026-05-06.txt
    ├── UBER_10-K_2026-02-13.txt          # cached by Fact Checker
    └── reports/
        ├── ten_k_report.json
        ├── transcript_report.json
        ├── red_flag_report.json
        ├── fact_check_report.json
        └── fact_check_audit_report.md
```

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `EDGAR_IDENTITY` | Yes | Your name and email for SEC EDGAR requests (e.g. `"Jane Doe jane@example.com"`) |

Copy `.env.example` to `.env`, add your details, and export `EDGAR_IDENTITY` before running the pipeline. No paid API keys are used by this project.

Optional CLI flags are available on each script (`--output-dir`, `--transcript-file`, `--ten-k-file`, etc.). Run any script with `-h` for details.

## Example audit citation

The Fact Checker report links directly back to source text:

```markdown
> research and development $ 3,109 $ 3,402

**Source:** [UBER_10-K_2026-02-13.txt (lines 1818-1818)](../UBER_10-K_2026-02-13.txt#L1818)
```

Each verified finding includes the hypothesis, quoted evidence from both sources, line-level anchors, and a verdict.

## Project structure

```
.
├── assets/                          # Earnings transcript PDFs
├── data-processing/
│   ├── analysis/
│   │   ├── extractor.py             # Structured extraction from raw text
│   │   ├── workers.py               # 10-K and Transcript analyst nodes
│   │   ├── graph.py                 # LangGraph pipeline
│   │   ├── discrepancy_detector.py  # Red Flag cross-reference logic
│   │   ├── fact_checker.py          # Hypothesis verification agent
│   │   └── source_index.py          # Line/page citation indexing
│   ├── fetch_filings.py
│   ├── run_analysis.py
│   ├── run_red_flag_report.py
│   ├── run_fact_check.py
│   └── requirements.txt
└── README.md
```

## Requirements

- Python 3.10+
- Internet access for SEC EDGAR (10-K / 10-Q fetching)
- A local earnings call transcript PDF per ticker

No OpenAI, FMP, or other paid API keys are needed.
