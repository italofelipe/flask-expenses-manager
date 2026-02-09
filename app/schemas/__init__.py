"""
Schemas da aplicação para documentação Swagger/OpenAPI

Este módulo contém todos os schemas Marshmallow utilizados para:
- Validação de dados de entrada
- Serialização de dados de saída
- Documentação automática da API no Swagger

Schemas disponíveis:
- Auth: Autenticação e registro de usuários
- User: Dados de usuário e perfil
- Transaction: Transações financeiras
- UserTicker: Ativos financeiros do usuário
- Account: Contas bancárias
- CreditCard: Cartões de crédito
- Tag: Tags para categorização
- Error: Respostas de erro padronizadas
"""

from .account_schema import AccountListSchema, AccountResponseSchema, AccountSchema
from .auth_schema import AuthSchema, AuthSuccessResponseSchema, LogoutSchema
from .credit_card_schema import (
    CreditCardListSchema,
    CreditCardResponseSchema,
    CreditCardSchema,
)
from .error_schema import ErrorResponseSchema
from .investment_operation_schema import InvestmentOperationSchema
from .tag_schema import TagListSchema, TagResponseSchema, TagSchema
from .transaction_schema import (
    MonthlySummarySchema,
    TransactionListSchema,
    TransactionResponseSchema,
    TransactionSchema,
)
from .user_schemas import (
    UserCompleteSchema,
    UserProfileSchema,
    UserRegistrationSchema,
    UserSchema,
)
from .user_ticker_schema import (
    UserTickerListSchema,
    UserTickerResponseSchema,
    UserTickerSchema,
)

__all__ = [
    # Auth schemas
    "AuthSchema",
    "AuthSuccessResponseSchema",
    "LogoutSchema",
    # User schemas
    "UserRegistrationSchema",
    "UserProfileSchema",
    "UserSchema",
    "UserCompleteSchema",
    # Transaction schemas
    "TransactionSchema",
    "TransactionResponseSchema",
    "TransactionListSchema",
    "MonthlySummarySchema",
    # UserTicker schemas
    "UserTickerSchema",
    "UserTickerResponseSchema",
    "UserTickerListSchema",
    # Account schemas
    "AccountSchema",
    "AccountResponseSchema",
    "AccountListSchema",
    # CreditCard schemas
    "CreditCardSchema",
    "CreditCardResponseSchema",
    "CreditCardListSchema",
    # Tag schemas
    "TagSchema",
    "TagResponseSchema",
    "TagListSchema",
    # Error schemas
    "ErrorResponseSchema",
    # Investment operation schemas
    "InvestmentOperationSchema",
]
