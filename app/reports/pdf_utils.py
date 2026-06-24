from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak
from reportlab.platypus import Paragraph
from reportlab.platypus import SimpleDocTemplate
from reportlab.platypus import Spacer
from reportlab.platypus import Table
from reportlab.platypus import TableStyle

from app.reports.report_utils import make_read_only
from app.reports.report_utils import make_writable


styles = getSampleStyleSheet()


def text(value: object) -> Paragraph:
    clean_value = str(value or "")
    clean_value = clean_value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    clean_value = clean_value.replace("\n", "<br/>")
    return Paragraph(clean_value, styles["BodyText"])


def heading(value: str) -> Paragraph:
    return Paragraph(str(value), styles["Heading1"])


def subheading(value: str) -> Paragraph:
    return Paragraph(str(value), styles["Heading2"])


def build_table(
    headers: list[str],
    rows: list[list[object]],
    column_widths: list[float] | None = None,
) -> Table:
    data = [[text(header) for header in headers]]
    data.extend([[text(value) for value in row] for row in rows])

    table = Table(data, colWidths=column_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9EAF7")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#9CA3AF")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def write_pdf(
    output_path: Path,
    story: list,
    use_landscape: bool = False,
) -> Path:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    make_writable(output_path)

    page_size = landscape(letter) if use_landscape else letter
    document = SimpleDocTemplate(
        str(output_path),
        pagesize=page_size,
        rightMargin=0.45 * inch,
        leftMargin=0.45 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.45 * inch,
    )
    document.build(story)
    make_read_only(output_path)
    return output_path


def spacer(height: float = 0.15) -> Spacer:
    return Spacer(1, height * inch)


def page_break() -> PageBreak:
    return PageBreak()
