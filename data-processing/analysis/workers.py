from typing import TypedDict

from analysis.extractor import extract_ten_k_findings, extract_transcript_findings
from analysis.schemas import AnalystFindings

TEN_K_ANALYST = "10-K Analyst"
TRANSCRIPT_ANALYST = "Transcript Analyst"


class AnalysisState(TypedDict):
    ticker: str
    ten_k_text: str
    transcript_text: str
    ten_k_report: dict | None
    transcript_report: dict | None


def ten_k_analyst_node(state: AnalysisState) -> dict:
    extracted = extract_ten_k_findings(state["ten_k_text"])
    findings = AnalystFindings(
        **extracted.model_dump(),
        analyst=TEN_K_ANALYST,
        source_document=f"{state['ticker']} Form 10-K",
    )
    return {"ten_k_report": findings.model_dump()}


def transcript_analyst_node(state: AnalysisState) -> dict:
    extracted = extract_transcript_findings(state["transcript_text"])
    findings = AnalystFindings(
        **extracted.model_dump(),
        analyst=TRANSCRIPT_ANALYST,
        source_document=f"{state['ticker']} earnings call transcript",
    )
    return {"transcript_report": findings.model_dump()}
