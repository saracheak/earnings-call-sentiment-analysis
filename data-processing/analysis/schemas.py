from pydantic import BaseModel, Field


class ExtractedFindings(BaseModel):
    """Fields extracted by an analyst worker via structured output."""

    revenue_guidance: str = Field(
        description=(
            "Revenue guidance, outlook, or forward-looking revenue commentary. "
            "Include specific figures or ranges when available."
        )
    )
    supply_chain_risks: list[str] = Field(
        description=(
            "Supply chain risks mentioned in the document. "
            "Each item should be a concise risk statement."
        )
    )
    rd_spend: str = Field(
        description=(
            "R&D spending figures, trends, or related commentary. "
            "Include dollar amounts and year-over-year changes when available."
        )
    )
    supporting_quotes: list[str] = Field(
        default_factory=list,
        description="Direct quotes from the source document supporting the extracted data points.",
    )


class AnalystFindings(ExtractedFindings):
    """Final analyst report including worker metadata."""

    analyst: str = Field(description="Name of the analyst agent that produced this report.")
    source_document: str = Field(description="Label for the source document that was analyzed.")
