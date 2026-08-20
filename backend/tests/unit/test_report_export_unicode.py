from app.schemas.report import ReportFilters
from app.services.report_export_service import ReportExportService


class _Reports:
    def sales(self, _filters, _skip, _limit):
        return [{"station": "İstanbul Şube", "attendant": "Çağrı Öztürk", "shift": "Öğle Vardiyası"}]


def test_pdf_export_embeds_a_unicode_font_for_turkish_report_content() -> None:
    pdf = ReportExportService(_Reports()).pdf("sales", ReportFilters())

    assert pdf.startswith(b"%PDF-")
    assert ReportExportService._font() != "Helvetica"
    assert b"/ToUnicode" in pdf
