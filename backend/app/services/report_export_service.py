"""Memory-only PDF and CSV renderers over ReportService result sets."""
from __future__ import annotations

import csv
from datetime import date, datetime
from html import escape
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.schemas.report import ReportFilters
from app.services.report_service import ReportService
from app.utils.datetime_utils import utc_now


REPORTS = {
    "end-of-day": ("Gün Sonu Raporu", "end_of_day"),
    "sales": ("Satış Raporu", "sales"),
    "attendants": ("Pompacı / Vardiya Raporu", "attendants"),
    "deliveries": ("Tank Dolum Raporu", "deliveries"),
    "tank-measurements": ("Tank Ölçüm Raporu", "tank_measurements"),
    "price-changes": ("Ürün Fiyat Değişim Raporu", "price_changes"),
    "faults": ("Arıza Raporu", "faults"),
    "customer-sales": ("Müşteri / Araç Satış Raporu", "customer_sales"),
}


class ReportExportService:
    def __init__(self, reports: ReportService) -> None:
        self.reports = reports

    def dataset(self, report_type: str, filters: ReportFilters) -> tuple[str, list[dict[str, Any]]]:
        try:
            title, method = REPORTS[report_type]
        except KeyError as exc:
            raise ValueError("Unsupported report type.") from exc
        result = getattr(self.reports, method)(filters, 0, 5000) if method in {"sales", "deliveries", "tank_measurements", "price_changes", "faults"} else getattr(self.reports, method)(filters)
        if isinstance(result, dict):
            rows = [{"section": key, "value": value} for key, value in result.items() if not isinstance(value, list)]
            for key, values in result.items():
                if isinstance(values, list):
                    rows.extend({"section": key, **item} for item in values)
            return title, rows
        return title, result

    def csv(self, report_type: str, filters: ReportFilters) -> bytes:
        _, rows = self.dataset(report_type, filters)
        columns = self._columns(rows)
        buffer = StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: self._text(row.get(key)) for key in columns})
        return buffer.getvalue().encode("utf-8-sig")

    def pdf(self, report_type: str, filters: ReportFilters) -> bytes:
        title, rows = self.dataset(report_type, filters)
        buffer = BytesIO()
        font = self._font()
        styles = getSampleStyleSheet()
        for style in styles.byName.values():
            style.fontName = font
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)
        story = [Paragraph("FuelMind AI", styles["Title"]), Paragraph(escape(title), styles["Heading2"]), Paragraph(f"Oluşturulma: {utc_now().isoformat()}", styles["Normal"]), Paragraph(f"Filtreler: {escape(self._filter_text(filters))}", styles["Normal"]), Spacer(1, 10)]
        columns = self._columns(rows)
        data = [[Paragraph(escape(str(key)), styles["BodyText"]) for key in columns]]
        for row in rows:
            data.append([Paragraph(escape(self._text(row.get(key))[:160]), styles["BodyText"]) for key in columns])
        if len(data) == 1:
            data.append([Paragraph("Kayıt bulunamadı.", styles["BodyText"])] + [""] * max(0, len(columns) - 1))
        table = Table(data, repeatRows=1, colWidths=[max(55, 760 / max(1, len(columns)))] * len(columns))
        table.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), font), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE6F1")), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONTSIZE", (0, 0), (-1, -1), 7)]))
        story.append(table)
        doc.build(story)
        return buffer.getvalue()

    @staticmethod
    def _columns(rows: list[dict[str, Any]]) -> list[str]:
        return list(dict.fromkeys(key for row in rows for key in row)) or ["result"]
    @staticmethod
    def _text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, (list, dict)):
            return str(value)
        return str(getattr(value, "value", value))
    @staticmethod
    def _filter_text(filters: ReportFilters) -> str:
        return ", ".join(f"{key}={value}" for key, value in filters.model_dump(exclude_none=True).items()) or "Yok"
    @staticmethod
    def _font() -> str:
        # The old DejaVu path does not exist on normal Windows installations,
        # causing ReportLab to fall back to Helvetica and render Turkish glyphs
        # as boxes. Use system Unicode fonts available on supported runtimes.
        paths = (
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/segoeui.ttf"),
            Path("C:/Windows/Fonts/calibri.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
        )
        for path in paths:
            if not path.exists():
                continue
            font_name = f"FuelMindUnicode{path.stem}"
            if font_name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(font_name, str(path)))
            return font_name
        return "Helvetica"
