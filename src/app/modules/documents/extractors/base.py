from abc import ABC, abstractmethod
from pathlib import Path

from app.modules.documents.schemas import ExtractedTable, ReportContextCreate


class BaseExtractor(ABC):
    """Lớp cơ sở cho các bộ trích xuất định dạng tài liệu (Excel, PDF, v.v.)."""

    @abstractmethod
    def extract(self, file_path: Path, context: ReportContextCreate) -> list[ExtractedTable]:
        """
        Trích xuất các bảng dữ liệu và giá trị tài chính từ tập tin.
        """
