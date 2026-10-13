import io

from fastapi.testclient import TestClient

from app.main import app
from app.modules.documents.normalizer import (
    match_standard_metric,
    parse_numeric_value,
)
from app.modules.documents.schemas import ExtractedValue
from app.modules.documents.validator import validate_accounting_rules

client = TestClient(app)


def test_normalizer_number_formats():
    # Kiểu Việt Nam
    assert parse_numeric_value("1.234.567,89") == 1234567.89
    # Kiểu Quốc tế
    assert parse_numeric_value("1,234,567.89") == 1234567.89
    # Số âm trong ngoặc
    assert parse_numeric_value("(500.000)") == -500000.0
    # Ký hiệu gạch ngang
    assert parse_numeric_value("-") == 0.0
    assert parse_numeric_value("—") == 0.0


def test_normalizer_metric_matching():
    code, score = match_standard_metric("Tổng cộng tài sản")
    assert code == "TOTAL_ASSETS"
    assert score >= 0.85

    code, score = match_standard_metric("Doanh thu bán hàng và cung cấp dịch vụ")
    assert code == "REVENUE"
    assert score >= 0.85

    code, score = match_standard_metric("Lợi nhuận sau thuế TNDN")
    assert code == "PROFIT_AFTER_TAX"
    assert score >= 0.85


def test_validator_balance_equation():
    values = [
        ExtractedValue(
            id="v1",
            table_id="t1",
            standard_code="TOTAL_ASSETS",
            raw_metric_name="Tổng tài sản",
            raw_value="1000",
            normalized_value=1000.0,
        ),
        ExtractedValue(
            id="v2",
            table_id="t1",
            standard_code="LIABILITIES",
            raw_metric_name="Nợ phải trả",
            raw_value="400",
            normalized_value=400.0,
        ),
        ExtractedValue(
            id="v3",
            table_id="t1",
            standard_code="EQUITY",
            raw_metric_name="Vốn chủ sở hữu",
            raw_value="600",
            normalized_value=600.0,
        ),
    ]
    issues, validated = validate_accounting_rules(values)
    assert len(issues) == 0
    assert all(not v.needs_review for v in validated)


def test_validator_detects_imbalance():
    values = [
        ExtractedValue(
            id="v1",
            table_id="t1",
            standard_code="TOTAL_ASSETS",
            raw_metric_name="Tổng tài sản",
            raw_value="1000",
            normalized_value=1000.0,
        ),
        ExtractedValue(
            id="v2",
            table_id="t1",
            standard_code="LIABILITIES",
            raw_metric_name="Nợ phải trả",
            raw_value="400",
            normalized_value=400.0,
        ),
        ExtractedValue(
            id="v3",
            table_id="t1",
            standard_code="EQUITY",
            raw_metric_name="Vốn chủ sở hữu",
            raw_value="500",  # Lệch 100
            normalized_value=500.0,
        ),
    ]
    issues, _ = validate_accounting_rules(values)
    assert len(issues) > 0
    assert any(issue.rule_name == "BALANCE_SHEET_EQUATION" for issue in issues)


def test_document_upload_and_extraction_workflow():
    # Giả lập file CSV báo cáo tài chính
    csv_content = (
        "Chi tieu,So tien\n"
        "Tong cong tai san,1.000.000.000\n"
        "Tai san ngan han,600.000.000\n"
        "Tai san dai han,400.000.000\n"
        "No phai tra,400.000.000\n"
        "Von chu so huu,600.000.000\n"
    )
    file_bytes = io.BytesIO(csv_content.encode("utf-8"))

    # 1. Upload
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("bctc.csv", file_bytes, "text/csv")},
        data={
            "company_name": "Công ty Cổ phần Mẫu",
            "report_type": "BALANCE_SHEET",
            "period": "2024",
            "currency": "VND",
        },
    )
    assert response.status_code == 201
    doc_data = response.json()
    doc_id = doc_data["id"]
    assert doc_data["file_name"] == "bctc.csv"

    # 2. Process
    proc_res = client.post(f"/api/v1/documents/{doc_id}/process")
    assert proc_res.status_code == 200
    proc_data = proc_res.json()
    assert proc_data["status"] == "COMPLETED"
    assert len(proc_data["tables"]) > 0
    assert proc_data["total_metrics_extracted"] > 0

    # 3. Get Detail
    get_res = client.get(f"/api/v1/documents/{doc_id}")
    assert get_res.status_code == 200

    # 4. Export
    export_res = client.get(f"/api/v1/documents/{doc_id}/export?format=table")
    assert export_res.status_code == 200
    assert len(export_res.json()["rows"]) > 0
