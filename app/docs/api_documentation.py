"""Metadados da documentação OpenAPI/Swagger da Auraxis API."""

API_INFO = {
    "title": "Auraxis API",
    "version": "1.0.0",
    "description": (
        "API para gestão financeira pessoal.\n\n"
        "- Controle de transações, carteira e dados de usuário.\n"
        "- Autenticação JWT.\n"
        "- Ticker representa o símbolo de mercado de ativos da carteira.\n"
        "- Consulte os documentos técnicos em docs/."
    ),
    "termsOfService": "https://seusite.com/termos",
    "contact": {"name": "Italo Chagas", "url": "https://github.com/italofelipe"},
    "license": {"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    "externalDocs": {
        "description": "Documentação técnica atual (as-is)",
        "url": "https://github.com/italofelipe/auraxis/tree/main/docs",
    },
}

TAGS = [
    {
        "name": "Autenticação",
        "description": "Endpoints para registro, login e logout de usuários",
    },
    {"name": "Usuários", "description": "Gerenciamento de dados de usuário e perfil"},
    {
        "name": "Transações",
        "description": "Criação, edição e consulta de transações financeiras",
    },
    {
        "name": "Metas",
        "description": "Gerenciamento de metas financeiras e planejamento",
    },
    {
        "name": "Wallet",
        "description": "Gerenciamento da carteira de investimentos",
    },
    {
        "name": "Health",
        "description": "Endpoint público para liveness/readiness de infraestrutura",
    },
    {"name": "Contas", "description": "Gerenciamento de contas bancárias (pendente)"},
    {
        "name": "Cartões de Crédito",
        "description": "Gerenciamento de cartões de crédito (pendente)",
    },
    {"name": "Tags", "description": "Sistema de categorização por tags (pendente)"},
]

EXAMPLES = {
    "transaction_create": {
        "summary": "Exemplo de criação de transação",
        "value": {
            "title": "Pagamento da conta de luz",
            "description": "Conta de energia elétrica do mês de janeiro",
            "amount": "150.50",
            "type": "expense",
            "due_date": "2024-02-15",
            "currency": "BRL",
            "is_recurring": False,
            "tag_id": "123e4567-e89b-12d3-a456-426614174000",
        },
    },
    "user_profile": {
        "summary": "Exemplo de atualização de perfil",
        "value": {
            "gender": "masculino",
            "birth_date": "1990-05-15",
            "monthly_income": "5000.00",
            "net_worth": "50000.00",
            "monthly_expenses": "3000.00",
            "initial_investment": "10000.00",
            "monthly_investment": "1000.00",
            "investment_goal_date": "2030-12-31",
        },
    },
    "wallet_create": {
        "summary": "Exemplo de criação de item da carteira",
        "value": {
            "name": "Investimento PETR4",
            "ticker": "PETR4",
            "quantity": 10,
            "register_date": "2024-07-01",
            "should_be_on_wallet": True,
        },
    },
}
