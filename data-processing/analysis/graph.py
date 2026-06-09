import json
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from analysis.workers import AnalysisState, ten_k_analyst_node, transcript_analyst_node


def build_analysis_graph():
    graph = StateGraph(AnalysisState)
    graph.add_node("ten_k_analyst", ten_k_analyst_node)
    graph.add_node("transcript_analyst", transcript_analyst_node)
    graph.add_edge(START, "ten_k_analyst")
    graph.add_edge(START, "transcript_analyst")
    graph.add_edge("ten_k_analyst", END)
    graph.add_edge("transcript_analyst", END)
    return graph.compile()


def run_analysis(
    *,
    ticker: str,
    ten_k_text: str,
    transcript_text: str,
) -> dict:
    graph = build_analysis_graph()
    return graph.invoke(
        {
            "ticker": ticker.upper(),
            "ten_k_text": ten_k_text,
            "transcript_text": transcript_text,
            "ten_k_report": None,
            "transcript_report": None,
        }
    )


def save_reports(result: dict, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    ten_k_path = output_dir / "ten_k_report.json"
    transcript_path = output_dir / "transcript_report.json"

    ten_k_path.write_text(
        json.dumps(result["ten_k_report"], indent=2),
        encoding="utf-8",
    )
    transcript_path.write_text(
        json.dumps(result["transcript_report"], indent=2),
        encoding="utf-8",
    )

    return ten_k_path, transcript_path
