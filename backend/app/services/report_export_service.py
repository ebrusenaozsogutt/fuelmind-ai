"""Memory-only PDF and CSV renderers over ReportService result sets."""
from __future__ import annotations

import csv
from datetime import date, datetime
from dataclasses import dataclass
from decimal import Decimal
from html import escape
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, A4, landscape, portrait
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


PDF_HEADERS = {
    "id": "ID", "sale_id": "Satış ID", "timestamp": "Tarih / Saat",
    "station": "İstasyon", "station_id": "İstasyon ID", "pump": "Pompa",
    "pump_id": "Pompa ID", "nozzle": "Tabanca", "nozzle_id": "Tabanca ID",
    "attendant": "Pompacı", "attendant_id": "Pompacı ID", "shift": "Vardiya",
    "shift_id": "Vardiya ID", "fuel_type": "Ürün", "fuel_type_id": "Ürün ID",
    "liters": "Litre", "quantity_liters": "Litre", "start_totalizer": "Başlangıç Totalizer",
    "end_totalizer": "Bitiş Totalizer", "unit_price": "Birim Fiyat",
    "total_amount": "Tutar", "customer": "Müşteri", "customer_id": "Müşteri ID",
    "plate": "Plaka", "card": "Kart", "payment_type": "Ödeme", "sale_status": "Durum",
    "section": "Bölüm", "value": "Değer", "key": "Kırılım", "transaction_count": "İşlem Sayısı",
    "tank": "Tank", "tank_id": "Tank ID", "level_before": "Önceki Seviye",
    "level_after": "Sonraki Seviye", "supplier": "Tedarikçi", "source": "Kaynak",
    "status": "Durum", "probe": "Prob", "fuel_height_mm": "Yakıt Yüksekliği (mm)",
    "fuel_volume_liters": "Yakıt Hacmi (L)", "water_height_mm": "Su Yüksekliği (mm)",
    "temperature_celsius": "Sıcaklık (°C)", "quality_score": "Kalite Puanı",
    "quality_flags": "Kalite İşaretleri", "probe_status": "Prob Durumu", "price_id": "Fiyat ID",
    "old_price": "Eski Fiyat", "new_price": "Yeni Fiyat", "changed_by": "Değiştiren",
    "target_type": "Hedef Türü", "target_id": "Hedef ID", "fault_type": "Arıza Tipi",
    "fault_code": "Arıza Kodu", "cause": "Neden", "description": "Açıklama",
    "started_at": "Başlangıç", "detected_at": "Tespit", "resolved_at": "Çözüm",
    "duration_seconds": "Süre (sn)", "related_alarm_id": "İlgili Alarm ID",
    "resolution_note": "Çözüm Notu", "resolved_by": "Çözen", "vehicle_id": "Araç ID",
}

_NARROW_COLUMNS = frozenset({
    "id", "sale_id", "station_id", "pump_id", "nozzle_id", "attendant_id", "shift_id",
    "fuel_type_id", "customer_id", "vehicle_id", "tank_id", "price_id", "target_id",
    "liters", "quantity_liters", "unit_price", "total_amount", "old_price", "new_price",
    "transaction_count", "duration_seconds", "status", "sale_status", "payment_type", "source",
})
_WIDE_COLUMNS = frozenset({
    "timestamp", "started_at", "detected_at", "resolved_at", "description", "cause",
    "resolution_note", "quality_flags", "supplier", "customer", "attendant", "station",
})
_THREE_DECIMAL_COLUMNS = frozenset({
    "liters", "quantity_liters", "start_totalizer", "end_totalizer", "level_before",
    "level_after", "fuel_volume_liters", "fuel_height_mm", "water_height_mm",
})
_TWO_DECIMAL_COLUMNS = frozenset({"total_amount", "old_price", "new_price", "temperature_celsius", "quality_score"})
_SALES_MINIMUM_WIDTHS = {
    "sale_id": 34.0, "timestamp": 80.0, "station": 68.0, "pump": 76.0, "nozzle": 58.0,
    "attendant": 70.0, "shift": 50.0, "fuel_type": 54.0, "liters": 35.0,
    "start_totalizer": 50.0, "end_totalizer": 50.0, "unit_price": 47.0,
    "total_amount": 48.0, "customer": 75.0, "plate": 53.0, "card": 45.0,
    "payment_type": 46.0, "sale_status": 55.0,
}


