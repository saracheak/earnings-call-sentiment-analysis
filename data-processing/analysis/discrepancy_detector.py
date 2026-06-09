import re
from dataclasses import dataclass

from analysis.discrepancy_schemas import (
    DiscrepancyInput,
    DiscrepancyType,
    RedFlag,
    RedFlagReport,
)
from analysis.schemas import AnalystFindings

NOT_FOUND_PREFIX = "no explicit"
MONEY_PATTERN = re.compile(
    r"\$\s*([\d,]+(?:\.\d+)?)\s*(million|billion|m|b)?",
    re.IGNORECASE,
)
PERCENT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*%")
TOPIC_KEYWORDS = {
    "geopolitical": ("geopolitical", "war", "conflict", "sanction", "tariff", "ukraine", "middle east"),
    "supply chain": ("supply chain", "logistics", "vendor", "supplier", "shipping", "shortage"),
    "cybersecurity": ("security", "breach", "cyber", "privacy", "unauthorized access"),
    "regulatory": ("regulation", "regulatory", "litigation", "legal", "compliance"),
    "macroeconomic": ("inflation", "recession", "interest rate", "fuel price", "macroeconomic"),
    "technology": ("technology", "infrastructure", "platform", "software", "system disruption"),
    "leadership": ("leadership", "management change", "turnover", "executive"),
    "competition": ("compet", "market share", "pricing pressure"),
    "rd investment": ("research and development", "r&d", "platform r&d"),
}

CAUTION_WORDS = (
    "uncertain",
    "uncertainty",
    "may ",
    "could ",
    "might ",
    "adversely",
    "risk",
    "volatile",
    "challenge",
    "headwind",
    "caution",
    "decline",
    "loss",
    "fail",
    "disruption",
    "negative",
    "pressure",
    "fluctuat",
)

CONFIDENCE_WORDS = (
    "confident",
    "confidence",
    "strong",
    "exceptional",
    "momentum",
    "accelerat",
    "robust",
    "optimistic",
    "outperform",
    "record",
    " durable ",
    " profitable growth",
    "high end of our guidance",
    "continued momentum",
)


@dataclass
class ParsedAmount:
    value: float
    unit: str
    raw: str


def _is_missing(text: str) -> bool:
    return text.strip().lower().startswith(NOT_FOUND_PREFIX)


def _collect_text(report: AnalystFindings) -> str:
    parts = [
        report.revenue_guidance,
        report.rd_spend,
        *report.supply_chain_risks,
        *report.supporting_quotes,
    ]
    return " ".join(parts).lower()


def _parse_money(text: str) -> list[ParsedAmount]:
    amounts: list[ParsedAmount] = []
    for match in MONEY_PATTERN.finditer(text):
        raw_number = match.group(1).replace(",", "")
        value = float(raw_number)
        unit = (match.group(2) or "dollars").lower()
        if unit in {"m", "million"}:
            value *= 1_000_000
            unit = "dollars"
        elif unit in {"b", "billion"}:
            value *= 1_000_000_000
            unit = "dollars"
        amounts.append(ParsedAmount(value=value, unit=unit, raw=match.group(0)))
    return amounts


def _parse_percentages(text: str) -> list[float]:
    return [float(match.group(1)) for match in PERCENT_PATTERN.finditer(text)]


def _sentiment_score(text: str) -> float:
    lowered = text.lower()
    caution = sum(1 for word in CAUTION_WORDS if word in lowered)
    confidence = sum(1 for word in CONFIDENCE_WORDS if word in lowered)
    return confidence - caution


def _topic_hits(text: str) -> set[str]:
    lowered = text.lower()
    return {
        topic
        for topic, keywords in TOPIC_KEYWORDS.items()
        if any(keyword in lowered for keyword in keywords)
    }


def _risk_topics(risks: list[str]) -> set[str]:
    topics: set[str] = set()
    for risk in risks:
        if _is_missing(risk):
            continue
        topics.update(_topic_hits(risk))
    return topics


def _severity_for_numerical(relative_delta: float) -> int:
    if relative_delta >= 0.25:
        return 10
    if relative_delta >= 0.15:
        return 8
    if relative_delta >= 0.05:
        return 7
    return 6


