from app.modules.documents.schemas import ExtractedValue, ValidationIssue


def validate_accounting_rules(values: list[ExtractedValue]) -> tuple[list[ValidationIssue], list[ExtractedValue]]:
    """
    Thực hiện kiểm tra các quy tắc kế toán cơ bản và tính điểm tin cậy:
    1. Tổng tài sản = Nợ phải trả + Vốn chủ sở hữu (hoặc Tổng nguồn vốn)
    2. Tài sản ngắn hạn + Tài sản dài hạn = Tổng tài sản
    3. Nợ phải trả + Vốn chủ sở hữu = Tổng nguồn vốn
    4. Doanh thu thuần - Giá vốn hàng bán = Lợi nhuận gộp
    """
    issues: list[ValidationIssue] = []

    # Tạo map mã chỉ tiêu -> giá trị số đã chuẩn hóa
    metrics_map: dict[str, float] = {}
    for val in values:
        if val.standard_code != "UNMAPPED" and val.normalized_value is not None:
            metrics_map[val.standard_code] = val.normalized_value

    def check_equality(
        rule_name: str,
        left_val: float | None,
        right_val: float | None,
        description: str,
        tolerance: float = 1.0,
    ) -> None:
        if left_val is None or right_val is None:
            return
        diff = abs(left_val - right_val)
        if diff > tolerance:
            issues.append(
                ValidationIssue(
                    rule_name=rule_name,
                    message=f"{description}. Chênh lệch: {diff:,.2f}",
                    severity="ERROR" if diff > 1000 else "WARNING",
                    difference=diff,
                )
            )

    # 1. Bảng cân đối: Tổng tài sản = Nợ + Vốn CSH
    total_assets = metrics_map.get("TOTAL_ASSETS")
    liabilities = metrics_map.get("LIABILITIES")
    equity = metrics_map.get("EQUITY")
    total_resources = metrics_map.get("TOTAL_RESOURCES")

    if total_assets is not None and liabilities is not None and equity is not None:
        check_equality(
            "BALANCE_SHEET_EQUATION",
            total_assets,
            liabilities + equity,
            "Tổng tài sản không bằng (Nợ phải trả + Vốn chủ sở hữu)",
        )

    if total_assets is not None and total_resources is not None:
        check_equality(
            "TOTAL_ASSETS_VS_RESOURCES",
            total_assets,
            total_resources,
            "Tổng tài sản không bằng Tổng nguồn vốn",
        )

    # 2. Tài sản ngắn hạn + dài hạn = Tổng tài sản
    current_assets = metrics_map.get("CURRENT_ASSETS")
    non_current_assets = metrics_map.get("NON_CURRENT_ASSETS")
    if total_assets is not None and current_assets is not None and non_current_assets is not None:
        check_equality(
            "ASSETS_SUM_CHECK",
            total_assets,
            current_assets + non_current_assets,
            "Tài sản ngắn hạn + Tài sản dài hạn không khớp Tổng tài sản",
        )

    # 3. Doanh thu thuần - Giá vốn = Lợi nhuận gộp
    revenue = metrics_map.get("REVENUE")
    cogs = metrics_map.get("COGS")
    gross_profit = metrics_map.get("GROSS_PROFIT")
    if revenue is not None and cogs is not None and gross_profit is not None:
        check_equality(
            "GROSS_PROFIT_CHECK",
            gross_profit,
            revenue - cogs,
            "Doanh thu thuần trừ Giá vốn không bằng Lợi nhuận gộp",
        )

    # Đánh giá lại độ tin cậy và gắn cờ rà soát
    has_critical_error = any(issue.severity == "ERROR" for issue in issues)

    for val in values:
        score = val.confidence_score
        # Nếu chưa khớp chỉ tiêu chuẩn
        if val.standard_code == "UNMAPPED":
            score = min(score, 0.6)
            val.needs_review = True
        # Nếu dính lỗi kế toán lớn
        elif has_critical_error:
            score = max(score - 0.2, 0.5)
            val.needs_review = True
        elif score < 0.8:
            val.needs_review = True

        val.confidence_score = round(score, 2)

    return issues, values
