from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

GraphQLOperationType = Literal["query", "mutation"]
GraphQLOperationAccess = Literal["public", "auth_required"]
GraphQLDomain = Literal[
    "auth",
    "goals",
    "investments",
    "simulations",
    "transactions",
    "user",
    "wallet",
]


@dataclass(frozen=True)
class GraphQLOperationDoc:
    name: str
    operation_type: GraphQLOperationType
    domain: GraphQLDomain
    access: GraphQLOperationAccess
    summary: str
    source_module: str
    entitlements: tuple[str, ...] = ()

    def to_manifest_entry(self) -> dict[str, object]:
        entry: dict[str, object] = {
            "name": self.name,
            "operation_type": self.operation_type,
            "domain": self.domain,
            "access": self.access,
            "summary": self.summary,
            "source_module": self.source_module,
        }
        if self.entitlements:
            entry["entitlements"] = list(self.entitlements)
        return entry


GRAPHQL_OPERATION_CATALOG: tuple[GraphQLOperationDoc, ...] = (
    GraphQLOperationDoc(
        name="me",
        operation_type="query",
        domain="user",
        access="auth_required",
        summary="Retorna o perfil do usuário autenticado.",
        source_module="app.graphql.queries.user",
    ),
    GraphQLOperationDoc(
        name="transactions",
        operation_type="query",
        domain="transactions",
        access="auth_required",
        summary="Lista transações ativas do usuário com paginação e filtros.",
        source_module="app.graphql.queries.transaction",
    ),
    GraphQLOperationDoc(
        name="transactionSummary",
        operation_type="query",
        domain="transactions",
        access="auth_required",
        summary="Retorna resumo mensal de transações com itens paginados.",
        source_module="app.graphql.queries.transaction",
    ),
    GraphQLOperationDoc(
        name="transactionDashboard",
        operation_type="query",
        domain="transactions",
        access="auth_required",
        summary="Entrega visão consolidada mensal de receitas, despesas e categorias.",
        source_module="app.graphql.queries.transaction",
    ),
    GraphQLOperationDoc(
        name="transactionDueRange",
        operation_type="query",
        domain="transactions",
        access="auth_required",
        summary="Lista transações por faixa de vencimento com métricas agregadas.",
        source_module="app.graphql.queries.transaction",
    ),
    GraphQLOperationDoc(
        name="goals",
        operation_type="query",
        domain="goals",
        access="auth_required",
        summary="Lista metas do usuário com paginação e filtro de status.",
        source_module="app.graphql.queries.goal",
    ),
    GraphQLOperationDoc(
        name="goal",
        operation_type="query",
        domain="goals",
        access="auth_required",
        summary="Retorna uma meta específica do usuário.",
        source_module="app.graphql.queries.goal",
    ),
    GraphQLOperationDoc(
        name="goalPlan",
        operation_type="query",
        domain="goals",
        access="auth_required",
        summary="Retorna o plano projetado de uma meta existente.",
        source_module="app.graphql.queries.goal",
    ),
    GraphQLOperationDoc(
        name="installmentVsCashCalculate",
        operation_type="query",
        domain="simulations",
        access="public",
        summary="Calcula a comparação entre pagamento parcelado e à vista.",
        source_module="app.graphql.queries.simulation",
    ),
    GraphQLOperationDoc(
        name="walletEntries",
        operation_type="query",
        domain="wallet",
        access="auth_required",
        summary="Lista entradas da carteira do usuário.",
        source_module="app.graphql.queries.wallet",
    ),
    GraphQLOperationDoc(
        name="walletHistory",
        operation_type="query",
        domain="wallet",
        access="auth_required",
        summary="Retorna histórico paginado de um investimento da carteira.",
        source_module="app.graphql.queries.wallet",
    ),
    GraphQLOperationDoc(
        name="tickers",
        operation_type="query",
        domain="wallet",
        access="auth_required",
        summary="Lista os tickers cadastrados pelo usuário.",
        source_module="app.graphql.queries.wallet",
    ),
    GraphQLOperationDoc(
        name="investmentOperations",
        operation_type="query",
        domain="investments",
        access="auth_required",
        summary="Lista operações de um investimento com paginação.",
        source_module="app.graphql.queries.investment",
    ),
    GraphQLOperationDoc(
        name="investmentOperationSummary",
        operation_type="query",
        domain="investments",
        access="auth_required",
        summary="Retorna o resumo agregado das operações de um investimento.",
        source_module="app.graphql.queries.investment",
    ),
    GraphQLOperationDoc(
        name="investmentPosition",
        operation_type="query",
        domain="investments",
        access="auth_required",
        summary="Retorna a posição consolidada de um investimento.",
        source_module="app.graphql.queries.investment",
    ),
    GraphQLOperationDoc(
        name="investmentInvestedAmount",
        operation_type="query",
        domain="investments",
        access="auth_required",
        summary="Calcula o valor investido acumulado em uma data específica.",
        source_module="app.graphql.queries.investment",
    ),
    GraphQLOperationDoc(
        name="investmentValuation",
        operation_type="query",
        domain="investments",
        access="auth_required",
        summary="Retorna a valorização atual de um investimento específico.",
        source_module="app.graphql.queries.investment",
    ),
    GraphQLOperationDoc(
        name="portfolioValuation",
        operation_type="query",
        domain="investments",
        access="auth_required",
        summary="Retorna a valorização consolidada do portfólio do usuário.",
        source_module="app.graphql.queries.investment",
    ),
    GraphQLOperationDoc(
        name="portfolioValuationHistory",
        operation_type="query",
        domain="investments",
        access="auth_required",
        summary="Retorna o histórico de valorização do portfólio em um período.",
        source_module="app.graphql.queries.investment",
    ),
    GraphQLOperationDoc(
        name="registerUser",
        operation_type="mutation",
        domain="auth",
        access="public",
        summary="Registra um novo usuário na plataforma.",
        source_module="app.graphql.mutations.auth",
    ),
    GraphQLOperationDoc(
        name="login",
        operation_type="mutation",
        domain="auth",
        access="public",
        summary="Autentica um usuário e retorna token JWT.",
        source_module="app.graphql.mutations.auth",
    ),
    GraphQLOperationDoc(
        name="logout",
        operation_type="mutation",
        domain="auth",
        access="auth_required",
        summary="Revoga a sessão atual do usuário autenticado.",
        source_module="app.graphql.mutations.auth",
    ),
    GraphQLOperationDoc(
        name="forgotPassword",
        operation_type="mutation",
        domain="auth",
        access="public",
        summary="Solicita o fluxo de redefinição de senha.",
        source_module="app.graphql.mutations.auth",
    ),
    GraphQLOperationDoc(
        name="resetPassword",
        operation_type="mutation",
        domain="auth",
        access="public",
        summary="Conclui a redefinição de senha com token válido.",
        source_module="app.graphql.mutations.auth",
    ),
    GraphQLOperationDoc(
        name="updateUserProfile",
        operation_type="mutation",
        domain="user",
        access="auth_required",
        summary="Atualiza o perfil financeiro e pessoal do usuário.",
        source_module="app.graphql.mutations.auth",
    ),
    GraphQLOperationDoc(
        name="createTransaction",
        operation_type="mutation",
        domain="transactions",
        access="auth_required",
        summary="Cria uma transação única, recorrente ou parcelada.",
        source_module="app.graphql.mutations.transaction",
    ),
    GraphQLOperationDoc(
        name="deleteTransaction",
        operation_type="mutation",
        domain="transactions",
        access="auth_required",
        summary="Realiza soft delete de uma transação do usuário.",
        source_module="app.graphql.mutations.transaction",
    ),
    GraphQLOperationDoc(
        name="createGoal",
        operation_type="mutation",
        domain="goals",
        access="auth_required",
        summary="Cria uma meta financeira.",
        source_module="app.graphql.mutations.goal",
    ),
    GraphQLOperationDoc(
        name="updateGoal",
        operation_type="mutation",
        domain="goals",
        access="auth_required",
        summary="Atualiza uma meta existente.",
        source_module="app.graphql.mutations.goal",
    ),
    GraphQLOperationDoc(
        name="deleteGoal",
        operation_type="mutation",
        domain="goals",
        access="auth_required",
        summary="Remove uma meta existente.",
        source_module="app.graphql.mutations.goal",
    ),
    GraphQLOperationDoc(
        name="simulateGoalPlan",
        operation_type="mutation",
        domain="goals",
        access="auth_required",
        summary="Simula o plano de aporte de uma meta sem persistir dados.",
        source_module="app.graphql.mutations.goal",
    ),
    GraphQLOperationDoc(
        name="saveInstallmentVsCashSimulation",
        operation_type="mutation",
        domain="simulations",
        access="auth_required",
        summary="Salva uma simulação de parcelado vs à vista no histórico do usuário.",
        source_module="app.graphql.mutations.simulation",
    ),
    GraphQLOperationDoc(
        name="createGoalFromInstallmentVsCashSimulation",
        operation_type="mutation",
        domain="simulations",
        access="auth_required",
        summary="Converte uma simulação em meta financeira.",
        source_module="app.graphql.mutations.simulation",
        entitlements=("advanced_simulations",),
    ),
    GraphQLOperationDoc(
        name="createPlannedExpenseFromInstallmentVsCashSimulation",
        operation_type="mutation",
        domain="simulations",
        access="auth_required",
        summary="Converte uma simulação em despesa planejada.",
        source_module="app.graphql.mutations.simulation",
        entitlements=("advanced_simulations",),
    ),
    GraphQLOperationDoc(
        name="addWalletEntry",
        operation_type="mutation",
        domain="wallet",
        access="auth_required",
        summary="Adiciona um item à carteira do usuário.",
        source_module="app.graphql.mutations.wallet",
    ),
    GraphQLOperationDoc(
        name="updateWalletEntry",
        operation_type="mutation",
        domain="wallet",
        access="auth_required",
        summary="Atualiza um item da carteira do usuário.",
        source_module="app.graphql.mutations.wallet",
    ),
    GraphQLOperationDoc(
        name="deleteWalletEntry",
        operation_type="mutation",
        domain="wallet",
        access="auth_required",
        summary="Remove um item da carteira do usuário.",
        source_module="app.graphql.mutations.wallet",
    ),
    GraphQLOperationDoc(
        name="addInvestmentOperation",
        operation_type="mutation",
        domain="investments",
        access="auth_required",
        summary="Registra uma operação em um investimento existente.",
        source_module="app.graphql.mutations.investment_operation",
    ),
    GraphQLOperationDoc(
        name="updateInvestmentOperation",
        operation_type="mutation",
        domain="investments",
        access="auth_required",
        summary="Atualiza uma operação de investimento existente.",
        source_module="app.graphql.mutations.investment_operation",
    ),
    GraphQLOperationDoc(
        name="deleteInvestmentOperation",
        operation_type="mutation",
        domain="investments",
        access="auth_required",
        summary="Remove uma operação de investimento existente.",
        source_module="app.graphql.mutations.investment_operation",
    ),
    GraphQLOperationDoc(
        name="addTicker",
        operation_type="mutation",
        domain="wallet",
        access="auth_required",
        summary="Adiciona um ticker ao acompanhamento do usuário.",
        source_module="app.graphql.mutations.ticker",
    ),
    GraphQLOperationDoc(
        name="deleteTicker",
        operation_type="mutation",
        domain="wallet",
        access="auth_required",
        summary="Remove um ticker do acompanhamento do usuário.",
        source_module="app.graphql.mutations.ticker",
    ),
)


def get_graphql_operation_catalog() -> tuple[GraphQLOperationDoc, ...]:
    return GRAPHQL_OPERATION_CATALOG


def get_graphql_operation_names(
    operation_type: GraphQLOperationType,
) -> set[str]:
    return {
        operation.name
        for operation in GRAPHQL_OPERATION_CATALOG
        if operation.operation_type == operation_type
    }


def build_graphql_operations_manifest() -> list[dict[str, object]]:
    return [operation.to_manifest_entry() for operation in GRAPHQL_OPERATION_CATALOG]
