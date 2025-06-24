"""
Documentação da API - Not Enough Cash, Stranger!

Este arquivo contém informações gerais sobre a API para documentação Swagger.
"""

API_INFO = {
    "title": "Not Enough Cash, Stranger!",
    "version": "1.0.0",
    "description": (
        "API para gerenciamento financeiro pessoal.\n\n"
        "- Controle de transações, contas, cartões, investimentos.\n"
        "- Autenticação JWT.\n"
        "- Consulte exemplos, modelos e instruções nos links abaixo.\n"
        "- Para detalhes completos, acesse a documentação externa."
    ),
    "termsOfService": "https://seusite.com/termos",
    "contact": {"name": "Italo Chagas", "url": "https://github.com/italofelipe"},
    "license": {"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    "externalDocs": {
        "description": "Documentação completa, exemplos e modelos de dados",
        "url": "https://github.com/seurepo/docs/API_DOCUMENTATION.md",
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
        "name": "Investimentos",
        "description": "Gerenciamento de ativos financeiros (tickers)",
    },
    {"name": "Contas", "description": "Gerenciamento de contas bancárias"},
    {
        "name": "Cartões de Crédito",
        "description": "Gerenciamento de cartões de crédito",
    },
    {"name": "Tags", "description": "Sistema de categorização por tags"},
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
    "user_ticker": {
        "summary": "Exemplo de criação de ticker",
        "value": {"symbol": "PETR4", "quantity": 100.0, "type": "stock"},
    },
}