def _detect_numerical_discrepancies(
    ten_k: AnalystFindings,
    transcript: AnalystFindings,
) -> list[RedFlag]:
    flags: list[RedFlag] = []

    ten_k_money = _parse_money(ten_k.rd_spend)
    transcript_money = _parse_money(transcript.rd_spend)

    if ten_k_money and not transcript_money:
        flags.append(
            RedFlag(
                discrepancy_type=DiscrepancyType.NUMERICAL,
                severity=8,
                title="R&D figures disclosed in filing but absent on earnings call",
                description=(
                    "The 10-K reports specific R&D dollar amounts, but the earnings call "
                    "transcript does not provide comparable figures."
                ),
                topic="rd_spend",
                ten_k_evidence=ten_k.rd_spend,
                transcript_evidence=transcript.rd_spend,
            )
        )
    elif ten_k_money and transcript_money:
        ten_k_value = ten_k_money[0].value
        transcript_value = transcript_money[0].value
        if ten_k_value > 0:
            delta = abs(ten_k_value - transcript_value) / ten_k_value
            if delta >= 0.05:
                flags.append(
                    RedFlag(
                        discrepancy_type=DiscrepancyType.NUMERICAL,
                        severity=_severity_for_numerical(delta),
                        title="R&D spend mismatch between filing and earnings call",
                        description=(
                            f"The filing and call cite different R&D figures "
                            f"({ten_k_money[0].raw} vs {transcript_money[0].raw})."
                        ),
                        topic="rd_spend",
                        ten_k_evidence=ten_k.rd_spend,
                        transcript_evidence=transcript.rd_spend,
                    )
                )

    ten_k_percents = _parse_percentages(
        " ".join([ten_k.revenue_guidance, ten_k.rd_spend, *ten_k.supporting_quotes])
    )
    transcript_percents = _parse_percentages(
        " ".join(
            [
                transcript.revenue_guidance,
                transcript.rd_spend,
                *transcript.supporting_quotes,
            ]
        )
    )
    if ten_k_percents and transcript_percents:
        ten_k_pct = ten_k_percents[0]
        transcript_pct = transcript_percents[0]
        if ten_k_pct > 0:
            delta = abs(ten_k_pct - transcript_pct) / ten_k_pct
            if delta >= 0.20:
                flags.append(
                    RedFlag(
                        discrepancy_type=DiscrepancyType.NUMERICAL,
                        severity=_severity_for_numerical(delta),
                        title="Percentage metric mismatch between filing and call",
                        description=(
                            f"The filing references {ten_k_pct}% while the call references "
                            f"{transcript_pct}% on a comparable metric."
                        ),
                        topic="revenue_guidance",
                        ten_k_evidence=ten_k.revenue_guidance,
                        transcript_evidence=transcript.revenue_guidance,
                    )
                )

    return flags


def _detect_omission_discrepancies(
    ten_k: AnalystFindings,
    transcript: AnalystFindings,
) -> list[RedFlag]:
    flags: list[RedFlag] = []
    ten_k_topics = _risk_topics(ten_k.supply_chain_risks)
    transcript_topics = _topic_hits(_collect_text(transcript))

    missing_on_call = sorted(ten_k_topics - transcript_topics)
    for topic in missing_on_call[:3]:
        matching_risks = [
            risk
            for risk in ten_k.supply_chain_risks
            if topic in _topic_hits(risk) and not _is_missing(risk)
        ]
        if not matching_risks:
            continue
        best_risk = max(matching_risks, key=lambda risk: len(_topic_hits(risk)))
        severity = 9 if topic in {"geopolitical", "supply chain", "regulatory"} else 7
        flags.append(
            RedFlag(
                discrepancy_type=DiscrepancyType.OMISSION,
                severity=severity,
                title=f"{topic.title()} risk disclosed in 10-K but not addressed on call",
                description=(
                    f"The filing highlights {topic}-related risk language, but the earnings "
                    "call analysis found no comparable discussion from management."
                ),
                topic="supply_chain_risks",
                ten_k_evidence=best_risk,
                transcript_evidence=transcript.revenue_guidance,
            )
        )

    if _is_missing(transcript.rd_spend) and not _is_missing(ten_k.rd_spend):
        flags.append(
            RedFlag(
                discrepancy_type=DiscrepancyType.OMISSION,
                severity=8,
                title="R&D spend discussed in filing but omitted on earnings call",
                description=(
                    "The 10-K includes R&D spending disclosure that management did not "
                    "revisit during the earnings call."
                ),
                topic="rd_spend",
                ten_k_evidence=ten_k.rd_spend,
                transcript_evidence=transcript.rd_spend,
            )
        )

    if _is_missing(transcript.supply_chain_risks[0]) and any(
        not _is_missing(risk) for risk in ten_k.supply_chain_risks
    ):
        flags.append(
            RedFlag(
                discrepancy_type=DiscrepancyType.OMISSION,
                severity=9,
                title="Operational risks in filing not discussed on earnings call",
                description=(
                    "The 10-K lists multiple operational and supply-chain-related risks, "
                    "but the transcript contains no explicit risk discussion from the CEO."
                ),
                topic="supply_chain_risks",
                ten_k_evidence=ten_k.supply_chain_risks[0],
                transcript_evidence=transcript.supply_chain_risks[0],
            )
        )

    for risk in ten_k.supply_chain_risks:
        if _is_missing(risk):
            continue
        key_terms = [
            term
            for term in re.findall(r"[A-Za-z]{5,}", risk.lower())
            if term
            not in {
                "their",
                "would",
                "could",
                "which",
                "these",
                "those",
                "about",
                "other",
                "business",
                "platform",
                "result",
            }
        ]
        if not key_terms:
            continue
        if any(term in _collect_text(transcript) for term in key_terms[:5]):
            continue
        topic = next(iter(_topic_hits(risk)), "risk")
        if topic in missing_on_call:
            continue
        flags.append(
            RedFlag(
                discrepancy_type=DiscrepancyType.OMISSION,
                severity=6,
                title=f"Filing risk statement on {topic} not echoed on call",
                description=(
                    "A specific risk statement from the filing does not appear to be "
                    "discussed in management remarks on the earnings call."
                ),
                topic="supply_chain_risks",
                ten_k_evidence=risk[:300],
                transcript_evidence=transcript.revenue_guidance[:300],
            )
        )
        break

    return flags


