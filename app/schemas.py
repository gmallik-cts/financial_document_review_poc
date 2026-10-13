from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, ConfigDict

class WorkflowType(str, Enum):
    ACCOUNT_ONBOARDING = "ACCOUNT_ONBOARDING"
    ACCOUNT_TRANSFER = "ACCOUNT_TRANSFER"

class CaseStatus(str, Enum):
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    REVIEW_READY = "REVIEW_READY"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"
    PROCESSING_FAILED = "PROCESSING_FAILED"
    DECIDED = "DECIDED"

class Recommendation(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"

class DocumentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_type: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=100000)  # local POC only

class CreateCaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    external_reference: str = Field(min_length=1, max_length=120)
    workflow_type: WorkflowType
    documents: list[DocumentInput] = Field(min_length=1, max_length=10)

class Finding(BaseModel):
    code: str
    severity: str
    field: str | None = None
    summary: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    requires_human_review: bool = False

class CaseResult(BaseModel):
    case_id: str
    status: CaseStatus
    recommendation: Recommendation
    reason_codes: list[str]
    findings: list[Finding]
    masked_for_ai: bool = True
    ai_provider_called: bool = False
    policy_version: str = "poc-policy-v1"
    rule_version: str = "poc-rules-v1"

class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: str = Field(pattern="^(APPROVED|REJECTED|NEEDS_MORE_INFORMATION)$")
    reviewer_id: str = Field(min_length=1, max_length=120)
    comments: str | None = Field(default=None, max_length=2000)
    override_reason: str | None = Field(default=None, max_length=500)
