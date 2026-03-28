from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

GraphQLOperationType = Literal["query", "mutation"]
GraphQLOperationAccess = Literal["public", "auth_required"]
GraphQLDomain = Literal[
    "auth",
    "dashboard",
    "goals",
    "investments",
    "simulations",
    "transactions",
    "user",
    "wallet",
]

QUERY_USER_MODULE = "app.graphql.queries.user"
QUERY_DASHBOARD_MODULE = "app.graphql.queries.dashboard"
QUERY_TRANSACTION_MODULE = "app.graphql.queries.transaction"
QUERY_GOAL_MODULE = "app.graphql.queries.goal"
QUERY_SIMULATION_MODULE = "app.graphql.queries.simulation"
QUERY_WALLET_MODULE = "app.graphql.queries.wallet"
QUERY_INVESTMENT_MODULE = "app.graphql.queries.investment"
MUTATION_AUTH_MODULE = "app.graphql.mutations.auth"
MUTATION_TRANSACTION_MODULE = "app.graphql.mutations.transaction"
MUTATION_GOAL_MODULE = "app.graphql.mutations.goal"
MUTATION_SIMULATION_MODULE = "app.graphql.mutations.simulation"
MUTATION_WALLET_MODULE = "app.graphql.mutations.wallet"
MUTATION_INVESTMENT_MODULE = "app.graphql.mutations.investment_operation"
MUTATION_TICKER_MODULE = "app.graphql.mutations.ticker"
ADVANCED_SIMULATIONS = "advanced_simulations"


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
        source_module=QUERY_USER_MODULE,
    ),
    GraphQLOperationDoc(
        name="dashboardOverview",
        operation_type="query",
        domain="dashboard",
        access="auth_required",
        summary="Retorna o read model canônico do dashboard financeiro mensal.",
        source_module=QUERY_DASHBOARD_MODULE,
    ),
    GraphQLOperationDoc(
        name="transactions",
        operation_type="query",
        domain="transactions",
        access="auth_required",
        summary="Lista transações ativas do usuário com paginação e filtros.",
        source_module=QUERY_TRANSACTION_MODULE,
    ),
    GraphQLOperationDoc(
        name="transaction",
        operation_type="query",
        domain="transactions",
        access="auth_required",
        summary="Retorna uma transação específica do usuário.",
        source_module=QUERY_TRANSACTION_MODULE,
    ),
    GraphQLOperationDoc(
        name="transactionSummary",
        operation_type="query",
        domain="transactions",
        access="auth_required",
        summary="Retorna resumo mensal de transações com itens paginados.",
        source_module=QUERY_TRANSACTION_MODULE,
    ),
    GraphQLOperationDoc(
        name="transactionDashboard",
        operation_type="query",
        domain="transactions",
        access="auth_required",
        summary=(
            "Compatibilidade transitória do dashboard mensal; "
            "prefira dashboardOverview."
        ),
        source_module=QUERY_TRANSACTION_MODULE,
    ),
    GraphQLOperationDoc(
        name="transactionDueRange",
        operation_type="query",
        domain="transactions",
        access="auth_required",
        summary="Lista transações por faixa de vencimento com métricas agregadas.",
        source_module=QUERY_TRANSACTION_MODULE,
    ),
    GraphQLOperationDoc(
        name="goals",
        operation_type="query",
        domain="goals",
        access="auth_required",
        summary="Lista metas do usuário com paginação e filtro de status.",
        source_module=QUERY_GOAL_MODULE,
    ),
    GraphQLOperationDoc(
        name="goal",
        operation_type="query",
        domain="goals",
        access="auth_required",
        summary="Retorna uma meta específica do usuário.",
        source_module=QUERY_GOAL_MODULE,
    ),
    GraphQLOperationDoc(
        name="goalPlan",
        operation_type="query",
        domain="goals",
        access="auth_required",
        summary="Retorna o plano projetado de uma meta existente.",
        source_module=QUERY_GOAL_MODULE,
    ),
    GraphQLOperationDoc(
        name="installmentVsCashCalculate",
        operation_type="query",
        domain="simulations",
        access="public",
        summary="Calcula a comparação entre pagamento parcelado e à vista.",
        source_module=QUERY_SIMULATION_MODULE,
    ),
    GraphQLOperationDoc(
        name="walletEntries",
        operation_type="query",
        domain="wallet",
        access="auth_required",
        summary="Lista entradas da carteira do usuário.",
        source_module=QUERY_WALLET_MODULE,
    ),
    GraphQLOperationDoc(
        name="walletHistory",
        operation_type="query",
        domain="wallet",
        access="auth_required",
        summary="Retorna histórico paginado de um investimento da carteira.",
        source_module=QUERY_WALLET_MODULE,
    ),
    GraphQLOperationDoc(
        name="tickers",
        operation_type="query",
        domain="wallet",
        access="auth_required",
        summary="Lista os tickers cadastrados pelo usuário.",
        source_module=QUERY_WALLET_MODULE,
    ),
    GraphQLOperationDoc(
        name="investmentOperations",
        operation_type="query",
        domain="investments",
        access="auth_required",
        summary="Lista operações de um investimento com paginação.",
        source_module=QUERY_INVESTMENT_MODULE,
    ),
    GraphQLOperationDoc(
        name="investmentOperationSummary",
        operation_type="query",
        domain="investments",
        access="auth_required",
        summary="Retorna o resumo agregado das operações de um investimento.",
        source_module=QUERY_INVESTMENT_MODULE,
    ),
    GraphQLOperationDoc(
        name="investmentPosition",
        operation_type="query",
        domain="investments",
        access="auth_required",
        summary="Retorna a posição consolidada de um investimento.",
        source_module=QUERY_INVESTMENT_MODULE,
    ),
    GraphQLOperationDoc(
        name="investmentInvestedAmount",
        operation_type="query",
        domain="investments",
        access="auth_required",
        summary="Calcula o valor investido acumulado em uma data específica.",
        source_module=QUERY_INVESTMENT_MODULE,
    ),
    GraphQLOperationDoc(
        name="investmentValuation",
        operation_type="query",
        domain="investments",
        access="auth_required",
        summary="Retorna a valorização atual de um investimento específico.",
        source_module=QUERY_INVESTMENT_MODULE,
    ),
    GraphQLOperationDoc(
        name="portfolioValuation",
        operation_type="query",
        domain="investments",
        access="auth_required",
        summary="Retorna a valorização consolidada do portfólio do usuário.",
        source_module=QUERY_INVESTMENT_MODULE,
    ),
    GraphQLOperationDoc(
        name="portfolioValuationHistory",
        operation_type="query",
        domain="investments",
        access="auth_required",
        summary="Retorna o histórico de valorização do portfólio em um período.",
        source_module=QUERY_INVESTMENT_MODULE,
    ),
    GraphQLOperationDoc(
        name="registerUser",
        operation_type="mutation",
        domain="auth",
        access="public",
        summary="Registra um novo usuário na plataforma.",
        source_module=MUTATION_AUTH_MODULE,
    ),
    GraphQLOperationDoc(
        name="login",
        operation_type="mutation",
        domain="auth",
        access="public",
        summary="Autentica um usuário e retorna token JWT.",
        source_module=MUTATION_AUTH_MODULE,
    ),
    GraphQLOperationDoc(
        name="logout",
        operation_type="mutation",
        domain="auth",
        access="auth_required",
        summary="Revoga a sessão atual do usuário autenticado.",
        source_module=MUTATION_AUTH_MODULE,
    ),
    GraphQLOperationDoc(
        name="forgotPassword",
        operation_type="mutation",
        domain="auth",
        access="public",
        summary="Solicita o fluxo de redefinição de senha.",
        source_module=MUTATION_AUTH_MODULE,
    ),
    GraphQLOperationDoc(
        name="resetPassword",
        operation_type="mutation",
        domain="auth",
        access="public",
        summary="Conclui a redefinição de senha com token válido.",
        source_module=MUTATION_AUTH_MODULE,
    ),
    GraphQLOperationDoc(
        name="updateUserProfile",
        operation_type="mutation",
        domain="user",
        access="auth_required",
        summary="Atualiza o perfil financeiro e pessoal do usuário.",
        source_module=MUTATION_AUTH_MODULE,
    ),
    GraphQLOperationDoc(
        name="createTransaction",
        operation_type="mutation",
        domain="transactions",
        access="auth_required",
        summary="Cria uma transação única, recorrente ou parcelada.",
        source_module=MUTATION_TRANSACTION_MODULE,
    ),
    GraphQLOperationDoc(
        name="deleteTransaction",
        operation_type="mutation",
        domain="transactions",
        access="auth_required",
        summary="Realiza soft delete de uma transação do usuário.",
        source_module=MUTATION_TRANSACTION_MODULE,
    ),
    GraphQLOperationDoc(
        name="updateTransaction",
        operation_type="mutation",
        domain="transactions",
        access="auth_required",
        summary="Atualiza parcialmente uma transação do usuário.",
        source_module=MUTATION_TRANSACTION_MODULE,
    ),
    GraphQLOperationDoc(
        name="createGoal",
        operation_type="mutation",
        domain="goals",
        access="auth_required",
        summary="Cria uma meta financeira.",
        source_module=MUTATION_GOAL_MODULE,
    ),
    GraphQLOperationDoc(
        name="updateGoal",
        operation_type="mutation",
        domain="goals",
        access="auth_required",
        summary="Atualiza uma meta existente.",
        source_module=MUTATION_GOAL_MODULE,
    ),
    GraphQLOperationDoc(
        name="deleteGoal",
        operation_type="mutation",
        domain="goals",
        access="auth_required",
        summary="Remove uma meta existente.",
        source_module=MUTATION_GOAL_MODULE,
    ),
    GraphQLOperationDoc(
        name="simulateGoalPlan",
        operation_type="mutation",
        domain="goals",
        access="auth_required",
        summary="Simula o plano de aporte de uma meta sem persistir dados.",
        source_module=MUTATION_GOAL_MODULE,
    ),
    GraphQLOperationDoc(
        name="saveInstallmentVsCashSimulation",
        operation_type="mutation",
        domain="simulations",
        access="auth_required",
        summary="Salva uma simulação de parcelado vs à vista no histórico do usuário.",
        source_module=MUTATION_SIMULATION_MODULE,
    ),
    GraphQLOperationDoc(
        name="createGoalFromInstallmentVsCashSimulation",
        operation_type="mutation",
        domain="simulations",
        access="auth_required",
        summary="Converte uma simulação em meta financeira.",
        source_module=MUTATION_SIMULATION_MODULE,
        entitlements=(ADVANCED_SIMULATIONS,),
    ),
    GraphQLOperationDoc(
        name="createPlannedExpenseFromInstallmentVsCashSimulation",
        operation_type="mutation",
        domain="simulations",
        access="auth_required",
        summary="Converte uma simulação em despesa planejada.",
        source_module=MUTATION_SIMULATION_MODULE,
        entitlements=(ADVANCED_SIMULATIONS,),
    ),
    GraphQLOperationDoc(
        name="addWalletEntry",
        operation_type="mutation",
        domain="wallet",
        access="auth_required",
        summary="Adiciona um item à carteira do usuário.",
        source_module=MUTATION_WALLET_MODULE,
    ),
    GraphQLOperationDoc(
        name="updateWalletEntry",
        operation_type="mutation",
        domain="wallet",
        access="auth_required",
        summary="Atualiza um item da carteira do usuário.",
        source_module=MUTATION_WALLET_MODULE,
    ),
    GraphQLOperationDoc(
        name="deleteWalletEntry",
        operation_type="mutation",
        domain="wallet",
        access="auth_required",
        summary="Remove um item da carteira do usuário.",
        source_module=MUTATION_WALLET_MODULE,
    ),
    GraphQLOperationDoc(
        name="addInvestmentOperation",
        operation_type="mutation",
        domain="investments",
        access="auth_required",
        summary="Registra uma operação em um investimento existente.",
        source_module=MUTATION_INVESTMENT_MODULE,
    ),
    GraphQLOperationDoc(
        name="updateInvestmentOperation",
        operation_type="mutation",
        domain="investments",
        access="auth_required",
        summary="Atualiza uma operação de investimento existente.",
        source_module=MUTATION_INVESTMENT_MODULE,
    ),
    GraphQLOperationDoc(
        name="deleteInvestmentOperation",
        operation_type="mutation",
        domain="investments",
        access="auth_required",
        summary="Remove uma operação de investimento existente.",
        source_module=MUTATION_INVESTMENT_MODULE,
    ),
    GraphQLOperationDoc(
        name="addTicker",
        operation_type="mutation",
        domain="wallet",
        access="auth_required",
        summary="Adiciona um ticker ao acompanhamento do usuário.",
        source_module=MUTATION_TICKER_MODULE,
    ),
    GraphQLOperationDoc(
        name="deleteTicker",
        operation_type="mutation",
        domain="wallet",
        access="auth_required",
        summary="Remove um ticker do acompanhamento do usuário.",
        source_module=MUTATION_TICKER_MODULE,
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
