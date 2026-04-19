"""OpenAPI doc kwargs for the dashboard domain endpoints."""

from __future__ import annotations

from typing import Any

from app.docs.openapi_helpers import (
    contract_header_param,
    json_error_response,
    json_success_response,
)

DASHBOARD_OVERVIEW_DOC: dict[str, Any] = {
    "summary": "Obter overview mensal do dashboard",
    "description": (
        "Contrato canônico do dashboard financeiro do MVP1. "
        "Use esta rota para visão agregada mensal; "
        "`/transactions/dashboard` permanece apenas como compatibilidade "
        "transitória."
    ),
    "tags": ["Dashboard"],
    "security": [{"BearerAuth": []}],
    "params": {
        "month": {
            "description": "Mês de referência no formato YYYY-MM",
            "in": "query",
            "type": "string",
            "required": True,
            "example": "2026-03",
        },
        **contract_header_param(supported_version="v2"),
    },
    "responses": {
        200: json_success_response(
            description="Overview do dashboard",
            message="Overview do dashboard calculado com sucesso",
            data_example={
                "month": "2026-03",
                "totals": {
                    "income_total": 5000.0,
                    "expense_total": 3200.0,
                    "balance": 1800.0,
                },
                "counts": {
                    "total_transactions": 14,
                    "income_transactions": 4,
                    "expense_transactions": 10,
                    "status": {"paid": 9, "pending": 5},
                },
                "top_categories": {
                    "expense": [
                        {
                            "tag_id": "73c3b094-60bf-45d5-8e32-0f673b2ab4a2",
                            "category_name": "Moradia",
                            "total_amount": 1800.0,
                            "transactions_count": 3,
                        }
                    ],
                    "income": [
                        {
                            "tag_id": None,
                            "category_name": "Receitas",
                            "total_amount": 5000.0,
                            "transactions_count": 4,
                        }
                    ],
                },
            },
        ),
        400: json_error_response(
            description="Parâmetro inválido",
            message="Parâmetro 'month' inválido. Use o formato YYYY-MM.",
            error_code="VALIDATION_ERROR",
            status_code=400,
        ),
        401: json_error_response(
            description="Token inválido",
            message="Token revogado",
            error_code="UNAUTHORIZED",
            status_code=401,
        ),
        500: json_error_response(
            description="Erro interno",
            message="Erro ao calcular overview do dashboard",
            error_code="INTERNAL_ERROR",
            status_code=500,
        ),
    },
}

DASHBOARD_TRENDS_DOC: dict[str, Any] = {
    "summary": "Tendências mensais do dashboard",
    "description": (
        "Retorna a série histórica de receitas, despesas e saldo "
        "para os últimos N meses (apenas transações pagas)."
    ),
    "tags": ["Dashboard"],
    "security": [{"BearerAuth": []}],
    "params": {
        "months": {
            "description": "Número de meses a incluir (1–24, padrão 6)",
            "in": "query",
            "type": "integer",
            "required": False,
            "example": 6,
        },
        **contract_header_param(supported_version="v2"),
    },
    "responses": {
        200: json_success_response(
            description="Série de tendências mensais",
            message="Tendências calculadas com sucesso",
            data_example={
                "months": 6,
                "series": [
                    {
                        "month": "2026-04",
                        "income": 5000.0,
                        "expenses": 3200.0,
                        "balance": 1800.0,
                    }
                ],
            },
        ),
        401: json_error_response(
            description="Token inválido",
            message="Token revogado",
            error_code="UNAUTHORIZED",
            status_code=401,
        ),
        422: json_error_response(
            description="Parâmetro inválido",
            message="O parâmetro 'months' deve ser um inteiro entre 1 e 24.",
            error_code="VALIDATION_ERROR",
            status_code=422,
        ),
        500: json_error_response(
            description="Erro interno",
            message="Erro ao calcular tendências do dashboard",
            error_code="INTERNAL_ERROR",
            status_code=500,
        ),
    },
}

