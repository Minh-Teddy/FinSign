import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.modules.documents.extractors.excel_extractor import ExcelExtractor
from app.modules.documents.extractors.pdf_extractor import PdfExtractor
from app.modules.documents.repository import document_repo
from app.modules.documents.schemas import (
    AuditLog,
    DocumentDetailResponse,
    DocumentResponse,
    DocumentStatus,
    ExtractedValue,
    FileType,
    ReportContextCreate,
    ReportContextResponse,
    ValueUpdateRequest,
)
from app.modules.documents.validator import validate_accounting_rules


class DocumentService:
    def __init__(self) -> None:
        self.upload_dir = Path(settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.excel_extractor = ExcelExtractor()
        self.pdf_extractor = PdfExtractor()

    def _determine_file_type(self, filename: str) -> FileType:
        ext = Path(filename).suffix.lower()
        if ext == ".pdf":
            return FileType.PDF
        elif ext == ".xlsx":
            return FileType.XLSX
        elif ext == ".xls":
            return FileType.XLS
        elif ext == ".csv":
            return FileType.CSV
        return FileType.UNKNOWN

    async def upload_document(
        self,
        file: UploadFile,
        context_data: ReportContextCreate,
        uploaded_by: str = "user",
    ) -> DocumentResponse:
        filename = file.filename or "unknown_file"
        file_type = self._determine_file_type(filename)
        if file_type == FileType.UNKNOWN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Định dạng file không được hỗ trợ. Chỉ chấp nhận .pdf, .xlsx, .xls, .csv.",
            )

        content = await file.read()
        file_size = len(content)
        max_bytes = settings.max_upload_size_mb * 1024 * 1024

        if file_size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Dung lượng file vượt quá giới hạn cho phép ({settings.max_upload_size_mb} MB).",
            )

        # Tính toán SHA-256 hash
        file_hash = hashlib.sha256(content).hexdigest()
        existing = document_repo.find_by_hash(file_hash)
        if existing:
            return existing

        doc_id = f"doc_{uuid.uuid4().hex[:10]}"
        saved_filename = f"{doc_id}_{filename}"
        saved_path = self.upload_dir / saved_filename

        import anyio

        await anyio.to_thread.run_sync(saved_path.write_bytes, content)

        context_res = ReportContextResponse(
            document_id=doc_id,
            company_name=context_data.company_name,
            tax_code=context_data.tax_code,
            report_type=context_data.report_type,
            period=context_data.period,
            currency=context_data.currency,
            unit_multiplier=context_data.unit_multiplier,
        )

        doc = DocumentResponse(
            id=doc_id,
            file_name=filename,
            file_type=file_type,
            file_size_bytes=file_size,
            file_hash=file_hash,
            status=DocumentStatus.PENDING,
            uploaded_by=uploaded_by,
            created_at=datetime.now(UTC),
            context=context_res,
        )

        return document_repo.save_document(doc)

    def process_document(self, document_id: str) -> DocumentDetailResponse:
        doc = document_repo.get_document(document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy tài liệu yêu cầu.",
            )

        document_repo.update_status(document_id, DocumentStatus.PROCESSING)

        saved_path = None
        for p in self.upload_dir.glob(f"{document_id}_*"):
            saved_path = p
            break

        if not saved_path or not saved_path.exists():
            document_repo.update_status(
                document_id,
                DocumentStatus.FAILED,
                error_message="Không tìm thấy file nguồn trên máy chủ.",
            )
            raise HTTPException(status_code=500, detail="File nguồn đã bị xóa hoặc di chuyển.")

        try:
            # Chọn extractor thích hợp
            ctx = doc.context or ReportContextCreate()
            if doc.file_type in (FileType.XLSX, FileType.XLS, FileType.CSV):
                tables = self.excel_extractor.extract(saved_path, ctx)
            elif doc.file_type == FileType.PDF:
                tables = self.pdf_extractor.extract(saved_path, ctx)
            else:
                tables = []

            # Tập hợp các giá trị và kiểm tra quy tắc kế toán
            all_values: list[ExtractedValue] = []
            for t in tables:
                all_values.extend(t.values)

            issues, validated_values = validate_accounting_rules(all_values)

            # Cập nhật lại các bảng với giá trị đã được validate
            val_map = {v.id: v for v in validated_values}
            for t in tables:
                t.values = [val_map.get(v.id, v) for v in t.values]

            document_repo.save_tables(document_id, tables)
            document_repo.update_status(document_id, DocumentStatus.COMPLETED, issues=issues)

            return self.get_document_detail(document_id)

        except Exception as e:  # noqa: BLE001
            document_repo.update_status(
                document_id, DocumentStatus.FAILED, error_message=str(e)
            )
            raise HTTPException(
                status_code=500, detail=f"Lỗi trong quá trình trích xuất tài liệu: {e!s}"
            )

    def get_document_detail(self, document_id: str) -> DocumentDetailResponse:
        doc = document_repo.get_document(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu.")

        tables = document_repo.get_tables(document_id)
        all_vals = [v for t in tables for v in t.values]
        total_metrics = len(all_vals)
        avg_conf = (
            sum(v.confidence_score for v in all_vals) / total_metrics
            if total_metrics > 0
            else 0.0
        )

        return DocumentDetailResponse(
            **doc.model_dump(),
            tables=tables,
            total_metrics_extracted=total_metrics,
            average_confidence=round(avg_conf, 2),
        )

    def update_value(
        self, document_id: str, value_id: str, update_req: ValueUpdateRequest, user_id: str = "reviewer"
    ) -> ExtractedValue:
        doc = document_repo.get_document(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu.")

        # Tìm giá trị trước khi cập nhật
        tables = document_repo.get_tables(document_id)
        target_val = None
        for t in tables:
            for v in t.values:
                if v.id == value_id:
                    target_val = v
                    break

        if not target_val:
            raise HTTPException(status_code=404, detail="Không tìm thấy chỉ tiêu cần sửa.")

        old_val = target_val.normalized_value
        updated = document_repo.update_value(
            document_id,
            value_id,
            update_req.normalized_value,
            update_req.standard_code,
            update_req.review_status.value,
        )

        # Ghi log kiểm tra
        document_repo.add_audit_log(
            AuditLog(
                id=f"log_{uuid.uuid4().hex[:8]}",
                document_id=document_id,
                value_id=value_id,
                action="MANUAL_EDIT" if update_req.normalized_value != old_val else "REVIEW_STATUS_UPDATE",
                user_id=user_id,
                before_value=old_val,
                after_value=update_req.normalized_value,
            )
        )

        return updated or target_val

    def export_document_data(self, document_id: str, export_format: str = "json") -> dict:
        detail = self.get_document_detail(document_id)
        if export_format.lower() == "json":
            return detail.model_dump()

        # Trả về bảng tổng hợp phẳng (flat rows) cho CSV/Excel
        flat_rows = []
        for table in detail.tables:
            for val in table.values:
                flat_rows.append(
                    {
                        "Ma_Chi_Tieu": val.standard_code,
                        "Ten_Goc": val.raw_metric_name,
                        "Gia_Tri_Goc": val.raw_value,
                        "Gia_Tri_Chuan_Hoa": val.normalized_value,
                        "Don_Vi": val.unit,
                        "Ky": val.period,
                        "Do_Tin_Cay": val.confidence_score,
                        "Trang_Thai_Ra_Soat": val.review_status,
                        "Vi_Tri_Nguon": val.lineage.cell_or_coordinates if val.lineage else "",
                    }
                )

        return {
            "document_id": document_id,
            "file_name": detail.file_name,
            "format": export_format,
            "rows": flat_rows,
        }


document_service = DocumentService()
