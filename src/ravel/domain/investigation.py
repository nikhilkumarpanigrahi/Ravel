"""Investigation aggregate: trigger, lifecycle, and trace."""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ravel.domain.enums import InvestigationState, TriggerType


class Trigger(BaseModel):
    trigger_id: str = Field(default_factory=lambda: f"TRG-{uuid.uuid4().hex[:12]}")
    type: TriggerType
    case_id: str
    opened_at: datetime
    trigger_text: str
    flagged_txn_id: str
    card_id: str = ""
    customer_id: str = ""
    risk_score: float | None = None


class AgentEvent(BaseModel):
    ts: float = Field(default_factory=time.time)
    step: int
    tool: str
    summary: str
    detail: dict[str, Any] = Field(default_factory=dict)


class Investigation(BaseModel):
    """One investigation run. Persisted across restarts."""

    investigation_id: str = Field(default_factory=lambda: f"INV-{uuid.uuid4().hex[:12]}")
    case_id: str
    state: InvestigationState = InvestigationState.TRIGGERED
    trigger: Trigger
    version: int = 0
    steps: list[AgentEvent] = Field(default_factory=list)
    tool_calls: int = 0
    tokens: int = 0
    latency_s: float = 0.0
    started_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    state_history: list[tuple[str, str]] = Field(default_factory=list)
    stop_reason: str = ""

    def transition(self, new_state: InvestigationState, reason: str = "") -> None:
        self.state_history.append((self.state.value, reason))
        self.state = new_state
        self.version += 1
        self.updated_at = datetime.utcnow()

    def record(self, step: int, tool: str, summary: str, detail: dict[str, Any] | None = None) -> AgentEvent:
        ev = AgentEvent(step=step, tool=tool, summary=summary, detail=detail or {})
        self.steps.append(ev)
        self.tool_calls += 1
        self.updated_at = datetime.utcnow()
        return ev
