import os
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from analysis.schemas import AnalystFindings, ExtractedFindings

MAX_DOCUMENT_CHARS = 120_000
TEN_K_ANALYST = "10-K Analyst"
TRANSCRIPT_ANALYST = "Transcript Analyst"


class AnalysisState(TypedDict):
    ticker: str
    ten_k_text: str
    transcript_text: str
    ten_k_report: dict | None
    transcript_report: dict | None


def _truncate(text: str, limit: int = MAX_DOCUMENT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n[Document truncated for analysis.]"


def _build_llm() -> ChatOpenAI:
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    return ChatOpenAI(model=model, temperature=0)


def _extract_findings(
    *,
    analyst_name: str,
    source_label: str,
    system_prompt: str,
    document_text: str,
) -> AnalystFindings:
    structured_llm = _build_llm().with_structured_output(ExtractedFindings)

    extracted = structured_llm.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=(
                    f"Ticker: {source_label}\n\n"
                    f"Analyze the following {source_label} and extract the required fields.\n\n"
                    f"{_truncate(document_text)}"
                )
            ),
        ]
    )

    return AnalystFindings(
        **extracted.model_dump(),
        analyst=analyst_name,
        source_document=source_label,
    )


def ten_k_analyst_node(state: AnalysisState) -> dict:
    findings = _extract_findings(
        analyst_name=TEN_K_ANALYST,
        source_label=f"{state['ticker']} Form 10-K",
        system_prompt=(
            "You are the 10-K Analyst. Extract structured findings from SEC Form 10-K filings. "
            "Focus on MD&A, risk factors, and financial statement footnotes. "
            "Return concrete revenue guidance, supply chain risks, and R&D spend details. "
            "Use supporting_quotes with verbatim excerpts from the filing."
        ),
        document_text=state["ten_k_text"],
    )
    return {"ten_k_report": findings.model_dump()}


def transcript_analyst_node(state: AnalysisState) -> dict:
    findings = _extract_findings(
        analyst_name=TRANSCRIPT_ANALYST,
        source_label=f"{state['ticker']} earnings call transcript",
        system_prompt=(
            "You are the Transcript Analyst. Extract structured findings from earnings call transcripts. "
            "Prioritize statements from the CEO and other executive speakers in the management discussion. "
            "Return revenue guidance, supply chain risks, and R&D spend as communicated on the call. "
            "Use supporting_quotes with verbatim CEO or executive remarks."
        ),
        document_text=state["transcript_text"],
    )
    return {"transcript_report": findings.model_dump()}
