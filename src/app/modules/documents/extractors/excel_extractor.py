import csv
import uuid
from pathlib import Path

from app.modules.documents.extractors.base import BaseExtractor
from app.modules.documents.normalizer import (
    match_standard_metric,
    parse_numeric_value,
)
from app.modules.documents.schemas import (
    ExtractedTable,
    ExtractedValue,
    Lineage,
    ReportContextCreate,
)


class ExcelExtractor(BaseExtractor):
    """Bộ trích xuất dữ liệu tài chính từ Excel (.xlsx, .xls) và CSV."""

    def extract(self, file_path: Path, context: ReportContextCreate) -> list[ExtractedTable]:
        ext = file_path.suffix.lower()
        if ext == ".csv":
            return self._extract_csv(file_path, context)
        return self._extract_xlsx(file_path, context)

    def _extract_xlsx(self, file_path: Path, context: ReportContextCreate) -> list[ExtractedTable]:
        tables: list[ExtractedTable] = []
        try:
            import openpyxl

            wb = openpyxl.load_workbook(file_path, data_only=True)
            for sheet_name in wb.sheetnames:
                sheet = wb[sheet_name]
                table_id = f"table_{uuid.uuid4().hex[:8]}"
                extracted_values: list[ExtractedValue] = []

                # Đọc từng dòng để tìm chỉ tiêu tài chính
                for row_idx, row in enumerate(sheet.iter_rows(values_only=False), start=1):
                    row_vals = [cell.value for cell in row]
                    if not any(row_vals):
                        continue

                    # Tìm ô chứa tên chỉ tiêu (thường ở cột 0, 1 hoặc 2)
                    metric_name = None
                    metric_cell_coord = ""
                    num_val = None
                    num_cell_coord = ""
                    raw_num_str = ""

                    for col_idx, cell in enumerate(row, start=1):
                        val = cell.value
                        if val is None:
                            continue
                        str_val = str(val).strip()

                        # Nếu là văn bản dài > 2 ký tự và chưa có tên chỉ tiêu
                        if not metric_name and isinstance(val, str) and len(str_val) >= 3:
                            # Bỏ qua nếu dòng này là tiêu đề đơn thuần như "Thuyết minh", "Mã số"
                            if str_val.lower() not in ("stt", "ma so", "thuyet minh", "nam nay", "nam truoc"):
                                metric_name = str_val
                                metric_cell_coord = f"{sheet_name}!{cell.coordinate}"
                        elif metric_name and (isinstance(val, (int, float)) or (isinstance(val, str) and any(char.isdigit() for char in str_val))):
                            # Tìm giá trị số đầu tiên sau cột tên chỉ tiêu
                            parsed = parse_numeric_value(val)
                            if parsed is not None and num_val is None:
                                num_val = parsed
                                raw_num_str = str_val
                                num_cell_coord = f"{sheet_name}!{cell.coordinate}"

                    if metric_name and num_val is not None:
                        std_code, conf = match_standard_metric(metric_name)
                        multiplier = context.unit_multiplier or 1.0

                        extracted_values.append(
                            ExtractedValue(
                                id=f"val_{uuid.uuid4().hex[:8]}",
                                table_id=table_id,
                                standard_code=std_code,
                                raw_metric_name=metric_name,
                                raw_value=raw_num_str,
                                normalized_value=num_val * multiplier,
                                period=context.period,
                                unit=context.currency,
                                confidence_score=conf if std_code != "UNMAPPED" else 0.5,
                                needs_review=conf < 0.85,
                                lineage=Lineage(
                                    file_name=file_path.name,
                                    page_or_sheet=sheet_name,
                                    cell_or_coordinates=f"Metric: {metric_cell_coord}, Value: {num_cell_coord}",
                                    snippet=f"{metric_name}: {raw_num_str}",
                                ),
                            )
                        )

                if extracted_values:
                    tables.append(
                        ExtractedTable(
                            id=table_id,
                            document_id="",
                            page_or_sheet=sheet_name,
                            extraction_method="OPENPYXL_DATA_READER",
                            headers=["Chỉ tiêu", "Số liệu"],
                            values=extracted_values,
                        )
                    )
        except ImportError:
            # Fallback nếu openpyxl chưa được cài
            pass

        return tables

    def _extract_csv(self, file_path: Path, context: ReportContextCreate) -> list[ExtractedTable]:
        tables: list[ExtractedTable] = []
        table_id = f"table_{uuid.uuid4().hex[:8]}"
        extracted_values: list[ExtractedValue] = []

        try:
            with open(file_path, mode="r", encoding="utf-8-sig", errors="ignore") as f:
                reader = csv.reader(f)
                for row_idx, row in enumerate(reader, start=1):
                    if not row:
                        continue
                    metric_name = None
                    num_val = None
                    raw_num_str = ""

                    for col_idx, item in enumerate(row):
                        cleaned = item.strip()
                        if not metric_name and len(cleaned) >= 3 and not any(c.isdigit() for c in cleaned[:3]):
                            metric_name = cleaned
                        elif metric_name and num_val is None:
                            parsed = parse_numeric_value(cleaned)
                            if parsed is not None:
                                num_val = parsed
                                raw_num_str = cleaned

                    if metric_name and num_val is not None:
                        std_code, conf = match_standard_metric(metric_name)
                        extracted_values.append(
                            ExtractedValue(
                                id=f"val_{uuid.uuid4().hex[:8]}",
                                table_id=table_id,
                                standard_code=std_code,
                                raw_metric_name=metric_name,
                                raw_value=raw_num_str,
                                normalized_value=num_val * (context.unit_multiplier or 1.0),
                                period=context.period,
                                unit=context.currency,
                                confidence_score=conf if std_code != "UNMAPPED" else 0.5,
                                needs_review=conf < 0.85,
                                lineage=Lineage(
                                    file_name=file_path.name,
                                    page_or_sheet="CSV",
                                    cell_or_coordinates=f"Row {row_idx}",
                                    snippet=f"{metric_name}: {raw_num_str}",
                                ),
                            )
                        )

            if extracted_values:
                tables.append(
                    ExtractedTable(
                        id=table_id,
                        document_id="",
                        page_or_sheet="CSV",
                        extraction_method="CSV_READER",
                        headers=["Chỉ tiêu", "Số liệu"],
                        values=extracted_values,
                    )
                )
        except (csv.Error, OSError):
            return tables

        return tables
