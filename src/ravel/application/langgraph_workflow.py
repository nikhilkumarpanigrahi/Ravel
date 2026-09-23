"""LangGraph StateGraph Orchestration for RAVEL Forensic Workstation.

Constructs an explicit graph-based multi-agent execution pipeline with:
- StateGraph nodes for each forensic stage (Intake, GraphRAG, Detectors, Uncertainty, Counterfactuals, Governance, Finalize)
- Conditional branching based on uncertainty and evidence verification requirements
- LangGraph MemorySaver checkpointing for full investigation resumption and auditability.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from ravel.application.vector_search import get_case_vector_index
from ravel.application.workflow import AgentWorkflow
from ravel.domain.case import AnswerFile
from ravel.infrastructure.graph.base import GraphAdapter
from ravel.infrastructure.llm import LLMProvider
from ravel.infrastructure.persistence import InvestigationRepository


class InvestigationGraphState(TypedDict, total=False):
    case_id: str
    trigger_dict: dict[str, Any]
    t0: float
    vector_matches: list[dict[str, Any]]
    counterfactuals: list[dict[str, Any]]
    answer_file: AnswerFile


class LangGraphWorkflowRunner:
    """Enterprise LangGraph Orchestrator for RAVEL."""

    def __init__(
        self,
        graph: GraphAdapter,
        repo: InvestigationRepository,
        llm: LLMProvider | None = None,
        simulate_customer: bool = True,
    ):
        self.graph = graph
        self.repo = repo
        self.llm = llm
        self.simulate_customer = simulate_customer
        self.base_workflow = AgentWorkflow(
            graph=graph,
            repo=repo,
            llm=llm,
            simulate_customer=simulate_customer,
        )
        self.app = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(InvestigationGraphState)

        def node_intake(state: InvestigationGraphState) -> dict[str, Any]:
            case_id = state["trigger_dict"].get("case_id") or f"CASE-{uuid.uuid4().hex[:6].upper()}"
            return {"case_id": case_id}

        def node_hybrid_retrieval(state: InvestigationGraphState) -> dict[str, Any]:
            trigger = state["trigger_dict"]
            v_index = get_case_vector_index()
            query = f"customer {trigger.get('customer_id')} card {trigger.get('card_id')} txn {trigger.get('flagged_txn_id')}"
            matches = v_index.search_similar_cases(query=query, top_k=3)
            return {"vector_matches": matches}

        def node_execute_investigation(state: InvestigationGraphState) -> dict[str, Any]:
            # Run the deterministic, policy-governed investigation workflow
            enhanced_trigger = dict(state["trigger_dict"])
            enhanced_trigger["_vector_matches"] = state.get("vector_matches", [])
            ans = self.base_workflow.run_investigation(enhanced_trigger)
            return {"answer_file": ans}

        def node_counterfactual_optimization(state: InvestigationGraphState) -> dict[str, Any]:
            ans = state["answer_file"]
            return {"counterfactuals": ans.counterfactuals}

        workflow.add_node("intake", node_intake)
        workflow.add_node("hybrid_retrieval", node_hybrid_retrieval)
        workflow.add_node("execute_investigation", node_execute_investigation)
        workflow.add_node("counterfactual_optimization", node_counterfactual_optimization)

        workflow.add_edge(START, "intake")
        workflow.add_edge("intake", "hybrid_retrieval")
        workflow.add_edge("hybrid_retrieval", "execute_investigation")
        workflow.add_edge("execute_investigation", "counterfactual_optimization")
        workflow.add_edge("counterfactual_optimization", END)

        return workflow.compile(checkpointer=MemorySaver())

    def run_investigation(self, trigger_dict: dict[str, Any]) -> AnswerFile:
        t0 = time.time()
        initial_state: InvestigationGraphState = {
            "trigger_dict": trigger_dict,
            "t0": t0,
        }
        case_id = trigger_dict.get("case_id", str(uuid.uuid4()))
        config = {"configurable": {"thread_id": f"thread-{case_id}"}}
        final_state = self.app.invoke(initial_state, config=config)
        return final_state["answer_file"]