def _detect_sentiment_discrepancies(
    ten_k: AnalystFindings,
    transcript: AnalystFindings,
) -> list[RedFlag]:
    flags: list[RedFlag] = []
    comparisons = (
        ("revenue_guidance", ten_k.revenue_guidance, transcript.revenue_guidance),
        ("rd_spend", ten_k.rd_spend, transcript.rd_spend),
    )

    for topic, ten_k_text, transcript_text in comparisons:
        if _is_missing(ten_k_text) or _is_missing(transcript_text):
            continue

        ten_k_score = _sentiment_score(ten_k_text)
        transcript_score = _sentiment_score(transcript_text)
        gap = transcript_score - ten_k_score

        if gap >= 3:
            flags.append(
                RedFlag(
                    discrepancy_type=DiscrepancyType.SENTIMENT_SHIFT,
                    severity=min(10, 6 + gap),
                    title=f"Optimistic call tone on {topic.replace('_', ' ')} vs cautious filing language",
                    description=(
                        "Management language on the earnings call is materially more confident "
                        "than the corresponding disclosure tone in the 10-K."
                    ),
                    topic=topic,
                    ten_k_evidence=ten_k_text,
                    transcript_evidence=transcript_text,
                )
            )
        elif gap <= -3:
            flags.append(
                RedFlag(
                    discrepancy_type=DiscrepancyType.SENTIMENT_SHIFT,
                    severity=min(10, 6 + abs(gap)),
                    title=f"Cautious call tone on {topic.replace('_', ' ')} vs filing language",
                    description=(
                        "Management sounded more cautious on the earnings call than the "
                        "corresponding disclosure language in the 10-K."
                    ),
                    topic=topic,
                    ten_k_evidence=ten_k_text,
                    transcript_evidence=transcript_text,
                )
            )

    ten_k_risk_tone = _sentiment_score(" ".join(ten_k.supply_chain_risks))
    transcript_tone = _sentiment_score(
        " ".join([transcript.revenue_guidance, *transcript.supporting_quotes])
    )
    tone_gap = transcript_tone - ten_k_risk_tone
    if tone_gap >= 4:
        flags.append(
            RedFlag(
                discrepancy_type=DiscrepancyType.SENTIMENT_SHIFT,
                severity=9,
                title="Confident CEO messaging despite extensive filing risk disclosures",
                description=(
                    "The 10-K emphasizes multiple risks using cautious language, while CEO "
                    "remarks on the call emphasize momentum and confidence without comparable "
                    "risk framing."
                ),
                topic="supply_chain_risks",
                ten_k_evidence=ten_k.supply_chain_risks[0],
                transcript_evidence=transcript.revenue_guidance,
            )
        )

    return flags


def _dedupe_flags(flags: list[RedFlag]) -> list[RedFlag]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[RedFlag] = []
    for flag in flags:
        key = (flag.discrepancy_type.value, flag.title, flag.topic)
        if key in seen:
            continue
        seen.add(key)
        unique.append(flag)
    return unique


def generate_red_flag_report(
    payload: DiscrepancyInput,
    *,
    max_flags: int = 5,
) -> RedFlagReport:
    ten_k = payload.ten_k_report
    transcript = payload.transcript_report

    flags = _dedupe_flags(
        _detect_numerical_discrepancies(ten_k, transcript)
        + _detect_omission_discrepancies(ten_k, transcript)
        + _detect_sentiment_discrepancies(ten_k, transcript)
    )
    flags.sort(key=lambda flag: flag.severity, reverse=True)
    top_flags = flags[:max_flags]

    if not top_flags:
        summary = (
            f"No major cross-source inconsistencies were detected for {payload.ticker} "
            "across numerical, omission, and sentiment checks."
        )
    else:
        categories = ", ".join(sorted({flag.discrepancy_type.value for flag in top_flags}))
        summary = (
            f"Identified {len(top_flags)} critical red flags for {payload.ticker} "
            f"spanning {categories} discrepancies between the 10-K and earnings call."
        )

    return RedFlagReport(
        ticker=payload.ticker.upper(),
        ten_k_source=ten_k.source_document,
        transcript_source=transcript.source_document,
        red_flags=top_flags,
        summary=summary,
    )
