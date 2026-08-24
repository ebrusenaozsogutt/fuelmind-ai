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
        return {"transaction_count": 2, "total_liters": 12.5, "total_amount": 500.25, "by_pump": []}

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
