from datetime import datetime, timezone
from app.schemas.report import ReportFilters
from app.services.report_export_service import REPORTS, ReportExportService


class _Reports:
    def sales(self, _filters, _skip, _limit):
        row = {
            "sale_id": 101, "timestamp": datetime(2026, 9, 6, 14, 28, 58, tzinfo=timezone.utc),
            "station": "Konya Merkez", "pump": "PUMP_GASOLINE_01", "nozzle": "NOZZLE_01",
            "attendant": "Çağrı Öztürk", "shift": "Öğle", "fuel_type": "Benzin",
            "liters": 42.125, "start_totalizer": 10450.125, "end_totalizer": 10492.250,
            "unit_price": 46.7891, "total_amount": 1971.88, "customer": "Konya Lojistik",
            "plate": "42 ABC 123", "card": "KART-001", "payment_type": "CARD", "sale_status": "COMPLETED",
        }
        return [row.copy() for _ in range(90)]

    def end_of_day(self, _filters):
        return {
            "transaction_count": 5527,
            "total_liters": 175107.209,
            "total_amount": 669933.38,
            "by_fuel_type": [{"key": "LPG", "transaction_count": 2075, "total_liters": 50406.329, "total_amount": 148392.17}],
            "by_pump": [{"key": "PUMP_GASOLINE_01", "transaction_count": 1937, "total_liters": 58434.182, "total_amount": 171007.99}],
            "by_customer": [{"key": None, "transaction_count": 5258, "total_liters": 165663.437, "total_amount": 650000.00}],
            "by_payment_type": [
                {"key": "CREDIT", "transaction_count": 100, "total_liters": 1000, "total_amount": 10000},
                {"key": None, "transaction_count": 2, "total_liters": 2, "total_amount": 20},
            ],
        }

    def attendants(self, _filters):
        return [{"attendant_name": "Çağrı Öztürk", "shift_name": "Öğle", "transaction_count": 2, "total_liters": 12.5, "total_amount": 500.25}]

    def deliveries(self, _filters, _skip, _limit):
        return [{"id": 1, "timestamp": datetime(2026, 9, 6, tzinfo=timezone.utc), "station": "Konya", "tank": "T-01", "quantity_liters": 1000.5, "supplier": "Tedarikçi A", "status": "COMPLETED"}]

    def tank_measurements(self, _filters, _skip, _limit):
        return [{"timestamp": datetime(2026, 9, 6, tzinfo=timezone.utc), "station": "Konya", "tank": "T-01", "probe": "P-01", "fuel_volume_liters": 550.5, "quality_score": 98.2}]

    def price_changes(self, _filters, _skip, _limit):
        return [{"price_id": 1, "timestamp": datetime(2026, 9, 6, tzinfo=timezone.utc), "station": "Konya", "fuel_type": "Benzin", "old_price": 45.0, "new_price": 46.5, "changed_by": "admin"}]

    def faults(self, _filters, _skip, _limit):
        return [{"id": 1, "station": "Konya", "fault_code": "PUMP_NOT_CONNECTED", "description": "Uzun açıklama metni", "cause": "Controlled acceptance check", "status": "OPEN"}]

    def customer_sales(self, _filters):
        return [{"customer_id": 1, "customer": "Konya Lojistik", "plate": "42 ABC 123", "transaction_count": 2, "total_liters": 12.5, "total_amount": 500.25}]


def test_pdf_layout_is_adaptive_localized_and_repeats_sales_headers() -> None:
    exporter = ReportExportService(_Reports())
    _, sales_rows = exporter.dataset("sales", ReportFilters())
    layout = exporter._table_layout("sales", exporter._columns(sales_rows))

    assert layout.pagesize[0] > layout.pagesize[1]
    assert layout.table_width <= layout.usable_width

    pdf = exporter.pdf("sales", ReportFilters())
    assert pdf.startswith(b"%PDF-")
    assert pdf.count(b"/Type /Page") >= 2
    assert exporter._header("sale_id") == "Satış ID"
    assert exporter._header("timestamp") == "Tarih /<br/>Saat"
    assert exporter._pdf_text("timestamp", sales_rows[0]["timestamp"]) == "06.09.2026 14:28"
    assert exporter._paragraph_text("PUMP_GASOLINE_01") == "PUMP_GASOLINE_01"


def test_all_report_pdf_exports_keep_json_and_csv_contracts_unchanged() -> None:
    exporter = ReportExportService(_Reports())

    for report_type in REPORTS:
        assert exporter.pdf(report_type, ReportFilters()).startswith(b"%PDF-")

    csv = exporter.csv("sales", ReportFilters()).decode("utf-8-sig")
    assert csv.startswith("sale_id,timestamp,station,pump")


def test_end_of_day_pdf_uses_localized_sections_without_changing_report_values() -> None:
    exporter = ReportExportService(_Reports())
    _, rows = exporter.dataset("end-of-day", ReportFilters())
    summary, groups = exporter._end_of_day_data(rows)

    assert summary == {"transaction_count": 5527, "total_liters": 175107.209, "total_amount": 669933.38}
    assert groups["by_fuel_type"][0]["total_amount"] == 148392.17
    assert groups["by_pump"][0]["key"] == "PUMP_GASOLINE_01"
    assert groups["by_customer"][0]["key"] is None
    assert groups["by_payment_type"][0]["key"] == "CREDIT"
    assert exporter._format_transaction_count(summary["transaction_count"]) == "5.527"
    assert exporter._format_liters(summary["total_liters"]) == "175.107,209 L"
    assert exporter._format_amount(summary["total_amount"]) == "669.933,38 TL"
    assert exporter._breakdown_label(groups["by_customer"][0]["key"], "Müşteri Tanımsız") == "Müşteri Tanımsız"
    assert exporter._breakdown_label(groups["by_payment_type"][1]["key"], "Ödeme Türü Tanımsız") == "Ödeme Türü Tanımsız"
    assert exporter.pdf("end-of-day", ReportFilters()).startswith(b"%PDF-")
    assert exporter.csv("end-of-day", ReportFilters()).decode("utf-8-sig").startswith(
        "section,value,key,transaction_count,total_liters,total_amount"
    )