@dataclass(frozen=True)
class PdfTableLayout:
    pagesize: tuple[float, float]
    left_margin: float
    right_margin: float
    top_margin: float
    bottom_margin: float
    column_widths: tuple[float, ...]
    font_size: float

    @property
    def usable_width(self) -> float:
        return self.pagesize[0] - self.left_margin - self.right_margin

    @property
    def table_width(self) -> float:
        return sum(self.column_widths)


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
        columns = self._columns(rows)
        layout = self._table_layout(report_type, columns)
        doc = SimpleDocTemplate(
            buffer,
            pagesize=layout.pagesize,
            leftMargin=layout.left_margin,
            rightMargin=layout.right_margin,
            topMargin=layout.top_margin,
            bottomMargin=layout.bottom_margin,
        )
        title_style = styles["Title"].clone("ReportTitle", fontName=font, fontSize=15, leading=18, spaceAfter=2)
        subtitle_style = styles["Heading2"].clone("ReportSubtitle", fontName=font, fontSize=11, leading=13, spaceAfter=3)
        meta_style = styles["Normal"].clone("ReportMeta", fontName=font, fontSize=7.5, leading=9)
        header_style = styles["BodyText"].clone("ReportHeader", fontName=font, fontSize=layout.font_size, leading=layout.font_size + 1, alignment=1, splitLongWords=0)
        cell_style = styles["BodyText"].clone("ReportCell", fontName=font, fontSize=layout.font_size, leading=layout.font_size + 1, splitLongWords=0)
        story = [
            Paragraph("FuelMind AI", title_style),
            Paragraph(escape(title), subtitle_style),
            Paragraph(f"Oluşturulma: {utc_now().strftime('%d.%m.%Y %H:%M')}", meta_style),
            Paragraph(f"Filtreler: {escape(self._filter_text(filters))}", meta_style),
            Spacer(1, 8),
        ]
        data = [[Paragraph(self._header(key), header_style) for key in columns]]
        for row in rows:
            data.append([Paragraph(self._paragraph_text(self._pdf_text(key, row.get(key))), cell_style) for key in columns])
        if len(data) == 1:
            data.append([Paragraph("Kayıt bulunamadı.", cell_style)] + [""] * max(0, len(columns) - 1))
        table = Table(data, repeatRows=1, colWidths=layout.column_widths, hAlign="LEFT", splitByRow=1)
        table_style = [
            ("FONTNAME", (0, 0), (-1, -1), font),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE6F1")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#18344F")),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#AAB7C4")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, 0), 4),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
            ("TOPPADDING", (0, 1), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 2),
        ]
        for index, column in enumerate(columns):
            if column in _NARROW_COLUMNS or column in _THREE_DECIMAL_COLUMNS or column in _TWO_DECIMAL_COLUMNS:
                table_style.append(("ALIGN", (index, 1), (index, -1), "RIGHT"))
        table.setStyle(TableStyle(table_style))
        story.append(table)
        doc.build(story, onFirstPage=lambda canvas, document: self._footer(canvas, document, title, font), onLaterPages=lambda canvas, document: self._footer(canvas, document, title, font))
        return buffer.getvalue()

    @staticmethod
    def _table_layout(report_type: str, columns: list[str]) -> PdfTableLayout:
        column_count = len(columns)
        if report_type == "sales" or column_count >= 15:
            pagesize = landscape(A3)
            margins = (26.0, 26.0, 26.0, 28.0)
            font_size = 6.7
        elif column_count >= 8:
            pagesize = landscape(A4)
            margins = (22.0, 22.0, 24.0, 26.0)
            font_size = 7.2
        else:
            pagesize = portrait(A4)
            margins = (28.0, 28.0, 24.0, 26.0)
            font_size = 8.2
        left, right, top, bottom = margins
        usable_width = pagesize[0] - left - right
        weights = [2.0 if key in _WIDE_COLUMNS else 0.72 if key in _NARROW_COLUMNS else 1.0 for key in columns]
        minimums = [34.0 if key in _NARROW_COLUMNS else 48.0 if key not in _WIDE_COLUMNS else 70.0 for key in columns]
        if report_type == "sales":
            minimums = [_SALES_MINIMUM_WIDTHS.get(key, value) for key, value in zip(columns, minimums, strict=True)]
        minimum_total = sum(minimums)
        if minimum_total > usable_width:
            # Very wide reports use A3, but retain a legible lower bound even for unknown fields.
            minimums = [max(26.0, value * usable_width / minimum_total) for value in minimums]
        remaining = max(0.0, usable_width - sum(minimums))
        weight_total = sum(weights) or 1.0
        widths = tuple(minimum + remaining * weight / weight_total for minimum, weight in zip(minimums, weights, strict=True))
        layout = PdfTableLayout(pagesize, left, right, top, bottom, widths, font_size)
        assert layout.table_width <= layout.usable_width + 0.01
        return layout

    @staticmethod
    def _header(column: str) -> str:
        label = PDF_HEADERS.get(column, column.replace("_", " ").title())
        return escape(label).replace(" Totalizer", "<br/>Totalizer").replace(" / ", " /<br/>")

    @staticmethod
    def _paragraph_text(value: str) -> str:
        # Keep normal identifiers such as PUMP_GASOLINE_01 intact; only long prose is
        # broken at spaces, not in the middle of identifiers.
        return escape(value[:320]).replace("\n", "<br/>")

    @staticmethod
    def _pdf_text(column: str, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.strftime("%d.%m.%Y %H:%M")
        if isinstance(value, date):
            return value.strftime("%d.%m.%Y")
        if isinstance(value, Decimal):
            value = float(value)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if column in _THREE_DECIMAL_COLUMNS:
                return f"{value:,.3f}".replace(",", "X").replace(".", ",").replace("X", ".")
            if column == "unit_price":
                return f"{value:,.4f}".replace(",", "X").replace(".", ",").replace("X", ".")
            if column in _TWO_DECIMAL_COLUMNS:
                return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return ReportExportService._text(value)

    @staticmethod
    def _footer(canvas: Any, document: Any, title: str, font: str) -> None:
        canvas.saveState()
        canvas.setFont(font, 7)
        canvas.setFillColor(colors.HexColor("#637381"))
        canvas.drawString(document.leftMargin, 14, f"FuelMind AI | {title}")
        canvas.drawRightString(document.pagesize[0] - document.rightMargin, 14, f"Sayfa {canvas.getPageNumber()}")
        canvas.restoreState()

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