DASHBOARD_WEEKLY_SUMMARY_DOC: dict[str, Any] = {
    "summary": "Resumo semanal com comparativo (semana atual vs anterior)",
    "description": (
        "Retorna os totais da semana atual e da semana anterior (receita, despesa, "
        "saldo, contagem de transações pagas), o comparativo com deltas absolutos e "
        "percentuais, e uma série temporal para alimentar gráficos. "
        "Granularidade: diária quando period ≤ 31 dias, semanal caso contrário."
    ),
    "tags": ["Dashboard"],
    "security": [{"BearerAuth": []}],
    "params": {
        "period": {
            "description": "Preset de período da série: 1m (padrão), 3m, 6m",
            "in": "query",
            "type": "string",
            "required": False,
            "example": "1m",
        },
        "start_date": {
            "description": "Data inicial para período customizado (YYYY-MM-DD)",
            "in": "query",
            "type": "string",
            "required": False,
            "example": "2026-03-01",
        },
        "end_date": {
            "description": "Data final para período customizado (YYYY-MM-DD)",
            "in": "query",
            "type": "string",
            "required": False,
            "example": "2026-04-19",
        },
        **contract_header_param(supported_version="v2"),
    },
    "responses": {
        200: json_success_response(
            description="Resumo semanal calculado com sucesso",
            message="Resumo semanal calculado com sucesso",
            data_example={
                "current_week": {
                    "start": "2026-04-14",
                    "end": "2026-04-20",
                    "income": 2500.0,
                    "expense": 1800.0,
                    "balance": 700.0,
                    "transaction_count": 8,
                },
                "previous_week": {
                    "start": "2026-04-07",
                    "end": "2026-04-13",
                    "income": 0.0,
                    "expense": 2100.0,
                    "balance": -2100.0,
                    "transaction_count": 5,
                },
                "comparison": {
                    "income_delta": 2500.0,
                    "income_delta_percent": None,
                    "expense_delta": -300.0,
                    "expense_delta_percent": -14.29,
                    "balance_delta": 2800.0,
                    "balance_delta_percent": None,
                },
                "series": [
                    {
                        "date": "2026-03-20",
                        "income": 0.0,
                        "expense": 200.0,
                        "balance": -200.0,
                    }
                ],
                "period": "1m",
                "series_start": "2026-03-20",
                "series_end": "2026-04-19",
            },
        ),
        401: json_error_response(
            description="Token inválido",
            message="Token revogado",
            error_code="UNAUTHORIZED",
            status_code=401,
        ),
        422: json_error_response(
            description="Parâmetro inválido",
            message=(
                "Período inválido. Use 1m, 3m, 6m ou forneça start_date e end_date."
            ),
            error_code="VALIDATION_ERROR",
            status_code=422,
        ),
        500: json_error_response(
            description="Erro interno",
            message="Erro ao calcular resumo semanal",
            error_code="INTERNAL_ERROR",
            status_code=500,
        ),
    },
}

DASHBOARD_SURVIVAL_DOC: dict[str, Any] = {
    "summary": "Índice de sobrevivência financeira (burn rate)",
    "description": (
        "Calcula quantos meses o patrimônio atual sustenta o custo de vida médio. "
        "Patrimônio = soma das entradas de carteira (should_be_on_wallet=True). "
        "Custo médio = média de despesas pagas nos últimos 3 meses completos."
    ),
    "tags": ["Dashboard"],
    "security": [{"BearerAuth": []}],
    "params": {
        **contract_header_param(supported_version="v2"),
    },
    "responses": {
        200: json_success_response(
            description="Índice de sobrevivência calculado",
            message="Índice de sobrevivência calculado com sucesso",
            data_example={
                "survival_months": 8.5,
                "total_assets": 42500.00,
                "avg_monthly_expense": 5000.00,
                "classification": "comfortable",
                "period_analyzed_months": 3,
            },
        ),
        401: json_error_response(
            description="Token inválido",
            message="Token revogado",
            error_code="UNAUTHORIZED",
            status_code=401,
        ),
        500: json_error_response(
            description="Erro interno",
            message="Erro ao calcular índice de sobrevivência",
            error_code="INTERNAL_ERROR",
            status_code=500,
        ),
    },
}
