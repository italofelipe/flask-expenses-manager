from datetime import date
from decimal import Decimal
from typing import Any, Dict


def _graphql(
    client,
    query: str,
    variables: Dict[str, Any] | None = None,
    token: str | None = None,
):
    headers: Dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.post(
        "/graphql",
        json={"query": query, "variables": variables or {}},
        headers=headers,
    )


def _register_and_login_graphql(client) -> str:
    suffix = "graphql-user"
    register_mutation = """
    mutation Register($name: String!, $email: String!, $password: String!) {
      registerUser(name: $name, email: $email, password: $password) {
        message
        user { id name email }
      }
    }
    """
    register_response = _graphql(
        client,
        register_mutation,
        {
            "name": suffix,
            "email": f"{suffix}@email.com",
            "password": "StrongPass@123",
        },
    )
    assert register_response.status_code == 200
    register_body = register_response.get_json()
    assert "errors" not in register_body
    assert (
        register_body["data"]["registerUser"]["message"] == "User created successfully"
    )

    login_mutation = """
    mutation Login($email: String!, $password: String!) {
      login(email: $email, password: $password) {
        message
        token
        user { id name email }
      }
    }
    """
    login_response = _graphql(
        client,
        login_mutation,
        {"email": f"{suffix}@email.com", "password": "StrongPass@123"},
    )
    assert login_response.status_code == 200
    login_body = login_response.get_json()
    assert "errors" not in login_body
    token = login_body["data"]["login"]["token"]
    assert token
    return token


def test_graphql_register_login_and_me(client) -> None:
    token = _register_and_login_graphql(client)

    me_query = """
    query Me {
      me {
        id
        name
        email
      }
    }
    """
    response = _graphql(client, me_query, token=token)
    assert response.status_code == 200
    body = response.get_json()
    assert "errors" not in body
    assert body["data"]["me"]["email"] == "graphql-user@email.com"


def test_graphql_transactions_summary_and_dashboard(client) -> None:
    token = _register_and_login_graphql(client)
    due_date = date.today().isoformat()
    create_mutation = """
    mutation CreateTx(
      $title: String!,
      $amount: String!,
      $type: String!,
      $dueDate: String!
    ) {
      createTransaction(
        title: $title,
        amount: $amount,
        type: $type,
        dueDate: $dueDate
      ) {
        message
        items { id title type amount dueDate }
      }
    }
    """
    expense_response = _graphql(
        client,
        create_mutation,
        {
            "title": "Conta de luz",
            "amount": "150.00",
            "type": "expense",
            "dueDate": due_date,
        },
        token=token,
    )
    assert expense_response.status_code == 200
    assert "errors" not in expense_response.get_json()

    income_response = _graphql(
        client,
        create_mutation,
        {
            "title": "Freelance",
            "amount": "500.00",
            "type": "income",
            "dueDate": due_date,
        },
        token=token,
    )
    assert income_response.status_code == 200
    assert "errors" not in income_response.get_json()

    list_query = """
    query ListTx {
      transactions(page: 1, perPage: 10) {
        items { title type amount }
        pagination { total page perPage }
      }
    }
    """
    list_response = _graphql(client, list_query, token=token)
    assert list_response.status_code == 200
    list_body = list_response.get_json()
    assert "errors" not in list_body
    assert list_body["data"]["transactions"]["pagination"]["total"] >= 2

    month_ref = date.today().strftime("%Y-%m")
    summary_query = """
    query Summary($month: String!) {
      transactionSummary(month: $month, page: 1, pageSize: 10) {
        month
        incomeTotal
        expenseTotal
        pagination { total }
      }
    }
    """
    summary_response = _graphql(
        client, summary_query, {"month": month_ref}, token=token
    )
    assert summary_response.status_code == 200
    summary_body = summary_response.get_json()
    assert "errors" not in summary_body
    assert summary_body["data"]["transactionSummary"]["month"] == month_ref

    dashboard_query = """
    query Dashboard($month: String!) {
      transactionDashboard(month: $month) {
        month
        totals { incomeTotal expenseTotal balance }
        counts { totalTransactions incomeTransactions expenseTransactions }
      }
    }
    """
    dashboard_response = _graphql(
        client, dashboard_query, {"month": month_ref}, token=token
    )
    assert dashboard_response.status_code == 200
    dashboard_body = dashboard_response.get_json()
    assert "errors" not in dashboard_body
    assert dashboard_body["data"]["transactionDashboard"]["month"] == month_ref


