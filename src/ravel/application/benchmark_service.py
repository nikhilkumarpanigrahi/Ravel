"""BenchmarkService: Executes the 20-case benchmark, writes answer files, and compiles metrics."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine

from ravel.application.answer_validator import validate_answer
from ravel.application.policy_engine import PolicyEngine
from ravel.application.workflow import AgentWorkflow
from ravel.config import Settings
from ravel.domain.case import AnswerFile
from ravel.infrastructure.graph.base import GraphAdapter
from ravel.infrastructure.persistence import InvestigationRepository

logger = logging.getLogger("ravel.benchmark")


class BenchmarkService:
    """Orchestrates end-to-end benchmark execution on HHGOA_IEEE case pack."""

    def __init__(self, settings: Settings, graph: GraphAdapter | None = None):
        self.settings = settings
        from ravel.infrastructure.graph import create_graph_adapter

        self.graph = graph or create_graph_adapter(settings)

        # Persistence repo
        engine = create_engine(settings.state_db_url)
        self.repo = InvestigationRepository(engine)
        self.policy_engine = PolicyEngine()
        from ravel.infrastructure.llm import build_llm

        self.llm = build_llm(settings)
        self.workflow = AgentWorkflow(
            graph=self.graph,
            repo=self.repo,
            policy_engine=self.policy_engine,
            simulate_customer=settings.simulate_customer_response,
            llm=self.llm,
        )

    def run_all(
        self,
        limit: int = 0,
        output_dir: str = "",
        replay: bool = False,
    ) -> dict[str, Any]:
        """Run all cases from case_pack.csv and output graded answer files."""
        out_path = Path(output_dir) if output_dir else self.settings.output_dir
        out_path.mkdir(parents=True, exist_ok=True)

        case_pack_file = self.settings.data_dir / "case_pack.csv"
        if not case_pack_file.exists():
            raise FileNotFoundError(f"Missing benchmark dataset: {case_pack_file}")

        cases: list[dict[str, str]] = []
        with open(case_pack_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cases.append(row)

        if limit > 0:
            cases = cases[:limit]

        results: list[dict[str, Any]] = []
        verdicts: dict[str, int] = {}
        patterns: dict[str, int] = {}
        sar_count = 0
        total_exposure = 0.0
        total_latency = 0.0
        total_tool_calls = 0

        for idx, c in enumerate(cases, 1):
            cid = c["case_id"]
            case_file = out_path / f"{cid}.json"

            if replay and case_file.exists():
                logger.info("[%d/%d] Replaying existing answer file for %s", idx, len(cases), cid)
                ans_data = json.loads(case_file.read_text(encoding="utf-8"))
            else:
                logger.info(
                    "[%d/%d] Investigating %s (Trigger: %s)...", idx, len(cases), cid, c.get("trigger_type")
                )
                ans: AnswerFile = self.workflow.run_investigation(c)
                validate_answer(ans)
                ans_data = ans.model_dump()
                case_file.write_text(json.dumps(ans_data, indent=2, default=str), encoding="utf-8")

            results.append(ans_data)

            # Metric rollups
            v = ans_data.get("case", {}).get("verdict", "uncertain")
            verdicts[v] = verdicts.get(v, 0) + 1

            p = ans_data.get("case", {}).get("pattern", "none")
            patterns[p] = patterns.get(p, 0) + 1

            if ans_data.get("sar", {}).get("file"):
                sar_count += 1

            exp = ans_data.get("case", {}).get("exposure_usd", 0.0)
            total_exposure += float(exp)

            total_latency += ans_data.get("latency_s", 0.0)
            total_tool_calls += ans_data.get("tool_calls", 0)

        n_cases = len(cases)
        report = {
            "cases_run": n_cases,
            "verdicts": verdicts,
            "patterns": patterns,
            "sar_filed": sar_count,
            "total_exposure_usd": round(total_exposure, 2),
            "avg_latency_s": round(total_latency / max(1, n_cases), 2),
            "avg_tool_calls": round(total_tool_calls / max(1, n_cases), 1),
            "cases": [
                {
                    "case_id": r["case_id"],
                    "verdict": r["case"]["verdict"],
                    "pattern": r["case"]["pattern"],
                    "fraud_probability": r["case"]["fraud_probability"],
                    "exposure_usd": r["case"]["exposure_usd"],
                    "sar_file": r["sar"]["file"],
                    "latency_s": r.get("latency_s", 0),
                }
                for r in results
            ],
        }

        # Write benchmark reports per PRD Section 35
        bench_dir = out_path.parent / "benchmark" if output_dir else self.settings.data_dir.parent / "benchmark"
        bench_dir.mkdir(parents=True, exist_ok=True)
        (bench_dir / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        self._write_markdown_report(bench_dir / "report.md", report)

        return report

    @staticmethod
    def _write_markdown_report(path: Path, report: dict[str, Any]) -> None:
        md = [
            "# RAVEL 20-Case Benchmark Report",
            "",
            f"**Cases Evaluated**: {report['cases_run']}  ",
            f"**Total Exposure Identified**: ${report['total_exposure_usd']:,.2f} USD  ",
            f"**SARs Filed**: {report['sar_filed']}  ",
            f"**Average Latency**: {report['avg_latency_s']}s / case  ",
            f"**Average Graph Queries / Case**: {report['avg_tool_calls']}  ",
            "",
            "## Verdicts Distribution",
            "",
            "| Verdict | Count | Share |",
            "| :--- | :--- | :--- |",
        ]
        total = max(1, report["cases_run"])
        for v, count in report["verdicts"].items():
            md.append(f"| `{v}` | {count} | {count / total * 100:.1f}% |")

        md.extend(
            [
                "",
                "## Patterns Identified",
                "",
                "| Fraud Pattern | Cases |",
                "| :--- | :--- |",
            ]
        )
        for p, count in report["patterns"].items():
            md.append(f"| `{p}` | {count} |")

        md.extend(
            [
                "",
                "## Case-by-Case Breakdown",
                "",
                "| Case ID | Verdict | Pattern | Probability | Exposure | SAR Filed | Latency |",
                "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
            ]
        )
        for c in report["cases"]:
            sar_badge = "Yes" if c["sar_file"] else "No"
            md.append(
                f"| `{c['case_id']}` | `{c['verdict']}` | `{c['pattern']}` | "
                f"{c['fraud_probability']:.2f} | ${c['exposure_usd']:,.2f} | {sar_badge} | {c['latency_s']}s |"
            )

        path.write_text("\n".join(md), encoding="utf-8")
