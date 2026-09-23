"""RAVEL Agent Workflow: 14-state investigation state machine fulfilling the PRD contract."""

from __future__ import annotations

import datetime as dt
import time
import uuid
from typing import Any

from ravel.application.agentic_engine import AgenticInvestigationEngine
from ravel.application.counterfactual import CounterfactualActionOptimizer
from ravel.application.detectors import run_detectors
from ravel.application.evidence_simulation import simulate_customer_response
from ravel.application.graphrag import GraphRAGService
from ravel.application.policy_engine import PolicyEngine
from ravel.application.uncertainty_service import assess_uncertainty
from ravel.domain.case import AnswerFile, Case, CaseMemoryEntry
from ravel.domain.enums import (
    ApprovalState,
    CaseStatus,
    EvidenceSource,
    EvidenceType,
    FraudPattern,
    InvestigationState,
    PatternStatus,
    TriggerType,
    Verdict,
)
from ravel.domain.evidence import EvidenceRecord
from ravel.domain.investigation import Investigation, Trigger
from ravel.domain.pattern import InvestigationContext, PatternResult
from ravel.domain.policy import ApprovalRecord, RecommendedAction
from ravel.domain.uncertainty import UncertaintyJourney
from ravel.infrastructure.graph.base import GraphAdapter
from ravel.infrastructure.llm import DeterministicSynthesizer, LLMProvider, timed_complete
from ravel.infrastructure.persistence import InvestigationRepository


