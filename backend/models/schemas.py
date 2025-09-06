# models/schemas.py - Enhanced Pydantic Models
from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum

class TemplateName(str, Enum):
    MASTER = "master"
    AUTOMATION_FRAMEWORK = "automation_framework" 
    VENDOR_CHECKLIST = "vendor_checklist"
    SIDE_BY_SIDE = "side_by_side"
    SIDE_BY_SIDE_VENDOR_COMPARE = "side_by_side_vendor_compare"
    RISK_ASSESSMENT = "risk_assessment"
    ORACLE_MAPPING = "oracle_mapping"
    QUICK_ANALYSIS = "quick_analysis"

class FileType(str, Enum):
    PDF = "pdf"
    DOCX = "docx" 
    TXT = "txt"
    CSV = "csv"
    XLSX = "xlsx"
    JSON = "json"

class AnalysisStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class SubscriptionTier(str, Enum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"

class AIProvider(str, Enum):
    AUTO = "auto"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE = "azure"
    OLLAMA = "ollama"

# User Management Schemas
class UserBase(BaseModel):
    email: EmailStr
    company: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class UserCreate(UserBase):
    password: str
    subscription_tier: SubscriptionTier = SubscriptionTier.FREE
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v

class UserUpdate(BaseModel):
    company: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    subscription_tier: Optional[SubscriptionTier] = None

class UserResponse(UserBase):
    id: str
    subscription_tier: SubscriptionTier
    api_calls_count: int
    api_calls_limit: int
    created_at: datetime
    is_active: bool

class AuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str

# Analysis Request Schemas
class AnalysisRequestBase(BaseModel):
    template: TemplateName
    ai_provider: AIProvider = AIProvider.AUTO
    priority: Priority = Priority.NORMAL
    custom_instructions: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class AnalysisRequest(AnalysisRequestBase):
    approach: str = "comprehensive"  # comprehensive, quick_scan, risk_focused, technical_mapping
    
class BulkAnalysisRequest(BaseModel):
    files: List[str]  # File IDs or paths
    template: TemplateName
    ai_provider: AIProvider = AIProvider.AUTO
    priority: Priority = Priority.NORMAL

class AnalysisResponse(BaseModel):
    analysis_id: str
    status: AnalysisStatus
    message: str
    estimated_completion: Optional[datetime] = None
    progress_percentage: Optional[int] = None
    
    # Results (when completed)
    excel_url: Optional[str] = None
    pdf_url: Optional[str] = None
    json_url: Optional[str] = None
    html_url: Optional[str] = None
    
    # Metadata
    file_name: Optional[str] = None
    template: Optional[TemplateName] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time: Optional[float] = None

class AnalysisResult(BaseModel):
    analysis_id: str
    user_id: str
    file_name: str
    template: TemplateName
    status: AnalysisStatus
    
    # Core Results
    document_analysis: Optional[Dict[str, Any]] = None
    risk_assessment: Optional[Dict[str, Any]] = None
    oracle_mapping: Optional[Dict[str, Any]] = None
    compliance_check: Optional[Dict[str, Any]] = None
    
    # Metadata
    confidence_score: Optional[float] = None
    processing_time: Optional[float] = None
    ai_provider_used: Optional[str] = None
    tokens_used: Optional[int] = None
    
    # File outputs
    exports: Optional[Dict[str, str]] = None  # {format: url}
    
    created_at: datetime
    completed_at: Optional[datetime] = None

# Agent-specific schemas
class AgentConfig(BaseModel):
    agent_type: str
    enabled: bool = True
    model_preference: Optional[str] = None
    custom_prompt: Optional[str] = None
    timeout_seconds: int = 120

class WorkflowConfig(BaseModel):
    name: str
    description: str
    agents: List[AgentConfig]
    parallel_execution: bool = False
    failure_strategy: str = "continue"  # continue, stop, retry

# File Management Schemas
class FileUpload(BaseModel):
    filename: str
    content_type: str
    size: int
    checksum: str

class FileMetadata(BaseModel):
    file_id: str
    filename: str
    size: int
    content_type: str
    uploaded_at: datetime
    user_id: str
    analysis_count: int = 0

# Reporting Schemas
class UsageStats(BaseModel):
    period_start: datetime
    period_end: datetime
    total_analyses: int
    successful_analyses: int
    failed_analyses: int
    avg_processing_time: float
    total_tokens_used: int
    most_used_template: str
    
class UserDashboard(BaseModel):
    user: UserResponse
    usage_stats: UsageStats
    recent_analyses: List[AnalysisResponse]
    storage_used: int  # bytes
    storage_limit: int  # bytes

# Subscription and Billing
class SubscriptionLimits(BaseModel):
    monthly_analyses: int
    concurrent_analyses: int
    max_file_size_mb: int
    storage_gb: int
    priority_processing: bool
    api_access: bool
    custom_workflows: bool
    
class SubscriptionPlan(BaseModel):
    tier: SubscriptionTier
    name: str
    description: str
    price_monthly: float
    limits: SubscriptionLimits
    features: List[str]

# Configuration Schemas
class SystemConfig(BaseModel):
    app_name: str = "AI Compensation Automation"
    version: str = "2.0.0"
    maintenance_mode: bool = False
    max_concurrent_analyses: int = 10
    default_ai_provider: AIProvider = AIProvider.AUTO
    supported_file_types: List[FileType]
    max_file_size_mb: int = 100

class AIProviderConfig(BaseModel):
    provider: AIProvider
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    max_tokens: int = 4000
    temperature: float = 0.2
    timeout: int = 120
    rate_limit: Optional[int] = None

# Error Response Schema
class ErrorResponse(BaseModel):
    error: str
    detail: str
    timestamp: datetime
    path: str
    user_id: Optional[str] = None

# Webhook Schemas
class WebhookEvent(BaseModel):
    event_type: str  # analysis.completed, analysis.failed, user.created
    timestamp: datetime
    data: Dict[str, Any]
    user_id: str

class WebhookConfig(BaseModel):
    url: str
    events: List[str]
    secret: Optional[str] = None
    active: bool = True

# Export Schemas
class ExportRequest(BaseModel):
    analysis_id: str
    format: str  # excel, pdf, json, csv
    include_raw_data: bool = False
    custom_template: Optional[str] = None

class ExportResponse(BaseModel):
    export_id: str
    download_url: str
    expires_at: datetime
    file_size: int

# Advanced Analysis Schemas
class ComparisonRequest(BaseModel):
    analysis_ids: List[str]
    comparison_type: str  # side_by_side, delta, benchmark
    include_recommendations: bool = True

class ComparisonResponse(BaseModel):
    comparison_id: str
    analyses_compared: List[str]
    results: Dict[str, Any]
    insights: List[str]
    recommendations: List[str]

# API Response Wrappers
class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
    errors: Optional[List[str]] = None
    warnings: Optional[List[str]] = None
    timestamp: datetime = datetime.utcnow()

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    per_page: int
    pages: int
    has_next: bool
    has_prev: bool

# Health Check Schema
class HealthCheck(BaseModel):
    status: str
    version: str
    timestamp: datetime
    database_status: str
    redis_status: str
    ai_providers_status: Dict[str, str]
    active_analyses: int
    system_load: float