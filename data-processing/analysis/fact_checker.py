import re
from pathlib import Path

from analysis.discrepancy_schemas import DiscrepancyType, RedFlag, RedFlagReport
from analysis.fact_checker_schemas import (
    DiscardedRedFlag,
    FactCheckReport,
    SourceCitation,
    VerifiedRedFlag,
)
from analysis.source_index import DocumentIndex, SourceMatch

NOT_FOUND_PREFIX = "no explicit"


def _is_missing(text: str) -> bool:
    return text.strip().lower().startswith(NOT_FOUND_PREFIX)


def _phrases_from_text(text: str) -> list[str]:
    words = [word for word in re.findall(r"[A-Za-z0-9$%]+", text.lower()) if len(word) > 2]
    phrases: list[str] = []
    for size in (5, 4, 3):
        for index in range(0, max(len(words) - size + 1, 0)):
            phrase = " ".join(words[index : index + size])
            if len(phrase) >= 15:
                phrases.append(phrase)
    return phrases


def _to_citation(
    *,
    document: str,
    file_path: Path,
    match: SourceMatch,
) -> SourceCitation:
    return SourceCitation(
        document=document,
        file_path=str(file_path),
        line_start=match.line_start,
        line_end=match.line_end,
        page=match.page,
        quote=match.quote,
        anchor=f"{file_path.name}#{match.anchor}",
    )


def _verify_ten_k_support(
    flag: RedFlag,
    ten_k_index: DocumentIndex,
    ten_k_path: Path,
) -> tuple[SourceCitation | None, str | None]:
    match = ten_k_index.find_quote(flag.ten_k_evidence)
    if match:
        return _to_citation(document="10-K", file_path=ten_k_path, match=match), None

    if flag.topic == "rd_spend":
        numbers = re.findall(r"\d[\d,]{2,}", flag.ten_k_evidence)
        if numbers and ten_k_index.contains_phrases([f"research and development {numbers[0]}"]):
            fallback = ten_k_index.find_quote(f"Research and development {numbers[0]}")
            if fallback:
                return _to_citation(document="10-K", file_path=ten_k_path, match=fallback), None

    return None, "Could not locate the cited 10-K passage in the raw filing text."


def _verify_transcript_support(
    flag: RedFlag,
    transcript_index: DocumentIndex,
    transcript_path: Path,
    *,
    require_absence: bool = False,
    search_scope: DocumentIndex | None = None,
) -> tuple[SourceCitation | None, str | None]:
    scope = search_scope or transcript_index

    if require_absence:
        phrases = _phrases_from_text(flag.ten_k_evidence)
        if scope.contains_phrases(phrases[:6]):
            return None, "Expected omission was not confirmed; related language appears in the transcript."

        if flag.topic == "rd_spend":
            numbers = re.findall(r"\d[\d,]{2,}", flag.ten_k_evidence)
            rd_phrases = [phrase for phrase in phrases if "research" in phrase or "development" in phrase]
            if numbers and scope.contains_phrases([f"research and development {numbers[0]}"] + rd_phrases[:3]):
                return None, "R&D figures appear in the transcript, so the omission claim is not supported."

        return None, None

    if _is_missing(flag.transcript_evidence):
        return None, "Transcript evidence was a placeholder and could not be verified in raw text."

    match = transcript_index.find_quote(flag.transcript_evidence)
    if not match:
        return None, "Could not locate the cited transcript passage in the raw call text."

    return _to_citation(document="Transcript", file_path=transcript_path, match=match), None


def _verify_red_flag(
    flag: RedFlag,
    ten_k_index: DocumentIndex,
    transcript_index: DocumentIndex,
    ceo_index: DocumentIndex,
    ten_k_path: Path,
    transcript_path: Path,
) -> tuple[VerifiedRedFlag | None, DiscardedRedFlag]:
    ten_k_citation, ten_k_error = _verify_ten_k_support(flag, ten_k_index, ten_k_path)
    if ten_k_error:
        return None, DiscardedRedFlag(red_flag=flag, reason=ten_k_error)

    if flag.discrepancy_type == DiscrepancyType.NUMERICAL:
        _, transcript_error = _verify_transcript_support(
            flag,
            transcript_index,
            transcript_path,
            require_absence=True,
            search_scope=ceo_index,
        )
        if transcript_error:
            return None, DiscardedRedFlag(red_flag=flag, reason=transcript_error)

        notes = (
            "Verified R&D figures in the raw 10-K and confirmed comparable figures "
            "are absent from CEO remarks on the earnings call."
        )
        return (
            VerifiedRedFlag(
                red_flag=flag,
                ten_k_citation=ten_k_citation,
                transcript_citation=None,
                verification_notes=notes,
            ),
            None,
        )

    if flag.discrepancy_type == DiscrepancyType.OMISSION:
        _, omission_error = _verify_transcript_support(
            flag,
            transcript_index,
            transcript_path,
            require_absence=True,
            search_scope=ceo_index,
        )
        if omission_error:
            return None, DiscardedRedFlag(red_flag=flag, reason=omission_error)

        notes = (
            "Verified the risk or disclosure in the raw 10-K and confirmed the topic "
            "is not discussed in CEO remarks on the earnings call."
        )
        return (
            VerifiedRedFlag(
                red_flag=flag,
                ten_k_citation=ten_k_citation,
                transcript_citation=None,
                verification_notes=notes,
            ),
            None,
        )

    transcript_citation, transcript_error = _verify_transcript_support(
        flag,
        transcript_index,
        transcript_path,
    )
    if transcript_error:
        return None, DiscardedRedFlag(red_flag=flag, reason=transcript_error)

    notes = (
        "Verified both the cautious filing language and the contrasting management "
        "tone directly in the raw source documents."
    )
    return (
        VerifiedRedFlag(
            red_flag=flag,
            ten_k_citation=ten_k_citation,
            transcript_citation=transcript_citation,
            verification_notes=notes,
        ),
        None,
    )


def run_fact_checker(
    *,
    red_flag_report: RedFlagReport,
    ten_k_text: str,
    transcript_text: str,
    ten_k_path: Path,
    transcript_path: Path,
) -> FactCheckReport:
    ten_k_index = DocumentIndex(ten_k_text)
    transcript_index = DocumentIndex(transcript_text, page_markers=True)
    ceo_index = transcript_index.extract_ceo_section()

    verified: list[VerifiedRedFlag] = []
    discarded: list[DiscardedRedFlag] = []

    for flag in red_flag_report.red_flags:
        result, rejected = _verify_red_flag(
            flag,
            ten_k_index,
            transcript_index,
            ceo_index,
            ten_k_path,
            transcript_path,
        )
        if result:
            verified.append(result)
        elif rejected:
            discarded.append(rejected)

    if verified:
        summary = (
            f"Fact Checker verified {len(verified)} of {len(red_flag_report.red_flags)} "
            f"red flags for {red_flag_report.ticker}; discarded {len(discarded)} unverified hypotheses."
        )
    else:
        summary = (
            f"Fact Checker could not verify any red flags for {red_flag_report.ticker}; "
            f"discarded {len(discarded)} hypotheses."
        )

    return FactCheckReport(
        ticker=red_flag_report.ticker,
        verified_flags=verified,
        discarded_flags=discarded,
        ten_k_source_file=str(ten_k_path),
        transcript_source_file=str(transcript_path),
        summary=summary,
    )
