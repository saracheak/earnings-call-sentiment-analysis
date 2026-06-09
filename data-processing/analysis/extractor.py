import re

from analysis.schemas import ExtractedFindings

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
WHITESPACE = re.compile(r"\s+")

GUIDANCE_KEYWORDS = (
    "guidance",
    "outlook",
    "forecast",
    "we expect",
    "looking ahead",
    "forward-looking",
    "anticipate",
)

GUIDANCE_CONTEXT = (
    "revenue",
    "growth",
    "bookings",
    "sales",
    "earnings",
    "profitability",
    "margin",
    "demand",
)

GUIDANCE_EXCLUDE = (
    "accounting guidance",
    "legal guidance",
    "tax guidance",
    "table of contents",
    "exhibit index",
    "signatures",
    "item 1.",
    "item 2.",
    "pages ",
    "forward-looking statements include",
    "statements concerning the following",
)

TRANSCRIPT_EXCLUDE = (
    "factset",
    "callstreet",
    "disclaimer",
    "maximum extent permitted",
    "not be liable",
    "copyright",
    "operator:",
)

SUPPLY_CHAIN_KEYWORDS = (
    "supply chain",
    "logistics disruption",
    "vendor",
    "supplier",
    "procurement",
    "inventory shortage",
    "distribution",
    "shipping",
    "shortage",
    "disruption",
)

RISK_INDICATORS = (
    "risk",
    "may ",
    "could ",
    "adversely",
    "challenge",
    "disruption",
    "depend",
    "fail",
    "uncertain",
    "volatile",
    "shortage",
    "increase the cost",
    "negatively",
)

RD_KEYWORDS = (
    "research and development",
    "r&d",
    "platform r&d",
)

