import uuid
from pathlib import Path

from app.modules.documents.extractors.base import BaseExtractor
from app.modules.documents.normalizer import match_standard_metric, parse_numeric_value
from app.modules.documents.schemas import (
    ExtractedTable,
    ExtractedValue,
    Lineage,
    ReportContextCreate,
)


class PdfExtractor(BaseExtractor):
    """Bộ trích xuất dữ liệu tài chính từ tập tin PDF (Text & Scan-ready)."""

    def extract(self, file_path: Path, context: ReportContextCreate) -> list[ExtractedTable]:
        tables: list[ExtractedTable] = []

        try:
            from pypdf import PdfReader

            reader = PdfReader(str(file_path))
            for page_idx, page in enumerate(reader.pages, start=1):
                text = page.extract_text()
                if not text:
                    continue

                table_id = f"table_{uuid.uuid4().hex[:8]}"
                extracted_values: list[ExtractedValue] = []

                # Tách văn bản theo từng dòng
                lines = text.split("\n")
                for line_idx, line in enumerate(lines, start=1):
                    line_str = line.strip()
                    if not line_str or len(line_str) < 5:
                        continue

                    # Tìm các nhóm số ở cuối dòng
                    # Ví dụ: "Tổng cộng tài sản 100 1.250.000.000 1.100.000.000"
                    tokens = line_str.split()
                    if len(tokens) < 2:
                        continue

                    # Lấy token cuối cùng thử parse số
                    last_token = tokens[-1]
                    parsed_num = parse_numeric_value(last_token)

                    if parsed_num is not None:
                        metric_tokens = tokens[:-1]
                        # Bỏ qua nếu token trước đó là mã số chỉ tiêu dạng số (ví dụ 100, 200, 300)
                        if len(metric_tokens) > 1 and metric_tokens[-1].isdigit():
                            metric_tokens = metric_tokens[:-1]

                        metric_name = " ".join(metric_tokens).strip()
                        if len(metric_name) >= 3 and not metric_name.isdigit():
                            std_code, conf = match_standard_metric(metric_name)
                            extracted_values.append(
                                ExtractedValue(
                                    id=f"val_{uuid.uuid4().hex[:8]}",
                                    table_id=table_id,
                                    standard_code=std_code,
                                    raw_metric_name=metric_name,
                                    raw_value=last_token,
                                    normalized_value=parsed_num * (context.unit_multiplier or 1.0),
                                    period=context.period,
                                    unit=context.currency,
                                    confidence_score=conf if std_code != "UNMAPPED" else 0.5,
                                    needs_review=conf < 0.85,
                                    lineage=Lineage(
                                        file_name=file_path.name,
                                        page_or_sheet=f"Page {page_idx}",
                                        cell_or_coordinates=f"Line {line_idx}",
                                        snippet=line_str,
                                    ),
                                )
                            )

                if extracted_values:
                    tables.append(
                        ExtractedTable(
                            id=table_id,
                            document_id="",
                            page_or_sheet=f"Page {page_idx}",
                            extraction_method="PYPDF_TEXT_EXTRACTOR",
                            headers=["Chỉ tiêu", "Số liệu"],
                            values=extracted_values,
                        )
                    )
        except ImportError:
            # Fallback nếu pypdf chưa cài
            pass

        return tables