def test_graphql_wallet_and_ticker_queries_mutations(client) -> None:
    token = _register_and_login_graphql(client)
    add_wallet_mutation = """
    mutation AddWallet {
      addWalletEntry(
        name: "Reserva",
        value: 1000,
        registerDate: "2026-02-09",
        shouldBeOnWallet: true
      ) {
        item { id name value registerDate shouldBeOnWallet assetClass }
      }
    }
    """
    wallet_response = _graphql(client, add_wallet_mutation, token=token)
    assert wallet_response.status_code == 200
    wallet_body = wallet_response.get_json()
    assert "errors" not in wallet_body
    assert wallet_body["data"]["addWalletEntry"]["item"]["name"] == "Reserva"
    assert wallet_body["data"]["addWalletEntry"]["item"]["assetClass"] == "custom"
    investment_id = wallet_body["data"]["addWalletEntry"]["item"]["id"]

    add_operation_mutation = """
    mutation AddOperation($investmentId: UUID!, $executedAt: String!) {
      addInvestmentOperation(
        investmentId: $investmentId,
        operationType: "buy",
        quantity: "3",
        unitPrice: "22.50",
        fees: "1.20",
        executedAt: $executedAt
      ) {
        message
        item { id operationType quantity unitPrice fees }
      }
    }
    """
    add_operation_response = _graphql(
        client,
        add_operation_mutation,
        {"investmentId": investment_id, "executedAt": "2026-02-09"},
        token=token,
    )
    assert add_operation_response.status_code == 200
    add_operation_body = add_operation_response.get_json()
    assert "errors" not in add_operation_body
    assert add_operation_body["data"]["addInvestmentOperation"]["item"]["quantity"] == (
        "3.000000"
    )

    operations_query = """
    query Operations($investmentId: UUID!, $date: String!) {
      investmentOperations(investmentId: $investmentId, page: 1, perPage: 10) {
        items { id operationType quantity unitPrice }
        pagination { total page perPage }
      }
      investmentOperationSummary(investmentId: $investmentId) {
        totalOperations
        buyOperations
        sellOperations
        netQuantity
      }
      investmentPosition(investmentId: $investmentId) {
        totalOperations
        buyOperations
        sellOperations
        totalBuyQuantity
        totalSellQuantity
        currentQuantity
        currentCostBasis
        averageCost
      }
      investmentInvestedAmount(investmentId: $investmentId, date: $date) {
        date
        totalOperations
        buyOperations
        sellOperations
        buyAmount
        sellAmount
        netInvestedAmount
      }
    }
    """
    operations_response = _graphql(
        client,
        operations_query,
        {"investmentId": investment_id, "date": "2026-02-09"},
        token=token,
    )
    assert operations_response.status_code == 200
    operations_body = operations_response.get_json()
    assert "errors" not in operations_body
    assert operations_body["data"]["investmentOperations"]["pagination"]["total"] == 1
    assert operations_body["data"]["investmentOperationSummary"]["buyOperations"] == 1
    assert (
        operations_body["data"]["investmentPosition"]["currentQuantity"] == "3.000000"
    )
    assert Decimal(
        operations_body["data"]["investmentInvestedAmount"]["netInvestedAmount"]
    ) == Decimal("68.7")

    wallet_query = """
    query WalletEntries {
      walletEntries(page: 1, perPage: 10) {
        items { id name registerDate shouldBeOnWallet }
        pagination { total page perPage }
      }
    }
    """
    wallet_list_response = _graphql(client, wallet_query, token=token)
    assert wallet_list_response.status_code == 200
    wallet_list_body = wallet_list_response.get_json()
    assert "errors" not in wallet_list_body
    assert wallet_list_body["data"]["walletEntries"]["pagination"]["total"] >= 1

    valuation_query = """
    query Valuation($investmentId: UUID!) {
      investmentValuation(investmentId: $investmentId) {
        investmentId
        name
        assetClass
        valuationSource
        investedAmount
        currentValue
        profitLossAmount
        profitLossPercent
      }
      portfolioValuation {
        summary {
          totalInvestments
          totalInvestedAmount
          totalCurrentValue
          totalProfitLoss
          totalProfitLossPercent
        }
      }
      portfolioValuationHistory(startDate: "2026-02-09", finalDate: "2026-02-09") {
        summary {
          startDate
          endDate
          totalPoints
          totalNetInvestedAmount
          finalCumulativeNetInvested
        }
        items {
          date
          totalOperations
          netInvestedAmount
          cumulativeNetInvested
        }
      }
    }
    """
    valuation_response = _graphql(
        client,
        valuation_query,
        {"investmentId": investment_id},
        token=token,
    )
    assert valuation_response.status_code == 200
    valuation_body = valuation_response.get_json()
    assert "errors" not in valuation_body
    assert valuation_body["data"]["investmentValuation"]["valuationSource"] == (
        "manual_value"
    )
    assert valuation_body["data"]["investmentValuation"]["assetClass"] == "custom"
    assert Decimal(valuation_body["data"]["investmentValuation"]["investedAmount"]) == (
        Decimal("1000")
    )
    assert (
        valuation_body["data"]["portfolioValuation"]["summary"]["totalInvestments"] >= 1
    )
    assert (
        valuation_body["data"]["portfolioValuationHistory"]["summary"]["totalPoints"]
        == 1
    )
    assert (
        valuation_body["data"]["portfolioValuationHistory"]["items"][0][
            "totalOperations"
        ]
        == 1
    )

    fixed_income_mutation = """
    mutation AddFixedIncomeWallet {
      addWalletEntry(
        name: "CDB",
        value: 1000,
        quantity: 1,
        assetClass: "cdb",
        annualRate: 12,
        registerDate: "2026-01-01",
        shouldBeOnWallet: true
      ) {
        item { id assetClass annualRate }
      }
    }
    """
    fixed_income_response = _graphql(client, fixed_income_mutation, token=token)
    assert fixed_income_response.status_code == 200
    fixed_income_body = fixed_income_response.get_json()
    assert "errors" not in fixed_income_body
    fixed_income_id = fixed_income_body["data"]["addWalletEntry"]["item"]["id"]

    fixed_income_valuation_query = """
    query FixedIncomeValuation($investmentId: UUID!) {
      investmentValuation(investmentId: $investmentId) {
        assetClass
        valuationSource
        investedAmount
        currentValue
      }
    }
    """
    fixed_income_valuation_response = _graphql(
        client,
        fixed_income_valuation_query,
        {"investmentId": fixed_income_id},
        token=token,
    )
    assert fixed_income_valuation_response.status_code == 200
    fixed_income_valuation_body = fixed_income_valuation_response.get_json()
    assert "errors" not in fixed_income_valuation_body
    assert (
        fixed_income_valuation_body["data"]["investmentValuation"]["assetClass"]
        == "cdb"
    )
    assert (
        fixed_income_valuation_body["data"]["investmentValuation"]["valuationSource"]
        == "fixed_income_projection"
    )

    add_ticker_mutation = """
    mutation AddTicker {
      addTicker(symbol: "PETR4", quantity: 10, type: "stock") {
        item { id symbol quantity type }
      }
    }
    """
    add_ticker_response = _graphql(client, add_ticker_mutation, token=token)
    assert add_ticker_response.status_code == 200
    add_ticker_body = add_ticker_response.get_json()
    assert "errors" not in add_ticker_body
    assert add_ticker_body["data"]["addTicker"]["item"]["symbol"] == "PETR4"

    tickers_query = """
    query Tickers {
      tickers {
        symbol
        quantity
        type
      }
    }
    """
    tickers_response = _graphql(client, tickers_query, token=token)
    assert tickers_response.status_code == 200
    tickers_body = tickers_response.get_json()
    assert "errors" not in tickers_body
    assert len(tickers_body["data"]["tickers"]) == 1

    delete_ticker_mutation = """
    mutation DeleteTicker {
      deleteTicker(symbol: "PETR4") {
        ok
        message
      }
    }
    """
    delete_response = _graphql(client, delete_ticker_mutation, token=token)
    assert delete_response.status_code == 200
    delete_body = delete_response.get_json()
    assert "errors" not in delete_body
    assert delete_body["data"]["deleteTicker"]["ok"] is True