class AgentWorkflow:
    """Executes stateful, deterministic, policy-governed fraud investigations."""

    def __init__(
        self,
        graph: GraphAdapter,
        repo: InvestigationRepository,
        policy_engine: PolicyEngine | None = None,
        simulate_customer: bool = True,
        llm: LLMProvider | None = None,
    ):
        self.graph = graph
        self.repo = repo
        self.policy = policy_engine or PolicyEngine()
        self.rag = GraphRAGService(graph)
        self.simulate_customer = simulate_customer
        self.llm = llm or DeterministicSynthesizer()
        self.agentic_engine = AgenticInvestigationEngine(graph)
        self.counterfactual_optimizer = CounterfactualActionOptimizer()

    def run_investigation(self, trigger_dict: dict[str, Any]) -> AnswerFile:
        """Run complete investigation lifecycle for a trigger, producing the answer file."""
        t0 = time.time()
        tool_calls = 0

        # 1. State: TRIGGERED
        case_id = trigger_dict.get("case_id") or f"CASE-{uuid.uuid4().hex[:6].upper()}"
        opened_at_str = trigger_dict.get("opened_at")
        opened_at = dt.datetime.fromisoformat(opened_at_str) if opened_at_str else dt.datetime.now(dt.UTC)

        trigger = Trigger(
            case_id=case_id,
            type=TriggerType(trigger_dict.get("trigger_type", "risk_score")),
            opened_at=opened_at,
            trigger_text=trigger_dict.get("trigger_text", ""),
            flagged_txn_id=str(trigger_dict.get("flagged_txn_id", "")),
            card_id=trigger_dict.get("card_id", ""),
            customer_id=trigger_dict.get("customer_id", ""),
            risk_score=float(trigger_dict["risk_score"]) if trigger_dict.get("risk_score") else None,
        )

        inv = Investigation(case_id=case_id, trigger=trigger)
        self.repo.save_investigation(inv)

        # 2. State: CASE_CREATED
        inv.transition(InvestigationState.CASE_CREATED, "Case record opened from trigger")
        inv.record(1, "trigger_intake", f"Intake {trigger.type.value} alert on txn {trigger.flagged_txn_id}")
        self.repo.save_investigation(inv)

        # 3. State: INVESTIGATING (Graph Traversal)
        inv.transition(InvestigationState.INVESTIGATING, "Traversing graph neighborhood and historical cases")
        tool_calls += 1
        rag_ctx = self.rag.retrieve(
            customer_id=trigger.customer_id,
            card_id=trigger.card_id,
            txn_id=trigger.flagged_txn_id,
            case_id=case_id,
        )
        vector_matches = trigger_dict.get("_vector_matches", [])
        if vector_matches:
            known_case_ids = {str(case.get("case_id", "")) for case in rag_ctx.historical_cases}
            unique_matches: list[dict[str, Any]] = []
            for match in vector_matches:
                match_id = str(match.get("case_id", ""))
                if match_id and match_id not in known_case_ids:
                    unique_matches.append(match)
                    known_case_ids.add(match_id)
            rag_ctx.historical_cases = unique_matches + rag_ctx.historical_cases
            match_ids = [str(match.get("case_id")) for match in vector_matches if match.get("case_id")]
            rag_ctx.evidence.append(
                EvidenceRecord(
                    case_id=case_id,
                    claim=f"Semantic case-memory retrieval returned: {', '.join(match_ids)}",
                    source=EvidenceSource.DOCUMENT,
                    ref="vector:closed_case_similarity",
                    entity_ids=match_ids,
                    evidence_type=EvidenceType.HISTORICAL_CASE,
                    strength=0.55,
                    confidence=0.70,
                    tool_used="vector:closed_case_similarity",
                    policy_context="Retrieved context only; not treated as proof of the current case",
                )
            )
        tool_calls += 3

        # Assemble InvestigationContext for detectors
        flagged_txn = self.graph.get_transaction(trigger.flagged_txn_id)
        customer_rec = self.graph.get_customer(trigger.customer_id)
        card_hist = self.graph.card_history(trigger.customer_id, limit=30)
        card_window = self.graph.card_window(
            trigger.customer_id,
            anchor_ts=str(flagged_txn.get("ts", "")),
            hours=3.0,
            limit=50,
        )
        tool_calls += 4

        ctx = InvestigationContext(
            txn=flagged_txn,
            customer=customer_rec,
            card_history=card_hist,
            card_window=card_window,
            connected_entities=self.graph.connected_entities(trigger.customer_id),
            related_transactions=self.graph.related_transactions(trigger.customer_id),
            historical_cases=rag_ctx.historical_cases,
            similar_cases=self.graph.similar_cases(limit=3),
        )
        tool_calls += 4

        # 4. State: EVIDENCE_COLLECTED
        inv.transition(
            InvestigationState.EVIDENCE_COLLECTED, "Collected multi-hop graph evidence and run detectors"
        )
        pattern_results: list[PatternResult] = run_detectors(ctx)
        tool_calls += 1

        detected_patterns = [p for p in pattern_results if p.status == PatternStatus.DETECTED]
        partial_patterns = [p for p in pattern_results if p.status == PatternStatus.PARTIAL]

        # 5. State: ASSESSING (Uncertainty & Initial Hypothesis)
        inv.transition(
            InvestigationState.ASSESSING, "Evaluating uncertainty, patterns, and policy thresholds"
        )
        inv.record(
            len(inv.steps) + 1,
            "pattern_detection",
            f"Evaluated 5 detectors: {len(detected_patterns)} detected",
        )

        # Determine primary candidate pattern
        top_pattern = FraudPattern.NONE
        candidate_confidence = 0.15
        affected_txn_ids: list[str] = []
        first_suspicious_id = ""

        if detected_patterns:
            detected_patterns.sort(key=lambda x: x.confidence, reverse=True)
            top_pattern = detected_patterns[0].pattern
            candidate_confidence = detected_patterns[0].confidence
            affected_txn_ids = detected_patterns[0].affected_txn_ids
            first_suspicious_id = detected_patterns[0].first_suspicious_txn_id
        elif partial_patterns:
            partial_patterns.sort(key=lambda x: x.confidence, reverse=True)
            top_pattern = partial_patterns[0].pattern
            candidate_confidence = partial_patterns[0].confidence
            affected_txn_ids = partial_patterns[0].affected_txn_ids

        # If trigger is a direct customer report dispute
        is_customer_dispute = trigger.type == TriggerType.CUSTOMER_REPORT
        if is_customer_dispute:
            if top_pattern == FraudPattern.NONE:
                top_pattern = FraudPattern.CARD_NOT_PRESENT_FRAUD
            candidate_confidence = max(candidate_confidence, 0.78)
            if trigger.flagged_txn_id not in affected_txn_ids:
                affected_txn_ids.append(trigger.flagged_txn_id)
            first_suspicious_id = first_suspicious_id or trigger.flagged_txn_id

        # Run principled agentic active-learning loop for autonomous hypothesis testing
        agent_probability, agent_evs, agent_trace = self.agentic_engine.run_agentic_loop(
            case_id=case_id,
            customer_id=trigger.customer_id,
            card_id=trigger.card_id,
            flagged_txn_id=trigger.flagged_txn_id,
            trigger_type=trigger.type,
            risk_score=trigger.risk_score,
            exposure_usd=float(flagged_txn.get("amount", 0.0)),
            has_device=(flagged_txn.get("channel") or "").lower() != "in_person",
            max_steps=3,
        )
        for a_ev in agent_evs:
            if not any(e.ref == a_ev.ref for e in rag_ctx.evidence):
                rag_ctx.evidence.append(a_ev)
        # Detector evidence remains primary; independently acquired graph evidence
        # contributes to the actual posterior instead of being display-only.
        if agent_evs:
            candidate_confidence = round(
                min(0.99, max(0.01, (0.70 * candidate_confidence) + (0.30 * agent_probability))),
                3,
            )

        # Check for recurring legitimate pattern
        is_recurring = False
        amt = flagged_txn.get("amount", 0)
        same_amt_count = sum(1 for t in card_hist if abs(float(t.get("amount", 0)) - amt) < 0.01)
        if same_amt_count >= 2:
            is_recurring = True

        # Calculate exposure
        exposure = 0.0
        if affected_txn_ids:
            for tid in set(affected_txn_ids):
                try:
                    t_info = self.graph.get_transaction(tid)
                    exposure += abs(float(t_info.get("amount", 0)))
                except Exception:
                    pass
        elif candidate_confidence > 0.4:
            exposure = float(flagged_txn.get("amount", 0))

        # Initial actions under R1/R5/R7
        initial_actions = self.policy.evaluate_initial_actions(
            verdict=Verdict.UNCERTAIN if candidate_confidence < 0.85 else Verdict.FRAUD,
            fraud_prob=candidate_confidence,
            pattern=top_pattern,
            exposure_usd=exposure,
            signals_count=len(detected_patterns) + (1 if is_customer_dispute else 0),
            has_shared_device=bool(rag_ctx.connected_cards),
            is_recurring=is_recurring,
            cleared_over_100=(exposure > 100.0),
        )
        initial_uncertainty = assess_uncertainty(
            fraud_probability=candidate_confidence,
            model_risk_score=trigger.risk_score,
            verdict=Verdict.UNCERTAIN if candidate_confidence < 0.85 else Verdict.FRAUD,
            pattern_results=pattern_results,
            evidence_count=len(rag_ctx.evidence),
            has_history=bool(rag_ctx.historical_cases),
            has_connected_entities=bool(ctx.connected_entities),
        )

        # 6. & 7. External Evidence Request (R1 Verification or Customer Report follow-up)
        evidence_requests_payload: list[dict[str, Any]] = []
        customer_response = ""

        needs_verification = any(
            a.action in (RecommendedAction(action=a.action, route=a.route).action)
            for a in initial_actions
            if a.action.value in ("VERIFY_WITH_CUSTOMER", "STEP_UP_AUTH")
        )

        if needs_verification or is_customer_dispute:
            inv.transition(
                InvestigationState.EVIDENCE_REQUESTED, "Dispatched verification request to cardholder"
            )
            step_no = len(inv.steps) + 1

            assumed_resp = simulate_customer_response(
                trigger_type=trigger.type,
                trigger_text=trigger.trigger_text,
                is_recurring=is_recurring,
            )
            req_type = "customer_validation"
            evidence_requests_payload.append(
                {
                    "type": req_type,
                    "asked_after_step": step_no,
                    "assumed_response": assumed_resp if self.simulate_customer else "",
                    "simulation_disclosure": "Synthetic response for benchmark/demo; not ground truth",
                }
            )
            inv.record(step_no, "request_customer_validation", f"Dispatched {req_type} request to customer")

            if self.simulate_customer:
                customer_response = assumed_resp
                # 8. State: EVIDENCE_RECEIVED
                inv.transition(
                    InvestigationState.EVIDENCE_RECEIVED,
                    "Simulated customer response received and recorded with disclosure",
                )
                rag_ctx.evidence.append(
                    EvidenceRecord(
                        case_id=case_id,
                        claim=f"Simulated customer verification response: {assumed_resp}",
                        source=EvidenceSource.CUSTOMER,
                        ref=f"evidence_request:{len(evidence_requests_payload)}",
                        entity_ids=[trigger.customer_id],
                        evidence_type=EvidenceType.CUSTOMER_RESPONSE,
                        strength=0.7,
                        confidence=0.5,
                        policy_context="Synthetic benchmark/demo evidence; not ground truth",
                    )
                )

        # 9. State: REASSESSING
        inv.transition(
            InvestigationState.REASSESSING,
            "Reassessing probability and verdict in light of complete evidence",
        )
        final_fraud_prob = candidate_confidence
        final_verdict = Verdict.UNCERTAIN
        response_norm = customer_response.lower()
        customer_denied = any(
            term in response_norm for term in ("deni", "never made", "stolen", "unauthorized")
        )
        customer_confirmed = (
            any(term in response_norm for term in ("confirm", "legitimate", "made this purchase"))
            and not customer_denied
        )
        customer_unreachable = any(
            term in response_norm for term in ("no reply", "timeout", "unreachable", "unverified")
        )

        if customer_denied:
            base_risk = trigger.risk_score if trigger.risk_score is not None else 0.65
            final_fraud_prob = round(
                min(0.985, max(0.88, 0.84 + (candidate_confidence * 0.08) + (base_risk * 0.05))), 3
            )
            final_verdict = Verdict.FRAUD
            if top_pattern == FraudPattern.NONE:
                top_pattern = FraudPattern.CARD_NOT_PRESENT_FRAUD
        elif customer_confirmed:
            base_risk = trigger.risk_score if trigger.risk_score is not None else 0.50
            final_fraud_prob = round(max(0.025, min(0.085, 0.03 + (base_risk * 0.04))), 3)
            final_verdict = Verdict.LEGITIMATE
            top_pattern = FraudPattern.NONE
            affected_txn_ids = []
            exposure = 0.0
        elif candidate_confidence >= 0.85:
            final_verdict = Verdict.FRAUD
        elif candidate_confidence <= 0.18:
            final_verdict = Verdict.LEGITIMATE
            top_pattern = FraudPattern.NONE
            affected_txn_ids = []
            exposure = 0.0
        else:
            final_verdict = Verdict.UNCERTAIN

        if final_verdict == Verdict.LEGITIMATE:
            top_pattern = FraudPattern.NONE
            affected_txn_ids = []
            exposure = 0.0

        # Ensure affected_txn_ids includes flagged if fraud
        if final_verdict == Verdict.FRAUD and trigger.flagged_txn_id not in affected_txn_ids:
            affected_txn_ids.insert(0, trigger.flagged_txn_id)

        # 10. State: POLICY_EVALUATION
        inv.transition(
            InvestigationState.POLICY_EVALUATION, "Computing final next-best-action recommendations"
        )
        final_actions = self.policy.evaluate_final_actions(
            verdict=final_verdict,
            final_fraud_prob=final_fraud_prob,
            pattern=top_pattern,
            exposure_usd=exposure,
            customer_response=customer_response,
            has_shared_device=bool(rag_ctx.connected_cards),
            connected_card_ids=rag_ctx.connected_cards,
            is_recurring=is_recurring,
        )
        final_uncertainty = assess_uncertainty(
            fraud_probability=final_fraud_prob,
            model_risk_score=trigger.risk_score,
            verdict=final_verdict,
            pattern_results=pattern_results,
            evidence_count=len(rag_ctx.evidence),
            has_history=bool(rag_ctx.historical_cases),
            has_connected_entities=bool(ctx.connected_entities),
            customer_response=customer_response,
        )
        uncertainty_journey = UncertaintyJourney(
            initial=initial_uncertainty,
            final=final_uncertainty,
            what_reduced_uncertainty=(
                ["customer validation response"] if customer_response and not customer_unreachable else []
            ),
        )

        # What changed description
        if not evidence_requests_payload:
            what_changed = "nothing"
        elif customer_denied:
            what_changed = (
                f"Customer response confirmed unauthorized use, increasing fraud probability to {final_fraud_prob:.2f}. "
                f"Actions escalated from verification to card block and case creation."
            )
        elif customer_confirmed:
            what_changed = "Customer confirmed transaction as legitimate; alert closed with no fraud."
        elif customer_unreachable:
            what_changed = (
                "The cardholder did not respond, so ownership remains unverified. "
                "R4 monitoring and pending-authorization controls replace any customer-denial action."
            )
        elif final_verdict == Verdict.FRAUD:
            what_changed = (
                f"Independent transaction and relationship evidence supports fraud probability {final_fraud_prob:.2f}; "
                "the recommendation does not rely on a customer denial."
            )
        else:
            what_changed = "Uncertainty persisted after inquiry; case escalated to analyst for manual review."

        if self.llm and getattr(self.llm, "name", "") != "deterministic" and customer_response:
            try:
                change_sys = (
                    "You are a senior bank fraud risk officer. Explain policy recommendation adjustments."
                )
                change_user = (
                    f"Initial Proposed Actions: {[a.action.value for a in initial_actions]}\n"
                    f"Customer Evidence Received: {customer_response}\n"
                    f"Final Verdict: {final_verdict.value}\n"
                    f"Final Actions: {[a.action.value for a in final_actions]}\n"
                    "Explain in 1-2 concise sentences what changed in the risk posture and why actions updated."
                )
                txt, tok = timed_complete(self.llm, change_sys, change_user, max_tokens=120)
                what_changed = txt.strip()
                inv.tokens += tok
            except Exception:
                pass

        # Attach stable approval request identifiers to active, non-auto actions.
        for act in final_actions:
            if act.requires_approval and not act.approval_id:
                act.approval_id = f"APP-{uuid.uuid4().hex[:8].upper()}"

        nba = self.policy.assemble_nba(initial_actions, final_actions, what_changed)

        # 11. State: ACTION_PROPOSED & APPROVAL_PENDING
        inv.transition(InvestigationState.ACTION_PROPOSED, "Proposed policy actions with approval routing")
        pending_approvals = [act for act in final_actions if act.requires_approval]
        for act in pending_approvals:
            rec = ApprovalRecord(
                approval_id=act.approval_id,
                action=act.action,
                case_id=case_id,
                route=act.route,
                state=ApprovalState.PENDING,
                requestor="agent",
                policy_version="1.0",
            )
            self.repo.add_approval(inv.investigation_id, rec)

        # 12. Execute only auto-routed actions; governed actions remain pending.
        if pending_approvals:
            inv.transition(
                InvestigationState.APPROVAL_PENDING,
                f"Waiting for {len(pending_approvals)} governed action approval(s)",
            )
        else:
            inv.transition(InvestigationState.ACTION_EXECUTED, "Executed automated policy actions")

        # 13. State: CASE_CLOSED & SAR generation
        inv.transition(InvestigationState.CASE_CLOSED, "Investigation closed with defensible decision")
        inv.stop_reason = (
            "Available graph and verification evidence support the recorded decision; policy actions remain recommendations until any required approval is recorded."
            if (
                final_verdict in (Verdict.FRAUD, Verdict.LEGITIMATE)
                or final_fraud_prob >= 0.85
                or final_fraud_prob <= 0.15
            )
            else "Further steps unlikely to change verdict; escalated under policy R8."
        )

        # Dates for SAR
        activity_dates = []
        if flagged_txn.get("ts"):
            d_str = str(flagged_txn["ts"])[:10]
            activity_dates = [d_str, d_str]

        # Narrative / Summary
        summary_text = (
            f"Investigation of {trigger.case_id} ({trigger.customer_id} / {trigger.card_id}): "
            f"Flagged transaction {trigger.flagged_txn_id} (${flagged_txn.get('amount', 0):.2f}) evaluated under {top_pattern.value}. "
            + (f"Assumed verification outcome: {customer_response}. " if customer_response else "")
            + (
                f"Identified {len(affected_txn_ids)} affected transaction(s) totaling ${exposure:.2f} USD exposure. "
                if affected_txn_ids
                else "No fraudulent exposure confirmed. "
            )
            + f"Verdict: {final_verdict.value} (fraud probability: {final_fraud_prob:.2f}). "
            + f"Recommended {len(final_actions)} action(s) adhering to bank policy."
        )

        if self.llm and getattr(self.llm, "name", "") != "deterministic":
            try:
                sum_sys = (
                    "You are RAVEL, an autonomous fraud investigation AI agent at a major bank. "
                    "Write a concise, professional case investigation summary summarizing the flagged transaction, "
                    "graph evidence, customer verification, exposure, and final verdict."
                )
                sum_user = (
                    f"{rag_ctx.to_summary_prompt()}\n"
                    f"Customer Response: {customer_response or 'None'}\n"
                    f"Exposure USD: ${exposure:.2f}\n"
                    f"Pattern Detected: {top_pattern.value}\n"
                    f"Final Verdict: {final_verdict.value} (probability: {final_fraud_prob:.2f})\n"
                    f"Recommended Actions: {[a.action.value for a in final_actions]}"
                )
                txt, tok = timed_complete(self.llm, sum_sys, sum_user, max_tokens=250)
                summary_text = txt.strip()
                inv.tokens += tok
            except Exception:
                pass

        sar = self.policy.generate_sar(
            final_actions=final_actions,
            case_id=case_id,
            customer_id=trigger.customer_id,
            card_id=trigger.card_id,
            pattern=top_pattern,
            exposure_usd=exposure,
            affected_txn_ids=affected_txn_ids,
            connected_cards=rag_ctx.connected_cards,
            device_profiles=rag_ctx.device_profiles,
            activity_dates=activity_dates,
            customer_response=customer_response,
            summary=summary_text,
        )

        if sar.file and self.llm and getattr(self.llm, "name", "") != "deterministic":
            try:
                sar_sys = (
                    "You are a BSA/AML regulatory compliance officer. Draft a formal Suspicious Activity Report (SAR) narrative "
                    "under FinCEN 31 CFR 1020.320. State the suspicious activity chronology, entities involved, "
                    "typology identified, and legal rationale for filing."
                )
                sar_user = (
                    f"Case ID: {case_id}\n"
                    f"Subject Customer ID: {trigger.customer_id}, Card: {trigger.card_id}\n"
                    f"Pattern: {top_pattern.value}\n"
                    f"Total Suspicious Amount: ${exposure:.2f} USD\n"
                    f"Connected Cards: {', '.join(rag_ctx.connected_cards[:15])}\n"
                    f"Connected Devices: {', '.join(rag_ctx.device_profiles[:5])}\n"
                    f"Evidence Summary:\n{summary_text}"
                )
                txt, tok = timed_complete(self.llm, sar_sys, sar_user, max_tokens=400)
                sar.narrative = txt.strip()
                inv.tokens += tok
            except Exception:
                pass

        # 14. State: MEMORY_UPDATED (Write back to graph and memory store)
        inv.transition(
            InvestigationState.MEMORY_UPDATED, "Case memory recorded into graph and persistence layer"
        )
        graph_case_payload = {
            "graph_case_id": f"RAVEL-{case_id}",
            "case_id": case_id,
            "customer_id": trigger.customer_id,
            "card_id": trigger.card_id,
            "verdict": final_verdict.value,
            "pattern": top_pattern.value,
            "exposure_usd": exposure,
            "affected_txn_ids": affected_txn_ids,
            "connected_card_ids": rag_ctx.connected_cards,
            "connected_device_profiles": rag_ctx.device_profiles,
            "actions_taken": [action.action.value for action in final_actions],
            "report_filed": sar.file,
            "summary": summary_text,
        }
        tool_calls += 1
        graph_case_id = self.graph.write_case(graph_case_payload)

        # Write memory entry
        self.repo.add_memory(
            CaseMemoryEntry(
                case_id=case_id,
                graph_case_id=graph_case_id,
                summary=summary_text,
                verdict=final_verdict.value,
                pattern=top_pattern.value,
                exposure_usd=exposure,
                affected_txn_ids=affected_txn_ids,
                entities=[trigger.customer_id, trigger.card_id] + rag_ctx.connected_cards,
                device_profiles=rag_ctx.device_profiles,
                actions_taken=[a.action.value for a in final_actions],
            )
        )

        # Build Case deliverable (Part 1)
        similar_prior = [c.get("case_id", "") for c in rag_ctx.historical_cases[:2] if c.get("case_id")]
        case_deliverable = Case(
            case_id=case_id,
            status=CaseStatus.CLOSED_FRAUD
            if final_verdict == Verdict.FRAUD
            else (
                CaseStatus.CLOSED_LEGITIMATE if final_verdict == Verdict.LEGITIMATE else CaseStatus.ESCALATED
            ),
            verdict=final_verdict,
            fraud_probability=round(final_fraud_prob, 2),
            pattern=top_pattern,
            pattern_description="Undocumented coordinated cross-account behavior"
            if top_pattern == FraudPattern.UNDOCUMENTED
            else "",
            affected_txn_ids=affected_txn_ids,
            first_suspicious_txn_id=first_suspicious_id or (affected_txn_ids[0] if affected_txn_ids else ""),
            connected_card_ids=rag_ctx.connected_cards,
            connected_device_profiles=rag_ctx.device_profiles,
            exposure_usd=round(exposure, 2),
            evidence=[Case.evidence_from(e) for e in rag_ctx.evidence],
            similar_prior_cases=similar_prior,
            summary=summary_text,
            written_to_graph=True,
            graph_case_id=graph_case_id,
        )

        latency_s = round(time.time() - t0, 2)
        inv.tool_calls = tool_calls
        inv.latency_s = latency_s
        inv.tokens = inv.tokens
        self.repo.save_investigation(inv)

        counterfactuals = self.counterfactual_optimizer.evaluate_candidates(
            candidate_actions=[action.model_dump(mode="json") for action in final_actions],
            fraud_probability=final_fraud_prob,
            exposure_usd=exposure,
            sar_required=sar.file,
        )

        # Construct full AnswerFile
        answer = AnswerFile(
            case_id=case_id,
            case=case_deliverable,
            evidence_requests=evidence_requests_payload,
            next_best_actions=nba.model_dump(mode="json"),
            uncertainty=uncertainty_journey,
            sar=sar,
            stop_reason=inv.stop_reason,
            tool_calls=tool_calls,
            tokens=inv.tokens,
            latency_s=latency_s,
            agent_trace=agent_trace,
            counterfactuals=[result.to_dict() for result in counterfactuals],
        )
        self.repo.save_case_record(case_id, inv.investigation_id, answer.model_dump(mode="json"))
        return answer
