from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any, Dict
from datetime import datetime
from enum import Enum


# ─── Auth ─────────────────────────────────────────────────────────────────────

class UserRole(str, Enum):
    admin = "admin"
    analyst = "analyst"
    viewer = "viewer"


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: Optional[str] = None
    organisation: Optional[str] = None
    department: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    organisation: Optional[str]
    department: Optional[str]
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ─── Documents ────────────────────────────────────────────────────────────────

class DocumentStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    indexed = "indexed"
    failed = "failed"


class DocumentResponse(BaseModel):
    id: str
    title: str
    filename: str
    file_type: str
    file_size: Optional[int]
    department: Optional[str]
    tags: List[str]
    status: str
    chunk_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int


# ─── Agent Trace ──────────────────────────────────────────────────────────────

class AgentAction(BaseModel):
    agent: str
    tool: str
    args: Dict[str, Any] = {}
    result_preview: Optional[str] = None
    duration_ms: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Citation(BaseModel):
    document_id: str
    document_title: str
    excerpt: str
    relevance_score: float


# ─── Ask / Chat ───────────────────────────────────────────────────────────────

class AskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    conversation_id: Optional[str] = None
    department_filter: Optional[str] = None
    stream: bool = False


class AskResponse(BaseModel):
    conversation_id: str
    message_id: str
    answer: str
    agent_trace: List[AgentAction] = []
    citations: List[Citation] = []
    suggested_followups: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Alerts ───────────────────────────────────────────────────────────────────

class AlertSeverity(str, Enum):
    critical = "critical"
    warning = "warning"
    info = "info"


class AlertStatus(str, Enum):
    new = "new"
    acknowledged = "acknowledged"
    resolved = "resolved"
    dismissed = "dismissed"


class AlertResponse(BaseModel):
    id: str
    title: str
    summary: str
    severity: str
    status: str
    alert_type: str
    metadata: Dict[str, Any]
    suggested_actions: List[str]
    draft_content: Optional[str]
    related_document_ids: List[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AlertListResponse(BaseModel):
    alerts: List[AlertResponse]
    total: int
    critical_count: int
    warning_count: int


# ─── Analytics ────────────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_documents: int
    documents_indexed: int
    total_queries_today: int
    total_queries_this_week: int
    active_alerts: int
    critical_alerts: int
    avg_query_response_ms: float
    top_departments: List[Dict[str, Any]]
    query_trend: List[Dict[str, Any]]
    most_queried_topics: List[Dict[str, Any]]


class HealthReport(BaseModel):
    overall_status: str
    checks: List[Dict[str, Any]]
    generated_at: datetime
