from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class AuditJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    taskId: str = Field(..., description="Java task id")
    taskNo: str = Field(..., description="Business task no")
    filePath: str = Field(..., description="Local absolute pdf path")
    fileName: str = Field(..., description="Original file name")
    callbackUrl: str = Field(..., description="Java callback endpoint")
    callbackToken: Optional[str] = Field(default=None, description="Callback token")
    modelName: Optional[str] = Field(default=None, description="LLM model name")
    ruleSetCodes: List[str] = Field(default_factory=list, description="Risk rule set codes")
    traceId: Optional[str] = Field(default=None, description="Tracing id")
    tenantId: Optional[str] = Field(default=None, description="Tenant id for data isolation")
    orgId: Optional[str] = Field(default=None, description="Organization id")
    userId: Optional[str] = Field(default=None, description="User id")
    permissionScope: Optional[str] = Field(default=None, description="Permission scope")
    documentId: Optional[str] = Field(default=None, description="Document id for retrieval namespace")
    contractId: Optional[str] = Field(default=None, description="Business contract id")


class AuditJobAcceptedResponse(BaseModel):
    accepted: bool = Field(default=True)
    status: Literal["ACCEPTED"] = Field(default="ACCEPTED")
    pythonJobId: str = Field(..., description="Python side job id")
    message: str = Field(default="task queued")


class VectorCleanupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    taskId: str = Field(..., description="Task id to cleanup vector index")


class VectorCleanupResponse(BaseModel):
    cleaned: bool = Field(..., description="Whether cleanup succeeded")
    taskId: str = Field(..., description="Task id")
    message: str = Field(default="ok")


class RiskItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    seqNo: int = Field(..., ge=1, description="Risk sequence no")
    riskType: str = Field(..., description="Risk type")
    riskLevel: Literal["HIGH", "MEDIUM", "LOW"] = Field(..., description="Risk level")
    riskScore: Optional[float] = Field(default=None, ge=0, le=100)
    clauseTitle: Optional[str] = Field(default=None)
    clausePosition: Optional[str] = Field(default=None)
    pageNo: int = Field(default=1, ge=1, description="Risk page number")
    contractExcerpt: str = Field(..., description="Raw contract excerpt")
    riskDesc: Optional[str] = Field(default=None)
    suggestion: str = Field(..., description="Fix suggestion")
    legalBasis: Optional[str] = Field(default=None)
    evidence: Optional[str] = Field(default=None)


class CallbackSummary(BaseModel):
    riskTotal: int = Field(..., ge=0)
    highRiskCount: int = Field(..., ge=0)
    mediumRiskCount: int = Field(..., ge=0)
    lowRiskCount: int = Field(..., ge=0)


class CallbackError(BaseModel):
    code: str = Field(..., description="Failure code")
    message: str = Field(..., description="Failure message")


class AuditCallbackPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    callbackId: str = Field(..., description="Idempotent callback id")
    taskId: str = Field(..., description="Java task id")
    taskNo: str = Field(..., description="Java task no")
    pythonJobId: str = Field(..., description="Python side job id")
    status: Literal["COMPLETED", "FAILED"] = Field(..., description="Final job status")
    finishedAt: datetime = Field(..., description="Finished time")
    summary: CallbackSummary
    riskItems: List[RiskItem] = Field(default_factory=list)
    error: Optional[CallbackError] = Field(default=None)
