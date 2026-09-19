"""Persistence layer for investigation state, evidence, cases, actions, and memory.

SQLite-backed via SQLAlchemy. Enables replay, idempotency, resumable benchmarks, and the UI.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship
from sqlalchemy.types import JSON as DB_JSON

from ravel.domain.investigation import AgentEvent, Investigation, Trigger


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class Base(DeclarativeBase):
    pass


class InvestigationModel(Base):
    __tablename__ = "investigations"
    investigation_id: Mapped[str] = mapped_column(String, primary_key=True)
    case_id: Mapped[str] = mapped_column(String, index=True)
    state: Mapped[str] = mapped_column(String, default="TRIGGERED")
    trigger_json: Mapped[dict] = mapped_column(DB_JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_s: Mapped[float] = mapped_column(Float, default=0.0)
    stop_reason: Mapped[str] = mapped_column(Text, default="")
    state_history: Mapped[list] = mapped_column(DB_JSON, default=list)
    created_at: Mapped[str] = mapped_column(String, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(String, default=utc_now_iso)

    events: Mapped[list[AgentEventModel]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan", lazy="selectin"
    )
    evidence: Mapped[list[EvidenceModel]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan", lazy="selectin"
    )
    assessments: Mapped[list[AssessmentModel]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan", lazy="selectin"
    )
    requests: Mapped[list[EvidenceRequestModel]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan", lazy="selectin"
    )
    approvals: Mapped[list[ApprovalModel]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan", lazy="selectin"
    )
    actions: Mapped[list[ActionModel]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan", lazy="selectin"
    )


class AgentEventModel(Base):
    __tablename__ = "agent_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    investigation_id: Mapped[str] = mapped_column(String, ForeignKey("investigations.investigation_id"))
    step: Mapped[int] = mapped_column(Integer, default=0)
    ts: Mapped[float] = mapped_column(Float, default=0.0)
    tool: Mapped[str] = mapped_column(String, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    detail_json: Mapped[dict] = mapped_column(DB_JSON, default=dict)

    investigation: Mapped[InvestigationModel] = relationship(back_populates="events")


class EvidenceModel(Base):
    __tablename__ = "evidence"
    evidence_id: Mapped[str] = mapped_column(String, primary_key=True)
    investigation_id: Mapped[str] = mapped_column(String, ForeignKey("investigations.investigation_id"))
    claim: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String, default="graph")
    ref: Mapped[str] = mapped_column(Text, default="")
    entity_ids_json: Mapped[list] = mapped_column(DB_JSON, default=list)
    evidence_type: Mapped[str] = mapped_column(String, default="transaction")
    supports: Mapped[str] = mapped_column(Text, default="")
    contradicts: Mapped[str] = mapped_column(Text, default="")
    strength: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    collected_at: Mapped[str] = mapped_column(String, default=utc_now_iso)
    tool_used: Mapped[str] = mapped_column(String, default="")

    investigation: Mapped[InvestigationModel] = relationship(back_populates="evidence")


class AssessmentModel(Base):
    __tablename__ = "assessments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    investigation_id: Mapped[str] = mapped_column(String, ForeignKey("investigations.investigation_id"))
    step: Mapped[int] = mapped_column(Integer, default=0)
    fraud_probability: Mapped[float] = mapped_column(Float, default=0.0)
    verdict: Mapped[str] = mapped_column(String, default="uncertain")
    pattern: Mapped[str] = mapped_column(String, default="none")
    assessment_json: Mapped[dict] = mapped_column(DB_JSON, default=dict)

    investigation: Mapped[InvestigationModel] = relationship(back_populates="assessments")


class EvidenceRequestModel(Base):
    __tablename__ = "evidence_requests"
    request_id: Mapped[str] = mapped_column(String, primary_key=True)
    investigation_id: Mapped[str] = mapped_column(String, ForeignKey("investigations.investigation_id"))
    type: Mapped[str] = mapped_column(String, default="customer_validation")
    asked_after_step: Mapped[int] = mapped_column(Integer, default=0)
    assumed_response: Mapped[str] = mapped_column(Text, default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    requested_at: Mapped[str] = mapped_column(String, default=utc_now_iso)
    fulfilled: Mapped[bool] = mapped_column(Integer, default=0)

    investigation: Mapped[InvestigationModel] = relationship(back_populates="requests")


class ApprovalModel(Base):
    __tablename__ = "approvals"
    approval_id: Mapped[str] = mapped_column(String, primary_key=True)
    investigation_id: Mapped[str] = mapped_column(String, ForeignKey("investigations.investigation_id"))
    action: Mapped[str] = mapped_column(String, default="")
    route: Mapped[str] = mapped_column(String, default="auto")
    state: Mapped[str] = mapped_column(String, default="PENDING")
    approver: Mapped[str] = mapped_column(String, default="")
    decided_at: Mapped[str] = mapped_column(String, default="")
    reason: Mapped[str] = mapped_column(Text, default="")

    investigation: Mapped[InvestigationModel] = relationship(back_populates="approvals")


class ActionModel(Base):
    __tablename__ = "actions"
    action_id: Mapped[str] = mapped_column(String, primary_key=True)
    investigation_id: Mapped[str] = mapped_column(String, ForeignKey("investigations.investigation_id"))
    action: Mapped[str] = mapped_column(String, default="")
    route: Mapped[str] = mapped_column(String, default="auto")
    reason: Mapped[str] = mapped_column(Text, default="")
    state: Mapped[str] = mapped_column(String, default="NOT_REQUIRED")
    simulated: Mapped[bool] = mapped_column(Integer, default=1)
    executed_at: Mapped[str] = mapped_column(String, default="")

    investigation: Mapped[InvestigationModel] = relationship(back_populates="actions")


class CaseRecordModel(Base):
    __tablename__ = "case_records"
    case_id: Mapped[str] = mapped_column(String, primary_key=True)
    investigation_id: Mapped[str] = mapped_column(String, index=True)
    case_json: Mapped[dict] = mapped_column(DB_JSON, default=dict)
    updated_at: Mapped[str] = mapped_column(String, default=utc_now_iso)


class MemoryEntryModel(Base):
    __tablename__ = "memory"
    memory_id: Mapped[str] = mapped_column(String, primary_key=True)
    case_id: Mapped[str] = mapped_column(String, index=True)
    graph_case_id: Mapped[str] = mapped_column(String, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    verdict: Mapped[str] = mapped_column(String, default="")
    pattern: Mapped[str] = mapped_column(String, default="")
    exposure_usd: Mapped[float] = mapped_column(Float, default=0.0)
    entities_json: Mapped[list] = mapped_column(DB_JSON, default=list)
    device_profiles_json: Mapped[list] = mapped_column(DB_JSON, default=list)
    affected_txn_ids_json: Mapped[list] = mapped_column(DB_JSON, default=list)
    created_at: Mapped[str] = mapped_column(String, default=utc_now_iso)


class Repository:
    def __init__(self, url: str | Any):
        if isinstance(url, str):
            self.engine = create_engine(
                url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {}
            )
        else:
            self.engine = url
        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        return Session(self.engine)

    # ------------------------------------------------------------------ investigations
    def save_investigation(self, inv: Investigation) -> None:
        with self.session() as s:
            s.merge(self._to_inv_model(inv))
            s.commit()

    def get_investigation(self, investigation_id: str) -> Investigation | None:
        with self.session() as s:
            m = s.get(InvestigationModel, investigation_id)
            return self._from_inv_model(m) if m else None

    def _to_inv_model(self, inv: Investigation) -> InvestigationModel:
        return InvestigationModel(
            investigation_id=inv.investigation_id,
            case_id=inv.case_id,
            state=inv.state.value,
            trigger_json=inv.trigger.model_dump(mode="json") if inv.trigger else {},
            version=inv.version,
            tool_calls=inv.tool_calls,
            tokens=inv.tokens,
            latency_s=inv.latency_s,
            stop_reason=inv.stop_reason,
            state_history=[[s, r] for s, r in inv.state_history],
            updated_at=utc_now_iso(),
            events=[
                AgentEventModel(step=e.step, ts=e.ts, tool=e.tool, summary=e.summary, detail_json=e.detail)
                for e in inv.steps
            ],
        )

    def _from_inv_model(self, m: InvestigationModel) -> Investigation:
        from ravel.domain.enums import InvestigationState
        from ravel.domain.investigation import Investigation

        inv = Investigation(
            investigation_id=m.investigation_id,
            case_id=m.case_id,
            state=InvestigationState(m.state),
            trigger=Trigger.model_validate(m.trigger_json),
            version=m.version,
            tool_calls=m.tool_calls,
            tokens=m.tokens,
            latency_s=m.latency_s,
            stop_reason=m.stop_reason,
            state_history=[(s, r) for s, r in (m.state_history or [])],
            steps=[
                AgentEvent(ts=e.ts, step=e.step, tool=e.tool, summary=e.summary, detail=e.detail_json)
                for e in sorted(m.events, key=lambda x: x.ts)
            ],
            started_at=datetime.fromisoformat(m.created_at),
            updated_at=datetime.fromisoformat(m.updated_at),
        )
        return inv

    # ------------------------------------------------------------------ evidence
    def add_evidence(self, inv_id: str, ev: Any) -> None:
        with self.session() as s:
            s.merge(
                EvidenceModel(
                    evidence_id=ev.evidence_id,
                    investigation_id=inv_id,
                    claim=ev.claim,
                    source=ev.source.value if hasattr(ev.source, "value") else str(ev.source),
                    ref=ev.ref,
                    entity_ids_json=list(ev.entity_ids),
                    evidence_type=ev.evidence_type.value
                    if hasattr(ev.evidence_type, "value")
                    else str(ev.evidence_type),
                    supports=ev.supports,
                    contradicts=ev.contradicts,
                    strength=ev.strength,
                    confidence=ev.confidence,
                    collected_at=ev.collected_at.isoformat()
                    if hasattr(ev.collected_at, "isoformat")
                    else str(ev.collected_at),
                    tool_used=ev.tool_used,
                )
            )
            s.commit()

    def list_evidence(self, inv_id: str) -> list[dict[str, Any]]:
        with self.session() as s:
            rows = s.query(EvidenceModel).filter(EvidenceModel.investigation_id == inv_id).all()
            return [
                {
                    "evidence_id": r.evidence_id,
                    "claim": r.claim,
                    "source": r.source,
                    "ref": r.ref,
                    "entity_ids": list(r.entity_ids_json or []),
                    "evidence_type": r.evidence_type,
                    "supports": r.supports,
                    "contradicts": r.contradicts,
                    "strength": r.strength,
                    "confidence": r.confidence,
                    "collected_at": r.collected_at,
                    "tool_used": r.tool_used,
                }
                for r in rows
            ]

    # ------------------------------------------------------------------ assessments
    def add_assessment(self, inv_id: str, step: int, assessment: Any) -> None:
        with self.session() as s:
            s.add(
                AssessmentModel(
                    investigation_id=inv_id,
                    step=step,
                    fraud_probability=assessment.fraud_probability,
                    verdict=assessment.verdict,
                    pattern=assessment.pattern_name,
                    assessment_json=assessment.model_dump(mode="json"),
                )
            )
            s.commit()

    def list_assessments(self, inv_id: str) -> list[dict[str, Any]]:
        with self.session() as s:
            rows = (
                s.query(AssessmentModel)
                .filter(AssessmentModel.investigation_id == inv_id)
                .order_by(AssessmentModel.step)
                .all()
            )
            return [
                {
                    "step": r.step,
                    "fraud_probability": r.fraud_probability,
                    "verdict": r.verdict,
                    "pattern": r.pattern,
                    **r.assessment_json,
                }
                for r in rows
            ]

    # ------------------------------------------------------------------ requests
    def add_request(self, inv_id: str, req: Any) -> None:
        with self.session() as s:
            s.merge(
                EvidenceRequestModel(
                    request_id=req.request_id,
                    investigation_id=inv_id,
                    type=req.type.value if hasattr(req.type, "value") else str(req.type),
                    asked_after_step=req.asked_after_step,
                    assumed_response=req.assumed_response,
                    reason=req.reason,
                    fulfilled=1 if req.fulfilled else 0,
                )
            )
            s.commit()

    def list_requests(self, inv_id: str) -> list[dict[str, Any]]:
        with self.session() as s:
            rows = s.query(EvidenceRequestModel).filter(EvidenceRequestModel.investigation_id == inv_id).all()
            return [
                {
                    "type": r.type,
                    "asked_after_step": r.asked_after_step,
                    "assumed_response": r.assumed_response,
                    "reason": r.reason,
                    "request_id": r.request_id,
                    "fulfilled": bool(r.fulfilled),
                }
                for r in rows
            ]

    # ------------------------------------------------------------------ approvals / actions
    def add_approval(self, inv_id: str, approval: Any) -> None:
        with self.session() as s:
            s.merge(
                ApprovalModel(
                    approval_id=approval.approval_id,
                    investigation_id=inv_id,
                    action=approval.action.value
                    if hasattr(approval.action, "value")
                    else str(approval.action),
                    route=approval.route.value if hasattr(approval.route, "value") else str(approval.route),
                    state=approval.state.value if hasattr(approval.state, "value") else str(approval.state),
                    approver=getattr(approval, "approver", ""),
                    reason=getattr(approval, "decision_reason", "") or getattr(approval, "reason", ""),
                )
            )
            s.commit()

    def list_approvals(self, inv_id: str) -> list[dict[str, Any]]:
        with self.session() as s:
            rows = s.query(ApprovalModel).filter(ApprovalModel.investigation_id == inv_id).all()
            return [
                {
                    "approval_id": r.approval_id,
                    "action": r.action,
                    "route": r.route,
                    "state": r.state,
                    "approver": r.approver,
                    "reason": r.reason,
                    "decided_at": r.decided_at,
                }
                for r in rows
            ]

    def add_action(self, inv_id: str, action: Any) -> None:
        with self.session() as s:
            s.merge(
                ActionModel(
                    action_id=action.action_id or action.action.value,
                    investigation_id=inv_id,
                    action=action.action.value if hasattr(action.action, "value") else str(action.action),
                    route=action.route.value if hasattr(action.route, "value") else str(action.route),
                    reason=action.reason,
                    state=action.state.value if hasattr(action.state, "value") else str(action.state),
                    simulated=1 if action.simulated else 0,
                )
            )
            s.commit()

    # ------------------------------------------------------------------ cases
    def save_case_record(self, case_id: str, inv_id: str, case_json: dict[str, Any]) -> None:
        with self.session() as s:
            m = s.get(CaseRecordModel, case_id)
            if m is None:
                m = CaseRecordModel(case_id=case_id, investigation_id=inv_id)
            m.case_json = case_json
            m.updated_at = utc_now_iso()
            s.merge(m)
            s.commit()

    def get_case_record(self, case_id: str) -> dict[str, Any] | None:
        with self.session() as s:
            m = s.get(CaseRecordModel, case_id)
            return m.case_json if m else None

    # ------------------------------------------------------------------ memory
    def add_memory(self, mem: Any) -> None:
        with self.session() as s:
            s.merge(
                MemoryEntryModel(
                    memory_id=mem.memory_id,
                    case_id=mem.case_id,
                    graph_case_id=mem.graph_case_id,
                    summary=mem.summary,
                    verdict=mem.verdict,
                    pattern=mem.pattern,
                    exposure_usd=mem.exposure_usd,
                    entities_json=list(mem.entities),
                    device_profiles_json=list(mem.device_profiles),
                    affected_txn_ids_json=list(mem.affected_txn_ids),
                )
            )
            s.commit()

    def query_memory(
        self, pattern: str = "", verdict: str = "", entity: str = "", limit: int = 20
    ) -> list[dict[str, Any]]:
        with self.session() as s:
            q = s.query(MemoryEntryModel)
            if pattern:
                q = q.filter(MemoryEntryModel.pattern == pattern)
            if verdict:
                q = q.filter(MemoryEntryModel.verdict == verdict)
            if entity:
                q = q.filter(MemoryEntryModel.entities_json.contains(entity))
            rows = q.order_by(MemoryEntryModel.created_at.desc()).limit(limit).all()
            return [
                {
                    "case_id": r.case_id,
                    "graph_case_id": r.graph_case_id,
                    "summary": r.summary,
                    "verdict": r.verdict,
                    "pattern": r.pattern,
                    "exposure_usd": r.exposure_usd,
                    "entities": list(r.entities_json or []),
                    "device_profiles": list(r.device_profiles_json or []),
                }
                for r in rows
            ]

    def list_investigations(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.session() as s:
            rows = (
                s.query(InvestigationModel).order_by(InvestigationModel.updated_at.desc()).limit(limit).all()
            )
            return [
                {
                    "investigation_id": r.investigation_id,
                    "case_id": r.case_id,
                    "state": r.state,
                    "tool_calls": r.tool_calls,
                    "tokens": r.tokens,
                    "latency_s": r.latency_s,
                    "updated_at": r.updated_at,
                }
                for r in rows
            ]


InvestigationRepository = Repository
