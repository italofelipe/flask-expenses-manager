"""GET /transactions/export — premium-gated CSV/PDF export.

Query params
------------
format        : ``csv`` (default) or ``pdf``
start_date    : YYYY-MM-DD  (inclusive)
end_date      : YYYY-MM-DD  (inclusive)
type          : ``income`` | ``expense``
status        : ``paid`` | ``pending`` | ``cancelled`` | ``postponed`` | ``overdue``

Entitlement
-----------
Requires the ``export_pdf`` feature (Premium / Trial plan).
Free users receive 403 ENTITLEMENT_REQUIRED.

Streaming (CSV)
---------------
CSV exports are streamed via Flask ``stream_with_context`` — rows are flushed
to the client as they are generated so peak memory usage stays constant
regardless of dataset size.  There is no row-count limit.

PDF exports are still materialised in memory (ReportLab requirement).
"""

from __future__ import annotations

from flask import Response, make_response, request, stream_with_context
from flask_apispec.views import MethodResource

from app.application.errors import PublicValidationError
from app.auth import current_user_id
from app.docs.openapi_helpers import json_error_response
from app.models.transaction import TransactionStatus, TransactionType
from app.services.transaction_export_service import (
    generate_csv_stream,
    generate_pdf_export,
)
from app.utils.typed_decorators import (
    typed_doc as doc,
)
from app.utils.typed_decorators import (
    typed_jwt_required as jwt_required,
)
from app.utils.typed_decorators import (
    typed_require_entitlement as require_entitlement,
)

from .utils import (
    _compat_error,
    _internal_error_response,
    _parse_optional_date,
)

_SUPPORTED_FORMATS = frozenset({"csv", "pdf"})
_VALID_TYPES = {t.value: t for t in TransactionType}
_VALID_STATUSES = {s.value: s for s in TransactionStatus}


def _parse_export_params() -> dict[str, object]:
    """Parse and validate query params for the export endpoint."""
    fmt = (request.args.get("format") or "csv").lower()
    if fmt not in _SUPPORTED_FORMATS:
        raise PublicValidationError("Parâmetro 'format' inválido. Use 'csv' ou 'pdf'.")

    start_date = _parse_optional_date(request.args.get("start_date"), "start_date")
    end_date = _parse_optional_date(request.args.get("end_date"), "end_date")

    if start_date and end_date and start_date > end_date:
        raise PublicValidationError("'start_date' não pode ser posterior a 'end_date'.")

    raw_type = request.args.get("type")
    tx_type: TransactionType | None = None
    if raw_type:
        if raw_type not in _VALID_TYPES:
            raise PublicValidationError(
                "Parâmetro 'type' inválido. Use 'income' ou 'expense'."
            )
        tx_type = _VALID_TYPES[raw_type]

    raw_status = request.args.get("status")
    tx_status: TransactionStatus | None = None
    if raw_status:
        if raw_status not in _VALID_STATUSES:
            raise PublicValidationError(
                "Parâmetro 'status' inválido. "
                "Use 'paid', 'pending', 'cancelled', 'postponed' ou 'overdue'."
            )
        tx_status = _VALID_STATUSES[raw_status]

    # Build a label for filenames (e.g. "2026-01_2026-03")
    parts = []
    if start_date:
        parts.append(start_date.strftime("%Y-%m"))
    if end_date:
        parts.append(end_date.strftime("%Y-%m"))
    month_label = "_".join(parts)

    return {
        "format": fmt,
        "start_date": start_date,
        "end_date": end_date,
        "tx_type": tx_type,
        "tx_status": tx_status,
        "month_label": month_label,
    }


class TransactionExportResource(MethodResource):
    @doc(
        summary="Exportar transações (CSV ou PDF)",
        description=(
            "Gera um arquivo com as transações do usuário no formato solicitado.\n\n"
            "**Requer entitlement `export_pdf` (plano Premium ou Trial).**\n\n"
            "Parâmetros:\n"
            "- `format`: `csv` (padrão) ou `pdf`\n"
            "- `start_date` / `end_date`: intervalo de `due_date` (YYYY-MM-DD)\n"
            "- `type`: `income` | `expense`\n"
            "- `status`: `paid` | `pending` | `cancelled` | `postponed` | `overdue`\n\n"
            "CSV: streamed via chunked transfer — sem limite de linhas.\n"
            "PDF: materializado em memória (limitado pela RAM do servidor)."
        ),
        tags=["Transações"],
        responses={
            200: {
                "description": "Arquivo CSV ou PDF com as transações",
                "content": {
                    "text/csv": {},
                    "application/pdf": {},
                },
            },
            400: json_error_response(
                description="Parâmetros inválidos",
                message="Parâmetro 'format' inválido.",
                error_code="VALIDATION_ERROR",
                status_code=400,
            ),
            401: json_error_response(
                description="Token ausente ou inválido",
                message="Token ausente",
                error_code="UNAUTHORIZED",
                status_code=401,
            ),
            403: json_error_response(
                description="Entitlement insuficiente — plano Premium necessário",
                message="Feature 'export_pdf' requires an active entitlement.",
                error_code="ENTITLEMENT_REQUIRED",
                status_code=403,
            ),
        },
    )
    @jwt_required()
    @require_entitlement("export_pdf")
    def get(self) -> Response:
        try:
            params = _parse_export_params()
        except PublicValidationError as exc:
            return _compat_error(
                legacy_payload={"error": str(exc)},
                status_code=400,
                message=str(exc),
                error_code="VALIDATION_ERROR",
            )

        user_id = current_user_id()
        fmt = str(params["format"])
        month_label = str(params["month_label"])

        if fmt == "pdf":
            try:
                result = generate_pdf_export(
                    user_id=user_id,
                    start_date=params["start_date"],  # type: ignore[arg-type]
                    end_date=params["end_date"],  # type: ignore[arg-type]
                    tx_type=params["tx_type"],  # type: ignore[arg-type]
                    status=params["tx_status"],  # type: ignore[arg-type]
                    month_label=month_label,
                )
            except Exception:
                return _internal_error_response(
                    message="Erro ao gerar o arquivo de exportação.",
                    log_context="transaction PDF export generation failed",
                )
            response = make_response(result.content)
            response.headers["Content-Type"] = result.content_type
            response.headers["Content-Disposition"] = (
                f'attachment; filename="{result.filename}"'
            )
            return response

        # CSV — stream row by row; no hard row-count limit
        filename = f"auraxis_transactions_{month_label or 'export'}.csv"
        return Response(
            stream_with_context(
                generate_csv_stream(
                    user_id=user_id,
                    start_date=params["start_date"],  # type: ignore[arg-type]
                    end_date=params["end_date"],  # type: ignore[arg-type]
                    tx_type=params["tx_type"],  # type: ignore[arg-type]
                    status=params["tx_status"],  # type: ignore[arg-type]
                )
            ),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
