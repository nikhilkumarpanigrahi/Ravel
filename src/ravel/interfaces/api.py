"""FastAPI backend service exposing forensic investigation, graph inspection, and approvals."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import create_engine

from ravel.application.benchmark_service import BenchmarkService
from ravel.application.counterfactual import CounterfactualActionOptimizer
from ravel.application.langgraph_workflow import LangGraphWorkflowRunner
from ravel.application.task_runner import task_runner
from ravel.application.workflow import AgentWorkflow
from ravel.config import settings
from ravel.infrastructure.graph import create_graph_adapter
from ravel.infrastructure.llm import build_llm
from ravel.infrastructure.persistence import InvestigationRepository
from ravel.interfaces.security import AnalystUser, require_role

app = FastAPI(title="RAVEL Forensic Workstation API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if settings.env != "development" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Services
graph_adapter = create_graph_adapter(settings)
engine = create_engine(settings.state_db_url)
repo = InvestigationRepository(engine)
llm = build_llm(settings)
state_machine_workflow = AgentWorkflow(graph=graph_adapter, repo=repo, llm=llm)
langgraph_workflow = LangGraphWorkflowRunner(graph=graph_adapter, repo=repo, llm=llm)
benchmark_service = BenchmarkService(settings, graph=graph_adapter)
counterfactual_optimizer = CounterfactualActionOptimizer()


def run_active_workflow(trigger_dict: dict):
    if settings.workflow_orchestrator == "langgraph":
        return langgraph_workflow.run_investigation(trigger_dict)
    return state_machine_workflow.run_investigation(trigger_dict)


workflow = state_machine_workflow

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
    approver: str = "fraud_lead"
    approver_role: str = "L1"


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
    rec = repo.get_case_record(case_id)
    if rec and "case" in rec:
        return rec
    p = settings.output_dir / f"{case_id}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail=f"Case {case_id} not found")


@app.post("/api/cases/{case_id}/replay")
def replay_case(
    case_id: str,
    async_mode: bool = False,
    analyst: AnalystUser = Depends(require_role("L1", "L2", "ADMIN")),
):
    """Run a benchmark case again from its original trigger data."""
    case_pack = settings.data_dir / "case_pack.csv"
    if not case_pack.exists():
        raise HTTPException(status_code=503, detail="Benchmark case pack is unavailable")
    with case_pack.open(encoding="utf-8", newline="") as source:
        trigger = next((row for row in csv.DictReader(source) if row.get("case_id") == case_id), None)
    if trigger is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found in case pack")

    if async_mode:
        task = task_runner.submit(f"Replay {case_id}", run_active_workflow, trigger)
        return JSONResponse(status_code=202, content=task.to_dict())

    try:
        answer = run_active_workflow(trigger)
        return answer.model_dump(mode="json")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/investigations")
def trigger_investigation(
    req: TriggerRequest,
    async_mode: bool = False,
    analyst: AnalystUser = Depends(require_role("L1", "L2", "ADMIN")),
):
    """Trigger an autonomous investigation for a transaction."""
    payload = req.model_dump()
    if async_mode:
        task = task_runner.submit(
            f"Investigation {req.case_id or req.flagged_txn_id}", run_active_workflow, payload
        )
        return JSONResponse(status_code=202, content=task.to_dict())

    try:
        ans = run_active_workflow(payload)
        return ans.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/tasks/{task_id}")
def get_task_status(task_id: str):
    """Check status and results of an asynchronous investigation task."""
    task = task_runner.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.to_dict()


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


@app.get("/api/cases/{case_id}/timeline")
def get_case_timeline(case_id: str):
    """Return the persisted trace for the latest investigation of a case."""
    inv = repo.get_latest_investigation_for_case(case_id)
    if not inv:
        raise HTTPException(status_code=404, detail="No persisted investigation found for case")
    return {
        "investigation_id": inv.investigation_id,
        "state": inv.state.value,
        "state_history": inv.state_history,
        "steps": [step.model_dump() for step in inv.steps],
    }


@app.get("/api/graph/{root_id}")
def get_subgraph(root_id: str, depth: int = 2):
    """Extract interactive subgraph for visualization."""
    return graph_adapter.subgraph_for_viz(root_id, depth=depth)


@app.get("/api/fraud-rings/{customer_id}")
def get_fraud_ring(customer_id: str, limit: int = 25):
    """Detect and return shared-device fraud rings linking multiple cards/customers."""
    shared = graph_adapter.shared_devices(customer_id, limit=limit)
    other_cards = list({r["other_card_id"] for r in shared if r.get("other_card_id")})
    other_customers = list({r["other_customer_id"] for r in shared if r.get("other_customer_id")})
    device_profiles = list({r["device_profile"] for r in shared if r.get("device_profile")})

    nodes: list[dict[str, Any]] = [
        {"id": customer_id, "type": "customer", "label": f"Seed: {customer_id}", "is_seed": True}
    ]
    edges: list[dict[str, Any]] = []

    for dev in device_profiles:
        nodes.append({"id": dev, "type": "device", "label": dev})
        edges.append({"from": customer_id, "to": dev, "type": "USES_DEVICE"})

    for row in shared:
        other_c = row.get("other_customer_id")
        other_card = row.get("other_card_id")
        dev = row.get("device_profile")
        if other_c and other_c not in [n["id"] for n in nodes]:
            nodes.append({"id": other_c, "type": "customer", "label": other_c, "is_seed": False})
        if dev and other_c:
            edges.append({"from": other_c, "to": dev, "type": "USES_DEVICE"})
        if other_card and other_card not in [n["id"] for n in nodes]:
            nodes.append({"id": other_card, "type": "card", "label": other_card})
            if other_c:
                edges.append({"from": other_c, "to": other_card, "type": "OWNS"})

    return {
        "seed_customer_id": customer_id,
        "ring_detected": len(other_cards) > 0,
        "ring_size": len(other_customers) + 1,
        "connected_customers": other_customers,
        "connected_cards": other_cards,
        "device_profiles": device_profiles,
        "total_shared_records": len(shared),
        "subgraph": {"nodes": nodes, "edges": edges},
    }


@app.get("/api/cases/{case_id}/evidence-optimizer")
def get_case_evidence_optimizer(case_id: str):
    """Rank next potential evidence inquiries by Expected Information Gain and cost."""
    from ravel.application.evidence_value_optimizer import EvidenceValueOptimizer

    case_data = get_case(case_id)
    fraud_prob = case_data.get("case", {}).get("fraud_probability", 0.5)
    exposure = case_data.get("case", {}).get("exposure_usd", 0.0)
    customer_id = case_data.get("case", {}).get("customer_id", "")
    txn_id = case_data.get("case", {}).get("flagged_txn_id", "")

    optimizer = EvidenceValueOptimizer()
    options = optimizer.rank_evidence_inquiries(
        current_fraud_prob=fraud_prob,
        exposure_usd=exposure,
        customer_id=customer_id,
        txn_id=txn_id,
    )
    return [opt.to_dict() for opt in options]


@app.post("/api/approvals")
def record_approval(
    decision: ApprovalDecision,
    analyst: AnalystUser = Depends(require_role("L1", "L2", "ADMIN")),
):
    """Analyst approval endpoint for human-in-the-loop governance."""
    requested = repo.get_approval(decision.approval_id)
    if requested is None:
        raise HTTPException(status_code=404, detail="Approval request not found")

    resolved_decision = decision.decision.upper()
    resolved_role = decision.approver_role.upper()
    if resolved_decision not in {"APPROVED", "REJECTED"}:
        raise HTTPException(status_code=422, detail="Decision must be APPROVED or REJECTED")
    if resolved_role not in {"L1", "L2"}:
        raise HTTPException(status_code=403, detail="Approver role must be L1 or L2")
    if requested["route"] == "L2" and resolved_role != "L2":
        raise HTTPException(status_code=403, detail="L2 approval requires a fraud manager")

    try:
        updated = repo.decide_approval(
            decision.approval_id,
            resolved_decision,
            decision.approver,
            decision.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    executions = repo.list_actions(requested["investigation_id"])
    execution = next(
        (item for item in executions if item["action_id"] == f"ACT-{decision.approval_id}"),
        None,
    )
    return {"status": "recorded", **updated, "execution": execution}


@app.get("/api/cases/{case_id}/counterfactuals")
def get_case_counterfactuals(case_id: str):
    """Simulate what-if outcomes and Pareto trade-offs for candidate actions."""
    case_data = get_case(case_id)
    actions = case_data.get("next_best_actions", {}).get("final", [])
    fraud_prob = case_data.get("case", {}).get("fraud_probability", 0.5)
    exposure = case_data.get("case", {}).get("exposure_usd", 0.0)
    cf_results = counterfactual_optimizer.evaluate_candidates(
        candidate_actions=actions,
        fraud_probability=fraud_prob,
        exposure_usd=exposure,
    )
    return [r.to_dict() for r in cf_results]


@app.get("/api/cases/{case_id}/approvals")
def get_case_approvals(case_id: str):
    """Return persisted approval state for a case's investigation runs."""
    return repo.list_case_approvals(case_id)


@app.get("/api/cases/{case_id}/actions")
def get_case_actions(case_id: str):
    """Return durable, simulated action executions for the latest case run."""
    return repo.list_case_actions(case_id)


@app.get("/api/benchmark/results")
def get_benchmark_results():
    bench_file = settings.data_dir.parent / "benchmark" / "results.json"
    if bench_file.exists():
        return json.loads(bench_file.read_text(encoding="utf-8"))
    return {"status": "no_results_yet"}


@app.post("/api/benchmark/run")
def trigger_benchmark(limit: int = 0, replay: bool = True, async_mode: bool = True):
    if not replay and async_mode:
        task = task_runner.submit("Full Benchmark Run", benchmark_service.run_all, limit=limit, replay=False)
        return JSONResponse(status_code=202, content=task.to_dict())
    report = benchmark_service.run_all(limit=limit, replay=replay)
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
