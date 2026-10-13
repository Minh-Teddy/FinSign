import threading

from app.modules.documents.schemas import (
    AuditLog,
    DocumentResponse,
    DocumentStatus,
    ExtractedTable,
    ExtractedValue,
    ValidationIssue,
)


class DocumentRepository:
    """Kho lưu trữ tài liệu và kết quả trích xuất."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._documents: dict[str, DocumentResponse] = {}
        self._tables: dict[str, list[ExtractedTable]] = {}  # document_id -> list[ExtractedTable]
        self._audit_logs: list[AuditLog] = []

    def save_document(self, doc: DocumentResponse) -> DocumentResponse:
        with self._lock:
            self._documents[doc.id] = doc
        return doc

    def get_document(self, document_id: str) -> DocumentResponse | None:
        with self._lock:
            return self._documents.get(document_id)

    def find_by_hash(self, file_hash: str) -> DocumentResponse | None:
        with self._lock:
            for doc in self._documents.values():
                if doc.file_hash == file_hash:
                    return doc
        return None

    def update_status(
        self,
        document_id: str,
        status: DocumentStatus,
        issues: list[ValidationIssue] | None = None,
        error_message: str | None = None,
    ) -> DocumentResponse | None:
        with self._lock:
            doc = self._documents.get(document_id)
            if not doc:
                return None
            doc.status = status
            if issues is not None:
                doc.validation_issues = issues
            if error_message is not None:
                doc.error_message = error_message
            return doc

    def save_tables(self, document_id: str, tables: list[ExtractedTable]) -> None:
        with self._lock:
            for table in tables:
                table.document_id = document_id
            self._tables[document_id] = tables

    def get_tables(self, document_id: str) -> list[ExtractedTable]:
        with self._lock:
            return self._tables.get(document_id, [])

    def update_value(
        self,
        document_id: str,
        value_id: str,
        new_val: float | None,
        std_code: str | None,
        review_status: str,
    ) -> ExtractedValue | None:
        with self._lock:
            tables = self._tables.get(document_id, [])
            for table in tables:
                for val in table.values:
                    if val.id == value_id:
                        if new_val is not None:
                            val.normalized_value = new_val
                        if std_code is not None:
                            val.standard_code = std_code
                        val.review_status = review_status
                        val.needs_review = False
                        return val
        return None

    def add_audit_log(self, log: AuditLog) -> None:
        with self._lock:
            self._audit_logs.append(log)

    def get_audit_logs(self, document_id: str) -> list[AuditLog]:
        with self._lock:
            return [l for l in self._audit_logs if l.document_id == document_id]


document_repo = DocumentRepository()
