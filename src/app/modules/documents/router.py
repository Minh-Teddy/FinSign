from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile, status

from app.modules.documents.schemas import (
    DocumentDetailResponse,
    DocumentResponse,
    ExtractedValue,
    ReportContextCreate,
    ReportType,
    ValueUpdateRequest,
)
from app.modules.documents.service import document_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tải lên tài liệu tài chính (PDF, Excel, CSV)",
)
async def upload_document(
    file: Annotated[UploadFile, File(description="Tập tin tài chính (PDF, XLSX, XLS, CSV)")],
    company_name: Annotated[str, Form(description="Tên doanh nghiệp")] = "",
    tax_code: Annotated[str, Form(description="Mã số thuế")] = "",
    report_type: Annotated[ReportType, Form(description="Loại báo cáo")] = ReportType.UNKNOWN,
    period: Annotated[str, Form(description="Kỳ báo cáo (VD: 2024, Q3/2024)")] = "",
    currency: Annotated[str, Form(description="Đơn vị tiền tệ")] = "VND",
    unit_multiplier: Annotated[float, Form(description="Hệ số đơn vị (1, 1000, 1000000)")] = 1.0,
) -> DocumentResponse:
    context = ReportContextCreate(
        company_name=company_name,
        tax_code=tax_code,
        report_type=report_type,
        period=period,
        currency=currency,
        unit_multiplier=unit_multiplier,
    )
    return await document_service.upload_document(file=file, context_data=context)


@router.post(
    "/{document_id}/process",
    response_model=DocumentDetailResponse,
    summary="Kích hoạt trích xuất số liệu, chuẩn hóa và xác thực kế toán",
)
def process_document(document_id: str) -> DocumentDetailResponse:
    return document_service.process_document(document_id)


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Xem chi tiết tài liệu và kết quả trích xuất",
)
def get_document(document_id: str) -> DocumentDetailResponse:
    return document_service.get_document_detail(document_id)


@router.patch(
    "/{document_id}/values/{value_id}",
    response_model=ExtractedValue,
    summary="Rà soát, phê duyệt hoặc điều chỉnh số liệu trích xuất",
)
def update_value(
    document_id: str,
    value_id: str,
    update_req: ValueUpdateRequest,
) -> ExtractedValue:
    return document_service.update_value(
        document_id=document_id,
        value_id=value_id,
        update_req=update_req,
    )


@router.get(
    "/{document_id}/export",
    summary="Xuất dữ liệu trích xuất ra JSON/Bảng biểu",
)
def export_document(
    document_id: str,
    format: str = Query(default="json", enum=["json", "table"]),
) -> dict:
    return document_service.export_document_data(document_id=document_id, export_format=format)
