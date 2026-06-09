from pathlib import Path

from analysis.fact_checker_schemas import FactCheckReport, SourceCitation, VerifiedRedFlag


def _format_citation(citation: SourceCitation, reports_dir: Path) -> str:
    source_path = Path(citation.file_path).resolve()
    try:
        relative_path = source_path.relative_to(reports_dir.parent.resolve())
    except ValueError:
        relative_path = Path(source_path.name)

    location_parts = [f"lines {citation.line_start}-{citation.line_end}"]
    if citation.page:
        location_parts.append(f"page {citation.page}")

    location = ", ".join(location_parts)
    anchor = citation.anchor.split("#", 1)[-1]
    link = f"../{relative_path.as_posix()}#{anchor}"
    return f"[{source_path.name} ({location})]({link})"


def render_audit_markdown(report: FactCheckReport, *, output_dir: Path) -> str:
    lines = [
        f"# Fact-Checked Red Flag Audit Report: {report.ticker}",
        "",
        report.summary,
        "",
        "## Source Documents",
        "",
        f"- **10-K:** `{report.ten_k_source_file}`",
        f"- **Transcript:** `{report.transcript_source_file}`",
        "",
    ]

    if report.verified_flags:
        lines.extend(["## Verified Findings", ""])
        for index, finding in enumerate(report.verified_flags, start=1):
            lines.extend(_render_verified_finding(index, finding, output_dir))
    else:
        lines.extend(["## Verified Findings", "", "_No red flags passed fact checking._", ""])

    lines.extend(["## Discarded Hypotheses", ""])
    if report.discarded_flags:
        for index, discarded in enumerate(report.discarded_flags, start=1):
            flag = discarded.red_flag
            lines.extend(
                [
                    f"### Discarded {index}: {flag.title}",
                    "",
                    f"- **Reason:** {discarded.reason}",
                    f"- **Original type:** `{flag.discrepancy_type.value}`",
                    f"- **Original severity:** {flag.severity}",
                    "",
                ]
            )
    else:
        lines.append("_No hypotheses were discarded._")
        lines.append("")

    lines.extend(
        [
            "## Audit Notes",
            "",
            "Each verified finding links back to the raw source text using file anchors ",
            "(`#L123` or `#L123-L130`) so a human analyst can inspect the original passage directly.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_verified_finding(
    index: int,
    finding: VerifiedRedFlag,
    output_dir: Path,
) -> list[str]:
    flag = finding.red_flag
    lines = [
        f"### Finding {index}: {flag.title}",
        "",
        f"- **Type:** `{flag.discrepancy_type.value}`",
        f"- **Severity:** {flag.severity}",
        f"- **Topic:** `{flag.topic}`",
        "",
        "#### Hypothesis",
        "",
        flag.description,
        "",
        "#### 10-K Evidence",
        "",
        f"> {finding.ten_k_citation.quote}",
        "",
        f"**Source:** {_format_citation(finding.ten_k_citation, output_dir)}",
        "",
    ]

    if finding.transcript_citation:
        lines.extend(
            [
                "#### Transcript Evidence",
                "",
                f"> {finding.transcript_citation.quote}",
                "",
                f"**Source:** {_format_citation(finding.transcript_citation, output_dir)}",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "#### Transcript Evidence",
                "",
                "_No matching management remark was found in CEO remarks for this topic, supporting the discrepancy claim._",
                "",
            ]
        )

    lines.extend(
        [
            "#### Fact Checker Verdict",
            "",
            finding.verification_notes,
            "",
        ]
    )
    return lines
