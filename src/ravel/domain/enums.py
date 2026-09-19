"""Domain enums shared across the RAVEL system."""

from __future__ import annotations

import enum


class InvestigationState(enum.StrEnum):
    TRIGGERED = "TRIGGERED"
    CASE_CREATED = "CASE_CREATED"
    INVESTIGATING = "INVESTIGATING"
    EVIDENCE_COLLECTED = "EVIDENCE_COLLECTED"
    ASSESSING = "ASSESSING"
    EVIDENCE_REQUESTED = "EVIDENCE_REQUESTED"
    EVIDENCE_RECEIVED = "EVIDENCE_RECEIVED"
    REASSESSING = "REASSESSING"
    POLICY_EVALUATION = "POLICY_EVALUATION"
    ACTION_PROPOSED = "ACTION_PROPOSED"
    APPROVAL_PENDING = "APPROVAL_PENDING"
    ACTION_EXECUTED = "ACTION_EXECUTED"
    CASE_CLOSED = "CASE_CLOSED"
    MEMORY_UPDATED = "MEMORY_UPDATED"


class CaseStatus(enum.StrEnum):
    OPEN = "open"
    CLOSED_FRAUD = "closed_fraud"
    CLOSED_LEGITIMATE = "closed_legitimate"
    ESCALATED = "escalated"


class Verdict(enum.StrEnum):
    FRAUD = "fraud"
    LEGITIMATE = "legitimate"
    UNCERTAIN = "uncertain"


class Outcome(enum.StrEnum):
    CONFIRMED_FRAUD = "confirmed_fraud"
    CLEARED = "cleared"


class FraudPattern(enum.StrEnum):
    CARD_TESTING = "card_testing"
    CARD_NOT_PRESENT_FRAUD = "card_not_present_fraud"
    CARD_NOT_PRESENT_NEW_DEVICE = "card_not_present_new_device"
    OUT_OF_REGION_USE = "out_of_region_use"
    ACCOUNT_TAKEOVER = "account_takeover"
    UNDOCUMENTED = "undocumented"
    NONE = "none"


class EvidenceSource(enum.StrEnum):
    GRAPH = "graph"
    DOCUMENT = "document"
    CUSTOMER = "customer"
    EXTERNAL = "external"


class EvidenceType(enum.StrEnum):
    TRANSACTION = "transaction"
    RELATIONSHIP = "relationship"
    BEHAVIORAL = "behavioral"
    DEVICE = "device"
    IDENTITY = "identity"
    HISTORICAL_CASE = "historical_case"
    POLICY = "policy"
    CUSTOMER_RESPONSE = "customer_response"
    EXTERNAL_SOURCE = "external_source"
    ANALYST_INPUT = "analyst_input"
    MODEL_HYPOTHESIS = "model_derived_hypothesis"


class PatternStatus(enum.StrEnum):
    DETECTED = "detected"
    PARTIAL = "partial"
    NOT_DETECTED = "not_detected"


class TriggerType(enum.StrEnum):
    RISK_SCORE = "risk_score"
    CUSTOMER_REPORT = "customer_report"
    ANALYST_REQUEST = "analyst_request"


class ActionType(enum.StrEnum):
    ALLOW_TRANSACTION = "ALLOW_TRANSACTION"
    DECLINE_TRANSACTION = "DECLINE_TRANSACTION"
    MONITOR_CARD = "MONITOR_CARD"
    MONITOR_CONNECTED_CARDS = "MONITOR_CONNECTED_CARDS"
    WARN_CUSTOMER = "WARN_CUSTOMER"
    VERIFY_WITH_CUSTOMER = "VERIFY_WITH_CUSTOMER"
    STEP_UP_AUTH = "STEP_UP_AUTH"
    BLOCK_CARD = "BLOCK_CARD"
    BLOCK_ALL_CARDS = "BLOCK_ALL_CARDS"
    GENERATE_REPORT = "GENERATE_REPORT"
    CREATE_CASE = "CREATE_CASE"
    FILE_REPORT = "FILE_REPORT"
    ESCALATE_TO_ANALYST = "ESCALATE_TO_ANALYST"
    CLOSE_NO_FRAUD = "CLOSE_NO_FRAUD"


class ApprovalRoute(enum.StrEnum):
    AUTO = "auto"
    L1 = "L1"
    L2 = "L2"


class ApprovalState(enum.StrEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    REQUIRED = "REQUIRED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class EvidenceRequestType(enum.StrEnum):
    CUSTOMER_VALIDATION = "customer_validation"
    STEP_UP_AUTH = "step_up_auth"
    ANALYST_INFO = "analyst_info"


class DecisionReadiness(enum.StrEnum):
    READY = "READY"
    NOT_READY = "NOT_READY"
    PARTIALLY_READY = "PARTIALLY_READY"


class RiskLevel(enum.StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
