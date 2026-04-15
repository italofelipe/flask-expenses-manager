"""Transaction export service — issue #1022, streaming refactor #1055.

Generates CSV and PDF exports for a user's transactions.
Both formats respect the same filters (date range, type, status).
Export is gated behind the ``export_pdf`` entitlement (Premium plan).

CSV export is streamed via ``generate_csv_stream()`` — a generator that
yields one line at a time so the response body is flushed incrementally.
This removes the previous 10 000-row hard limit and reduces peak memory
usage from O(N) to O(batch_size).

PDF export loads rows in batches but must materialise the full document
before returning (ReportLab's SimpleDocTemplate is not incrementally
writable without the low-level canvas API).
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Generator, Iterator

from app.models.transaction import Transaction, TransactionStatus, TransactionType

if TYPE_CHECKING:
    from uuid import UUID

_EXPORT_BATCH_SIZE = 500
_DATE_FMT = "%d/%m/%Y"
_CSV_COLUMNS = ["data", "tipo", "titulo", "valor", "status", "descricao"]


@dataclass(frozen=True)
class ExportResult:
    content: bytes
    content_type: str
    filename: str


# ---------------------------------------------------------------------------
# Batched query (no hard limit)
# ---------------------------------------------------------------------------


def _iter_transactions_batched(
    *,
    user_id: "UUID",
    start_date: date | None,
    end_date: date | None,
    tx_type: TransactionType | None,
    status: TransactionStatus | None,
    batch_size: int = _EXPORT_BATCH_SIZE,
) -> Iterator[Transaction]:
    """Yield every matching transaction using cursor-based pagination.

    Queries ``batch_size`` rows at a time ordered by ``(due_date, id)``
    so pagination is deterministic and restart-safe.  There is no upper
    bound on the total number of rows yielded.
    """
    from uuid import UUID as _UUID

    last_due: date | None = None
    last_id: _UUID | None = None

    while True:
        query = Transaction.query.filter_by(user_id=user_id, deleted=False)

        if start_date is not None:
            query = query.filter(Transaction.due_date >= start_date)
        if end_date is not None:
            query = query.filter(Transaction.due_date <= end_date)
        if tx_type is not None:
            query = query.filter(Transaction.type == tx_type)
        if status is not None:
            query = query.filter(Transaction.status == status)

        if last_due is not None and last_id is not None:
            # Keyset pagination: skip rows we already yielded.
            # Rows are ordered by (due_date ASC, id ASC) so this condition
            # correctly advances the cursor without duplicates or gaps.
            from sqlalchemy import and_, or_

            query = query.filter(
                or_(
                    Transaction.due_date > last_due,
                    and_(
                        Transaction.due_date == last_due,
                        Transaction.id > last_id,
                    ),
                )
            )

        batch: list[Transaction] = (
            query.order_by(Transaction.due_date.asc(), Transaction.id.asc())
            .limit(batch_size)
            .all()
        )
        if not batch:
            break

        for row in batch:
            yield row

        last_row = batch[-1]
        last_due = last_row.due_date
        last_id = last_row.id

        if len(batch) < batch_size:
            # Last partial batch — no more rows
            break


# ---------------------------------------------------------------------------
# CSV streaming generator
# ---------------------------------------------------------------------------


def generate_csv_stream(
    *,
    user_id: "UUID",
    start_date: date | None = None,
    end_date: date | None = None,
    tx_type: TransactionType | None = None,
    status: TransactionStatus | None = None,
) -> Generator[str, None, None]:
    """Yield one CSV line at a time (header + data rows).

    Each yielded string ends with CRLF (standard CSV line ending).
    The first yielded string is the UTF-8 BOM + header row so the
    output is Excel-compatible when concatenated.

    Usage with Flask::

        from flask import Response, stream_with_context

        return Response(
            stream_with_context(generate_csv_stream(user_id=user_id, ...)),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="export.csv"'},
        )
    """
    # BOM + header
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(_CSV_COLUMNS)
    yield "\ufeff" + buf.getvalue()  # UTF-8 BOM for Excel compat

    for tx in _iter_transactions_batched(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        tx_type=tx_type,
        status=status,
    ):
        row_buf = io.StringIO()
        row_writer = csv.writer(row_buf, lineterminator="\r\n")
        row_writer.writerow(
            [
                tx.due_date.strftime(_DATE_FMT) if tx.due_date else "",
                tx.type.value if tx.type else "",
                tx.title or "",
                str(Decimal(str(tx.amount)).quantize(Decimal("0.01"))),
                tx.status.value if tx.status else "",
                tx.description or "",
            ]
        )
        yield row_buf.getvalue()


# ---------------------------------------------------------------------------
# CSV (materialised, for backward compat and service-layer unit tests)
# ---------------------------------------------------------------------------


def generate_csv_export(
    *,
    user_id: "UUID",
    start_date: date | None = None,
    end_date: date | None = None,
    tx_type: TransactionType | None = None,
    status: TransactionStatus | None = None,
    month_label: str = "",
) -> ExportResult:
    """Return a fully-materialised ExportResult (backward-compatible API).

    Internally consumes ``generate_csv_stream()`` so the same batching
    and unlimited-row semantics apply.
    """
    content = "".join(
        generate_csv_stream(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            tx_type=tx_type,
            status=status,
        )
    ).encode("utf-8")

    filename = f"auraxis_transactions_{month_label or 'export'}.csv"
    return ExportResult(
        content=content,
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

    # Materialise rows in batches — no 10K hard limit
    transactions = list(
        _iter_transactions_batched(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            tx_type=tx_type,
            status=status,
        )
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
