from enum import Enum

from pydantic import BaseModel, Field

from analysis.schemas import AnalystFindings


class DiscrepancyType(str, Enum):
    NUMERICAL = "numerical"
    OMISSION = "omission"
    SENTIMENT_SHIFT = "sentiment_shift"


class RedFlag(BaseModel):
    discrepancy_type: DiscrepancyType
    severity: int = Field(ge=1, le=10, description="Criticality score from 1 (low) to 10 (high).")
    title: str
    description: str
    topic: str
    ten_k_evidence: str
    transcript_evidence: str


class RedFlagReport(BaseModel):
    ticker: str
    ten_k_source: str
    transcript_source: str
    red_flags: list[RedFlag] = Field(description="Top 3-5 most critical inconsistencies.")
    summary: str


class DiscrepancyInput(BaseModel):
    ticker: str
    ten_k_report: AnalystFindings
    transcript_report: AnalystFindings
