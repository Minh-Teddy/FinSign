from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DocumentStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FileType(str, Enum):
    PDF = "PDF"
    XLSX = "XLSX"
    XLS = "XLS"
    CSV = "CSV"
    UNKNOWN = "UNKNOWN"


class ReportType(str, Enum):
    BALANCE_SHEET = "BALANCE_SHEET"                  # Bảng cân đối kế toán
    INCOME_STATEMENT = "INCOME_STATEMENT"            # Báo cáo kết quả hoạt động kinh doanh
    CASH_FLOW = "CASH_FLOW"                          # Báo cáo lưu chuyển tiền tệ
    NOTES = "NOTES"                                  # Thuyết minh báo cáo tài chính
    UNKNOWN = "UNKNOWN"


class ReviewStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EDITED = "EDITED"


class Lineage(BaseModel):
    file_name: str
    page_or_sheet: str
    cell_or_coordinates: str = ""
    snippet: str = ""


class ReportContextCreate(BaseModel):
    company_name: str = ""
    tax_code: str = ""
    report_type: ReportType = ReportType.UNKNOWN
    period: str = ""
    currency: str = "VND"
    unit_multiplier: float = 1.0


class ReportContextResponse(ReportContextCreate):
    document_id: str


class ExtractedValue(BaseModel):
    id: str
    table_id: str
    standard_code: str = "UNMAPPED"
    raw_metric_name: str
    raw_value: str
    normalized_value: float | None = None
    period: str = ""
    unit: str = "VND"
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    needs_review: bool = False
    review_status: ReviewStatus = ReviewStatus.PENDING
    lineage: Lineage | None = None


class ExtractedTable(BaseModel):
    id: str
    document_id: str
    page_or_sheet: str
    extraction_method: str = "TEXT_PARSER"
    headers: list[str] = Field(default_factory=list)
    values: list[ExtractedValue] = Field(default_factory=list)


class ValidationIssue(BaseModel):
    rule_name: str
    message: str
    severity: str = "WARNING"  # WARNING or ERROR
    difference: float | None = None


class AuditLog(BaseModel):
    id: str
    document_id: str
    value_id: str
    action: str
    user_id: str = "system"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    before_value: Any = None
    after_value: Any = None


class ValueUpdateRequest(BaseModel):
    normalized_value: float | None = None
    standard_code: str | None = None
    review_status: ReviewStatus = ReviewStatus.EDITED
    notes: str = ""


class DocumentResponse(BaseModel):
    id: str
    file_name: str
    file_type: FileType
    file_size_bytes: int
    file_hash: str
    status: DocumentStatus
    uploaded_by: str = "anonymous"
    created_at: datetime
    context: ReportContextResponse | None = None
    validation_issues: list[ValidationIssue] = Field(default_factory=list)
    error_message: str | None = None


class DocumentDetailResponse(DocumentResponse):
    tables: list[ExtractedTable] = Field(default_factory=list)
    total_metrics_extracted: int = 0
    average_confidence: float = 0.0