CEO_TITLE_PATTERN = re.compile(
    r"Chief Executive Officer|CEO &|CEO,",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    return WHITESPACE.sub(" ", text).strip()


def _split_sentences(text: str) -> list[str]:
    return [_normalize(s) for s in SENTENCE_SPLIT.split(text) if _normalize(s)]


def _find_sentences(
    text: str,
    keywords: tuple[str, ...],
    *,
    exclude: tuple[str, ...] = (),
    require_any: tuple[str, ...] = (),
    limit: int = 5,
) -> list[str]:
    matches: list[str] = []
    for sentence in _split_sentences(text):
        lowered = sentence.lower()
        if any(keyword in lowered for keyword in keywords):
            if exclude and any(term in lowered for term in exclude):
                continue
            if require_any and not any(term in lowered for term in require_any):
                continue
            matches.append(sentence)
        if len(matches) >= limit:
            break
    return matches


def _extract_section(text: str, start_pattern: str, end_pattern: str) -> str:
    matches = list(
        re.finditer(
            rf"{start_pattern}(.*?){end_pattern}",
            text,
            re.IGNORECASE | re.DOTALL,
        )
    )
    if not matches:
        return text
    best_match = max(
        matches,
        key=lambda match: len(match.group(1) or ""),
    )
    return best_match.group(1) or text


def _extract_rd_spend(text: str) -> tuple[str, list[str]]:
    rd_sentences = _find_sentences(text, RD_KEYWORDS, limit=8)
    dollar_matches = re.findall(
        r"research and development[^\n$]{0,80}\$\s*[\d,]+[^\n.]{0,120}",
        text,
        re.IGNORECASE,
    )
    table_matches = re.findall(
        r"research and development[^\n]{0,40}\b\d{2,4}\b[^\n]{0,40}\b\d{2,4}\b",
        text,
        re.IGNORECASE,
    )

    quotes = rd_sentences[:3]
    if dollar_matches:
        quotes = [_normalize(match) for match in dollar_matches[:2]] + quotes

    summary_parts: list[str] = []
    if dollar_matches:
        summary_parts.append(_normalize(dollar_matches[0]))
    elif table_matches:
        summary_parts.append(
            "Research and development expense figures reported in the filing: "
            + _normalize(table_matches[0])
        )
    elif rd_sentences:
        summary_parts.append(rd_sentences[0])
    else:
        summary_parts.append("No explicit R&D spend disclosure found in the document.")

    return _normalize(" ".join(summary_parts)), quotes[:3]


def _extract_revenue_guidance(text: str) -> tuple[str, list[str]]:
    mda_section = _extract_section(
        text,
        r"Item 7\.?\s*Management['’]s Discussion",
        r"Item 7A|Item 8\.",
    )
    guidance_sentences = _find_sentences(
        mda_section,
        GUIDANCE_KEYWORDS,
        exclude=GUIDANCE_EXCLUDE,
        require_any=GUIDANCE_CONTEXT,
        limit=6,
    )
    if not guidance_sentences:
        guidance_sentences = _find_sentences(
            text,
            GUIDANCE_KEYWORDS,
            exclude=GUIDANCE_EXCLUDE,
            require_any=GUIDANCE_CONTEXT,
            limit=6,
        )
    if not guidance_sentences:
        return (
            "No explicit revenue guidance or outlook language found in the document.",
            [],
        )
    guidance_sentences.sort(key=len)
    return guidance_sentences[0], guidance_sentences[:3]


def _extract_supply_chain_risks(text: str) -> tuple[list[str], list[str]]:
    risk_section = _extract_section(
        text,
        r"Item 1A\.?\s*Risk Factors",
        r"Item 1B|Item 2\.",
    )
    risk_sentences = _find_sentences(
        risk_section,
        SUPPLY_CHAIN_KEYWORDS,
        require_any=RISK_INDICATORS,
        limit=5,
    )
    if not risk_sentences:
        risk_sentences = _find_sentences(
            risk_section,
            ("supply chain", "supplier", "vendor", "logistics"),
            require_any=RISK_INDICATORS,
            limit=5,
        )

    if not risk_sentences:
        return (
            ["No explicit supply chain risk language found in the document."],
            [],
        )
    return risk_sentences, risk_sentences[:3]


def extract_ten_k_findings(text: str) -> ExtractedFindings:
    revenue_guidance, guidance_quotes = _extract_revenue_guidance(text)
    supply_chain_risks, supply_quotes = _extract_supply_chain_risks(text)
    rd_spend, rd_quotes = _extract_rd_spend(text)

    supporting_quotes = []
    for quote in guidance_quotes + supply_quotes + rd_quotes:
        if quote not in supporting_quotes:
            supporting_quotes.append(quote)

    return ExtractedFindings(
        revenue_guidance=revenue_guidance,
        supply_chain_risks=supply_chain_risks,
        rd_spend=rd_spend,
        supporting_quotes=supporting_quotes[:5],
    )


def _extract_ceo_remarks(transcript: str) -> str:
    blocks = re.split(r"\.{10,}", transcript)
    ceo_remarks: list[str] = []

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            continue

        title_line = lines[1] if len(lines) > 1 else ""
        if not CEO_TITLE_PATTERN.search(title_line):
            continue

        remarks = _normalize(" ".join(lines[2:]))
        if remarks:
            ceo_remarks.append(remarks)

    return " ".join(ceo_remarks)


def _extract_transcript_revenue_guidance(text: str) -> tuple[str, list[str]]:
    guidance_sentences = _find_sentences(
        text,
        GUIDANCE_KEYWORDS,
        exclude=GUIDANCE_EXCLUDE + TRANSCRIPT_EXCLUDE,
        require_any=GUIDANCE_CONTEXT,
        limit=6,
    )
    if not guidance_sentences:
        return (
            "No explicit revenue guidance or outlook language found in the document.",
            [],
        )
    guidance_sentences.sort(key=len)
    return guidance_sentences[0], guidance_sentences[:3]


def _extract_transcript_supply_chain_risks(text: str) -> tuple[list[str], list[str]]:
    risk_sentences = _find_sentences(
        text,
        ("supply chain", "supplier", "vendor", "logistics", "inventory", "shortage"),
        exclude=TRANSCRIPT_EXCLUDE,
        require_any=RISK_INDICATORS,
        limit=5,
    )
    if not risk_sentences:
        return (
            ["No explicit supply chain risk language found in the document."],
            [],
        )
    return risk_sentences, risk_sentences[:3]


def extract_transcript_findings(transcript: str) -> ExtractedFindings:
    ceo_text = _extract_ceo_remarks(transcript) or transcript

    revenue_guidance, guidance_quotes = _extract_transcript_revenue_guidance(ceo_text)
    supply_chain_risks, supply_quotes = _extract_transcript_supply_chain_risks(ceo_text)
    rd_spend, rd_quotes = _extract_rd_spend(ceo_text)

    if revenue_guidance.startswith("No explicit"):
        revenue_guidance, guidance_quotes = _extract_transcript_revenue_guidance(transcript)
    if supply_chain_risks[0].startswith("No explicit"):
        supply_chain_risks, supply_quotes = _extract_transcript_supply_chain_risks(
            transcript
        )
    if rd_spend.startswith("No explicit"):
        rd_spend, rd_quotes = _extract_rd_spend(transcript)

    supporting_quotes = []
    for quote in guidance_quotes + supply_quotes + rd_quotes:
        if quote not in supporting_quotes:
            supporting_quotes.append(quote)

    return ExtractedFindings(
        revenue_guidance=revenue_guidance,
        supply_chain_risks=supply_chain_risks,
        rd_spend=rd_spend,
        supporting_quotes=supporting_quotes[:5],
    )
