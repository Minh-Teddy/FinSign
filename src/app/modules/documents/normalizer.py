import re
import unicodedata

# Từ điển ánh xạ các chỉ tiêu tài chính chuẩn (VAS / IFRS)
STANDARD_METRICS_CATALOG: dict[str, list[str]] = {
    # --- Bảng cân đối kế toán ---
    "TOTAL_ASSETS": [
        "tong cong tai san", "tong tai san", "tong cong ts", "total assets"
    ],
    "CURRENT_ASSETS": [
        "tai san ngan han", "ts ngan han", "current assets"
    ],
    "NON_CURRENT_ASSETS": [
        "tai san dai han", "ts dai han", "non current assets", "non-current assets"
    ],
    "LIABILITIES": [
        "no phai tra", "tong no phai tra", "tong no", "liabilities", "total liabilities"
    ],
    "CURRENT_LIABILITIES": [
        "no ngan han", "current liabilities"
    ],
    "NON_CURRENT_LIABILITIES": [
        "no dai han", "non current liabilities", "non-current liabilities"
    ],
    "EQUITY": [
        "von chu so huu", "tong von chu so huu", "equity", "owner equity", "shareholders equity"
    ],
    "TOTAL_RESOURCES": [
        "tong cong nguon von", "tong nguon von", "total equity and liabilities"
    ],

    # --- Báo cáo kết quả hoạt động kinh doanh ---
    "REVENUE": [
        "doanh thu thuan", "doanh thu ban hang va cung cap dich vu",
        "doanh thu thuan ve ban hang va cung cap dich vu", "net revenue", "revenue"
    ],
    "COGS": [
        "gia von hang ban", "cost of goods sold", "cogs"
    ],
    "GROSS_PROFIT": [
        "loi nhuan gop", "loi nhuan gop ve ban hang va cung cap dich vu", "gross profit"
    ],
    "FINANCIAL_INCOME": [
        "doanh thu hoat dong tai chinh", "financial income"
    ],
    "FINANCIAL_EXPENSES": [
        "chi phi tai chinh", "financial expenses"
    ],
    "OPERATING_PROFIT": [
        "loi nhuan thuan tu hoat dong kinh doanh", "operating profit"
    ],
    "PROFIT_BEFORE_TAX": [
        "tong loi nhuan ke toan truoc thue", "loi nhuan truoc thue", "profit before tax"
    ],
    "PROFIT_AFTER_TAX": [
        "loi nhuan sau thue thu nhap doanh nghiep", "loi nhuan sau thue",
        "tong loi nhuan sau thue", "net profit after tax", "profit after tax"
    ],

    # --- Báo cáo lưu chuyển tiền tệ ---
    "NET_CASH_OPERATING": [
        "luu chuyen tien thuan tu hoat dong kinh doanh", "net cash flows from operating activities"
    ],
    "NET_CASH_INVESTING": [
        "luu chuyen tien thuan tu hoat dong dau tu", "net cash flows from investing activities"
    ],
    "NET_CASH_FINANCING": [
        "luu chuyen tien thuan tu hoat dong tai chinh", "net cash flows from financing activities"
    ],
    "CASH_END_PERIOD": [
        "tien va tuong duong tien cuoi ky", "cash and cash equivalents at end of period"
    ],
}

UNIT_MULTIPLIERS: dict[str, float] = {
    "dong": 1.0,
    "vnd": 1.0,
    "nghin": 1_000.0,
    "ngan": 1_000.0,
    "trieu": 1_000_000.0,
    "ty": 1_000_000_000.0,
    "usd": 1.0,
}


def remove_vietnamese_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt để so khớp xấp xỉ không dấu."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D")
    return text.lower().strip()


def parse_numeric_value(raw_val: str | float | None) -> float | None:
    """
    Chuẩn hóa số liệu từ chuỗi thô:
    - 1.234.567,89 (chuẩn VN)
    - 1,234,567.89 (chuẩn quốc tế)
    - (123.456) -> số âm -123456
    - '-' hoặc '—' -> 0.0
    """
    if raw_val is None:
        return None
    if isinstance(raw_val, (int, float)):
        return float(raw_val)

    s = str(raw_val).strip()
    if not s or s in ("-", "—", "–", "n/a", "N/A"):
        return 0.0

    is_negative = False
    # Kiểm tra số âm dạng (123.456) hoặc -123.456
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1].strip()
    elif s.startswith("-"):
        is_negative = True
        s = s[1:].strip()

    # Loại bỏ ký tự tiền tệ hoặc khoảng trắng
    s = re.sub(r"[^\d,\.]", "", s)
    if not s:
        return None

    # Phát hiện dấu phân cách thập phân:
    # Trường hợp 1: Có cả '.' và ','
    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):
            # Kiểu VN: 1.234.567,89
            s = s.replace(".", "").replace(",", ".")
        else:
            # Kiểu US: 1,234,567.89
            s = s.replace(",", "")
    elif "," in s and "." not in s:
        # Chỉ có dấu phẩy: kiểm tra xem là phân cách hàng nghìn hay thập phân
        comma_index = s.rfind(",")
        digits_after = len(s) - 1 - comma_index
        if digits_after == 3 and s.count(",") > 1:
            # 1,234,567 -> hàng nghìn US
            s = s.replace(",", "")
        elif digits_after in (1, 2):
            # 1234,56 -> thập phân VN
            s = s.replace(",", ".")
        elif digits_after == 3 and len(s[:comma_index]) <= 3:
            # 1,000 -> có thể là 1 nghìn
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    elif "." in s and "," not in s:
        # Chỉ có dấu chấm: kiểm tra xem là phân cách hàng nghìn hay thập phân
        dot_index = s.rfind(".")
        digits_after = len(s) - 1 - dot_index
        if digits_after == 3 and (s.count(".") > 1 or len(s[:dot_index]) <= 3):
            # 1.234.567 hoặc 1.000 -> hàng nghìn VN
            s = s.replace(".", "")

    try:
        val = float(s)
        return -val if is_negative else val
    except ValueError:
        return None


def match_standard_metric(raw_name: str) -> tuple[str, float]:
    """
    Ánh xạ tên chỉ tiêu thô về mã chuẩn trong STANDARD_METRICS_CATALOG.
    Trả về (mã_chuẩn, độ_tin_cậy: 0.0 -> 1.0).
    """
    cleaned = remove_vietnamese_accents(raw_name)
    # Loại bỏ tiền tố số/mã chỉ mục (ví dụ: "1.", "1.1", "A.", "I.", "a)")
    cleaned = re.sub(r"^([0-9]+(\.[0-9]+)*|[ivx]+|[a-z])[\.\-\)\s]+\s*", "", cleaned).strip()

    best_code = "UNMAPPED"
    best_score = 0.0

    for code, synonyms in STANDARD_METRICS_CATALOG.items():
        for syn in synonyms:
            if syn == cleaned:
                return code, 1.0
            if syn in cleaned:
                score = len(syn) / max(len(cleaned), 1)
                if score > best_score:
                    best_score = max(score, 0.85)
                    best_code = code

    if best_score >= 0.7:
        return best_code, best_score
    return "UNMAPPED", 0.0


def extract_unit_multiplier(text: str) -> float:
    """Phát hiện đơn vị tính từ dòng tiêu đề/văn bản."""
    clean = remove_vietnamese_accents(text)
    for unit_key, multiplier in UNIT_MULTIPLIERS.items():
        if unit_key in clean:
            return multiplier
    return 1.0
