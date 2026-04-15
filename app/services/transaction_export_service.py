"""Transaction export service — issue #1022.

Generates CSV and PDF exports for a user's transactions.
Both formats respect the same filters (date range, type, status).
Export is gated behind the ``export_pdf`` entitlement (Premium plan).

Limits
------
- Maximum 10 000 transactions per export to avoid memory / timeout issues.
- Callers receive a structured ``ExportResult`` so the controller can set
  appropriate headers without coupling to the generation logic.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from app.models.transaction import Transaction, TransactionStatus, TransactionType

if TYPE_CHECKING:
    from uuid import UUID

EXPORT_LIMIT = 10_000
_DATE_FMT = "%d/%m/%Y"
_CSV_COLUMNS = ["data", "tipo", "titulo", "valor", "status", "descricao"]


@dataclass(frozen=True)
class ExportResult:
    content: bytes
    content_type: str
    filename: str


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


def _build_export_query(
    *,
    user_id: "UUID",
    start_date: date | None,
    end_date: date | None,
    tx_type: TransactionType | None,
    status: TransactionStatus | None,
) -> list[Transaction]:
    query = Transaction.query.filter_by(user_id=user_id, deleted=False)

    if start_date is not None:
        query = query.filter(Transaction.due_date >= start_date)
    if end_date is not None:
        query = query.filter(Transaction.due_date <= end_date)
    if tx_type is not None:
        query = query.filter(Transaction.type == tx_type)
    if status is not None:
        query = query.filter(Transaction.status == status)

    results: list[Transaction] = (
        query.order_by(Transaction.due_date.asc(), Transaction.created_at.asc())
        .limit(EXPORT_LIMIT)
        .all()
    )
    return results


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def _build_csv_rows(transactions: list[Transaction]) -> list[list[str]]:
    rows: list[list[str]] = []
    for tx in transactions:
        rows.append(
            [
                tx.due_date.strftime(_DATE_FMT) if tx.due_date else "",
                tx.type.value if tx.type else "",
                tx.title or "",
                str(Decimal(str(tx.amount)).quantize(Decimal("0.01"))),
                tx.status.value if tx.status else "",
                tx.description or "",
            ]
        )
    return rows


def generate_csv_export(
    *,
    user_id: "UUID",
    start_date: date | None = None,
    end_date: date | None = None,
    tx_type: TransactionType | None = None,
    status: TransactionStatus | None = None,
    month_label: str = "",
) -> ExportResult:
    transactions = _build_export_query(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        tx_type=tx_type,
        status=status,
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_CSV_COLUMNS)
    writer.writerows(_build_csv_rows(transactions))

    filename = f"auraxis_transactions_{month_label or 'export'}.csv"
    return ExportResult(
        content=buf.getvalue().encode("utf-8-sig"),  # BOM for Excel compat
        content_type="text/csv; charset=utf-8",
        filename=filename,
    )


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

_LABEL_MAP: dict[str, str] = {
    "income": "Receita",
    "expense": "Despesa",
    "paid": "Pago",
    "pending": "Pendente",
    "cancelled": "Cancelado",
    "postponed": "Adiado",
    "overdue": "Vencido",
}


def generate_pdf_export(
    *,
    user_id: "UUID",
    start_date: date | None = None,
    end_date: date | None = None,
    tx_type: TransactionType | None = None,
    status: TransactionStatus | None = None,
    month_label: str = "",
) -> ExportResult:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    transactions = _build_export_query(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        tx_type=tx_type,
        status=status,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    elements = []

    # Header
    title_text = "Auraxis — Extrato de Transações"
    if month_label:
        title_text += f" ({month_label})"
    elements.append(Paragraph(title_text, styles["Title"]))
    elements.append(Spacer(1, 0.4 * cm))

    # Summary line
    total_income = sum(
        Decimal(str(tx.amount))
        for tx in transactions
        if tx.type == TransactionType.INCOME
    )
    total_expense = sum(
        Decimal(str(tx.amount))
        for tx in transactions
        if tx.type == TransactionType.EXPENSE
    )
    balance = total_income - total_expense
    summary = (
        f"Total de registros: {len(transactions)} | "
        f"Receitas: R$ {total_income:.2f} | "
        f"Despesas: R$ {total_expense:.2f} | "
        f"Saldo: R$ {balance:.2f}"
    )
    elements.append(Paragraph(summary, styles["Normal"]))
    elements.append(Spacer(1, 0.6 * cm))

    # Table
    header_row = ["Data", "Tipo", "Título", "Valor (R$)", "Status"]
    table_data: list[list[str]] = [header_row]
    for tx in transactions:
        table_data.append(
            [
                tx.due_date.strftime(_DATE_FMT) if tx.due_date else "",
                _LABEL_MAP.get(tx.type.value, tx.type.value) if tx.type else "",
                (tx.title or "")[:50],
                f"{Decimal(str(tx.amount)):.2f}",
                _LABEL_MAP.get(tx.status.value, tx.status.value) if tx.status else "",
            ]
        )

    col_widths = [2.5 * cm, 2.5 * cm, 7 * cm, 3 * cm, 2.5 * cm]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f5f5f5")],
                ),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
                ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(table)

    doc.build(elements)
    filename = f"auraxis_transactions_{month_label or 'export'}.pdf"
    return ExportResult(
        content=buf.getvalue(),
        content_type="application/pdf",
        filename=filename,
    )
