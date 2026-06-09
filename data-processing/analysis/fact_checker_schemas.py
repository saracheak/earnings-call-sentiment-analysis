from pydantic import BaseModel, Field

from analysis.discrepancy_schemas import DiscrepancyType, RedFlag


class SourceCitation(BaseModel):
    document: str
    file_path: str
    line_start: int
    line_end: int
    page: str | None = None
    quote: str
    anchor: str


class VerifiedRedFlag(BaseModel):
    red_flag: RedFlag
    ten_k_citation: SourceCitation
    transcript_citation: SourceCitation | None = None
    verification_notes: str


class DiscardedRedFlag(BaseModel):
    red_flag: RedFlag
    reason: str


class FactCheckReport(BaseModel):
    ticker: str
    verified_flags: list[VerifiedRedFlag] = Field(default_factory=list)
    discarded_flags: list[DiscardedRedFlag] = Field(default_factory=list)
    ten_k_source_file: str
    transcript_source_file: str
    summary: str
