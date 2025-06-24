# Documentação da API - Not Enough Cash, Stranger!

## 📋 Visão Geral

Esta API fornece funcionalidades completas para gerenciamento financeiro pessoal, incluindo controle de transações, investimentos, contas bancárias e cartões de crédito.

## 🔗 Acesso à Documentação

- **Swagger UI**: `http://localhost:5000/docs/`
- **OpenAPI JSON**: `http://localhost:5000/docs/swagger/`

## 🔐 Autenticação

A API utiliza JWT (JSON Web Tokens) para autenticação:

1. **Registro**: `POST /auth/register`
2. **Login**: `POST /auth/login`
3. **Logout**: `POST /auth/logout`

Para endpoints protegidos, inclua o header:
```
Authorization: Bearer <seu_token_jwt>
```

## 📊 Modelos de Dados

### Usuário (User)
```json
{
  "id": "uuid",
  "name": "string (2-128 chars)",
  "email": "email@exemplo.com",
  "password": "string (min 6 chars)",
  "gender": "masculino|feminino|outro",
  "birth_date": "YYYY-MM-DD",
  "monthly_income": "decimal",
  "net_worth": "decimal",
  "monthly_expenses": "decimal",
  "initial_investment": "decimal",
  "monthly_investment": "decimal",
  "investment_goal_date": "YYYY-MM-DD"
}
```

### Transação (Transaction)
```json
{
  "id": "uuid",
  "title": "string (1-120 chars)",
  "description": "string (max 300 chars)",
  "observation": "string (max 500 chars)",
  "amount": "decimal (min 0.01)",
  "currency": "string (3 chars, ISO 4217)",
  "type": "income|expense",
  "status": "paid|pending|cancelled|postponed|overdue",
  "due_date": "YYYY-MM-DD",
  "is_recurring": "boolean",
  "is_installment": "boolean",
  "installment_count": "integer (1-60)",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "tag_id": "uuid",
  "account_id": "uuid",
  "credit_card_id": "uuid"
}
```

### Ativo Financeiro (UserTicker)
```json
{
  "id": "uuid",
  "symbol": "string (1-10 chars)",
  "quantity": "float (min 0.01)",
  "type": "stock|fii|etf|bond|crypto|other"
}
```

### Conta Bancária (Account)
```json
{
  "id": "uuid",
  "name": "string (1-100 chars)"
}
```

### Cartão de Crédito (CreditCard)
```json
{
  "id": "uuid",
  "name": "string (1-100 chars)"
}
```

### Tag
```json
{
  "id": "uuid",
  "name": "string (1-50 chars)"
}
```

## 🚀 Endpoints Principais

### Autenticação
- `POST /auth/register` - Registrar novo usuário
- `POST /auth/login` - Fazer login
- `POST /auth/logout` - Fazer logout

### Usuários
- `GET /user/me` - Obter dados do usuário logado
- `PUT /user/profile` - Atualizar perfil do usuário

### Transações
- `GET /transaction/` - Listar transações (com paginação)
- `POST /transaction/` - Criar nova transação
- `GET /transaction/{id}` - Obter transação específica
- `PUT /transaction/{id}` - Atualizar transação
- `DELETE /transaction/{id}` - Excluir transação
- `GET /transaction/summary/{year}/{month}` - Resumo mensal

### Investimentos (Tickers)
- `GET /ticker/` - Listar ativos do usuário
- `POST /ticker/` - Adicionar novo ativo
- `GET /ticker/{id}` - Obter ativo específico
- `PUT /ticker/{id}` - Atualizar ativo
- `DELETE /ticker/{id}` - Remover ativo

## 📝 Exemplos de Uso

### Criar uma Transação
```bash
curl -X POST "http://localhost:5000/transaction/" \
  -H "Authorization: Bearer <seu_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Pagamento da conta de luz",
    "description": "Conta de energia elétrica do mês de janeiro",
    "amount": "150.50",
    "type": "expense",
    "due_date": "2024-02-15",
    "currency": "BRL",
    "is_recurring": false
  }'
```

### Atualizar Perfil do Usuário
```bash
curl -X PUT "http://localhost:5000/user/profile" \
  -H "Authorization: Bearer <seu_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "gender": "masculino",
    "birth_date": "1990-05-15",
    "monthly_income": "5000.00",
    "net_worth": "50000.00",
    "monthly_expenses": "3000.00"
  }'
```

### Adicionar Ativo Financeiro
```bash
curl -X POST "http://localhost:5000/ticker/" \
  -H "Authorization: Bearer <seu_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "PETR4",
    "quantity": 100.0,
    "type": "stock"
  }'
```

## 🔍 Filtros e Paginação

### Transações
- `page`: Número da página (padrão: 1)
- `per_page`: Itens por página (padrão: 20, máximo: 100)
- `type`: Filtrar por tipo (income/expense)
- `status`: Filtrar por status
- `start_date`: Data inicial
- `end_date`: Data final
- `tag_id`: Filtrar por tag
- `account_id`: Filtrar por conta
- `credit_card_id`: Filtrar por cartão

### Exemplo de Filtro
```bash
GET /transaction/?type=expense&status=pending&page=1&per_page=10
```

## 📊 Resumo Mensal

O endpoint `/transaction/summary/{year}/{month}` retorna:

```json
{
  "income_total": "5000.00",
  "expense_total": "3000.00",
  "transactions": [...]
}
```

## ⚠️ Códigos de Erro

- `400` - Dados inválidos
- `401` - Não autorizado (token inválido/expirado)
- `404` - Recurso não encontrado
- `422` - Erro de validação
- `500` - Erro interno do servidor

## 🔧 Configuração

### Variáveis de Ambiente
```bash
FLASK_ENV=development
FLASK_DEBUG=True
DATABASE_URL=postgresql://user:pass@localhost/dbname
JWT_SECRET_KEY=your-secret-key
```

### Dependências
```bash
pip install -r requirements.txt
```

## 🚀 Executando a API

1. **Instalar dependências**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configurar banco de dados**:
   ```bash
   flask db upgrade
   ```

3. **Executar a aplicação**:
   ```bash
   python run.py
   ```

4. **Acessar documentação**:
   ```
   http://localhost:5000/docs/
   ```

## 📚 Recursos Adicionais

- **Validações**: Todos os campos possuem validações apropriadas
- **Paginação**: Endpoints de listagem suportam paginação
- **Soft Delete**: Transações são marcadas como deletadas, não removidas fisicamente
- **Relacionamentos**: Suporte completo a relacionamentos entre entidades
- **Auditoria**: Campos `created_at` e `updated_at` em todas as entidades

## 🤝 Contribuindo

Para contribuir com a documentação:

1. Atualize os schemas em `app/schemas/`
2. Adicione exemplos em `app/docs/api_documentation.py`
3. Atualize este README conforme necessário
4. Teste a documentação no Swagger UI
