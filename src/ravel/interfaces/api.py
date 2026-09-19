"""FastAPI backend service exposing forensic investigation, graph inspection, and approvals."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import create_engine

from ravel.application.benchmark_service import BenchmarkService
from ravel.application.workflow import AgentWorkflow
from ravel.config import settings
from ravel.infrastructure.graph.mock import MockGraphAdapter
from ravel.infrastructure.persistence import InvestigationRepository

app = FastAPI(title="RAVEL Forensic Workstation API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Services
level0_dir = settings.data_dir.parent / "data" / "level0"
graph_adapter = MockGraphAdapter(level0_dir)
engine = create_engine(settings.state_db_url)
repo = InvestigationRepository(engine)
workflow = AgentWorkflow(graph=graph_adapter, repo=repo)
benchmark_service = BenchmarkService(settings, graph=graph_adapter)

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


class TriggerRequest(BaseModel):
    case_id: str = ""
    trigger_type: str = "risk_score"
    trigger_text: str = ""
    flagged_txn_id: str
    card_id: str = ""
    customer_id: str = ""
    risk_score: float | None = None


class ApprovalDecision(BaseModel):
    approval_id: str
    decision: str  # APPROVED or REJECTED
    reason: str = ""
    approver: str = "analyst_l1"


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name, "graph": graph_adapter.health()}


@app.get("/api/cases")
def list_cases():
    """List all available cases in the benchmark or repo."""
    cases_dir = settings.output_dir
    results = []
    if cases_dir.exists():
        for p in sorted(cases_dir.glob("*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                results.append(
                    {
                        "case_id": d.get("case_id", p.stem),
                        "verdict": d.get("case", {}).get("verdict", "unknown"),
                        "pattern": d.get("case", {}).get("pattern", "none"),
                        "exposure_usd": d.get("case", {}).get("exposure_usd", 0.0),
                        "fraud_probability": d.get("case", {}).get("fraud_probability", 0.0),
                        "status": d.get("case", {}).get("status", "open"),
                        "sar_file": d.get("sar", {}).get("file", False),
                    }
                )
            except Exception:
                continue
    return results


@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    p = settings.output_dir / f"{case_id}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    rec = repo.get_case_record(case_id)
    if rec:
        return rec
    raise HTTPException(status_code=404, detail=f"Case {case_id} not found")


@app.post("/api/investigations")
def trigger_investigation(req: TriggerRequest):
    """Trigger an autonomous investigation for a transaction."""
    try:
        ans = workflow.run_investigation(req.model_dump())
        return ans.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/investigations/{inv_id}")
def get_investigation(inv_id: str):
    inv = repo.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return inv.model_dump()


@app.get("/api/investigations/{inv_id}/timeline")
def get_investigation_timeline(inv_id: str):
    inv = repo.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return {
        "investigation_id": inv_id,
        "state": inv.state.value,
        "state_history": inv.state_history,
        "steps": [s.model_dump() for s in inv.steps],
    }


@app.get("/api/graph/{root_id}")
def get_subgraph(root_id: str, depth: int = 2):
    """Extract interactive subgraph for visualization."""
    return graph_adapter.subgraph_for_viz(root_id, depth=depth)


@app.post("/api/approvals")
def record_approval(decision: ApprovalDecision):
    """Analyst approval endpoint for human-in-the-loop governance."""
    return {
        "status": "recorded",
        "approval_id": decision.approval_id,
        "decision": decision.decision,
        "approver": decision.approver,
    }


@app.get("/api/benchmark/results")
def get_benchmark_results():
    bench_file = settings.data_dir.parent / "benchmark" / "results.json"
    if bench_file.exists():
        return json.loads(bench_file.read_text(encoding="utf-8"))
    return {"status": "no_results_yet"}


@app.post("/api/benchmark/run")
def trigger_benchmark(limit: int = 0):
    report = benchmark_service.run_all(limit=limit)
    return report


# Serve single-page forensic workstation UI
@app.get("/")
def serve_ui():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse(
        {"message": "RAVEL Forensic API Running. Workstation UI static file not installed yet."}
    )


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
