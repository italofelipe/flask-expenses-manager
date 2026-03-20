from __future__ import annotations

import uuid

from app.models.user import User
from app.services.entitlement_service import grant_entitlement


def _graphql(
    client,
    query: str,
    variables: dict[str, object] | None = None,
    token: str | None = None,
):
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.post(
        "/graphql",
        json={"query": query, "variables": variables or {}},
        headers=headers,
    )


def _register_and_login_graphql(client, prefix: str) -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@email.com"
    password = "StrongPass@123"
    register_mutation = """
    mutation Register($name: String!, $email: String!, $password: String!) {
      registerUser(name: $name, email: $email, password: $password) {
        message
      }
    }
    """
    register_response = _graphql(
        client,
        register_mutation,
        {
            "name": f"{prefix}-{suffix}",
            "email": email,
            "password": password,
        },
    )
    assert register_response.status_code == 200
    assert "errors" not in register_response.get_json()

    login_mutation = """
    mutation Login($email: String!, $password: String!) {
      login(email: $email, password: $password) {
        token
      }
    }
    """
    login_response = _graphql(
        client,
        login_mutation,
        {"email": email, "password": password},
    )
    assert login_response.status_code == 200
    login_body = login_response.get_json()
    assert "errors" not in login_body
    return login_body["data"]["login"]["token"], email


def _grant_advanced_simulations(client, email: str) -> None:
    with client.application.app_context():
        user = User.query.filter_by(email=email).first()
        assert user is not None
        grant_entitlement(user.id, "advanced_simulations", source="manual")
        from app.extensions.database import db

        db.session.commit()


def test_graphql_installment_vs_cash_calculate_is_public(client) -> None:
    query = """
    query InstallmentVsCashCalculate(
      $cashPrice: String!,
      $installmentCount: Int!,
      $inflationRateAnnual: String!
    ) {
      installmentVsCashCalculate(
        cashPrice: $cashPrice
        installmentCount: $installmentCount
        installmentTotal: "990.00"
        firstPaymentDelayDays: 30
        opportunityRateType: "manual"
        opportunityRateAnnual: "12.00"
        inflationRateAnnual: $inflationRateAnnual
        feesEnabled: false
        feesUpfront: "0.00"
      ) {
        toolId
        ruleVersion
        result {
          recommendedOption
        }
      }
    }
    """

    response = _graphql(
        client,
        query,
        {
            "cashPrice": "900.00",
            "installmentCount": 3,
            "inflationRateAnnual": "4.50",
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert "errors" not in body
    assert body["data"]["installmentVsCashCalculate"]["toolId"] == (
        "installment_vs_cash"
    )


def test_graphql_installment_vs_cash_save_and_bridges_flow(client) -> None:
    token, email = _register_and_login_graphql(client, "graphql-installment")
    _grant_advanced_simulations(client, email)

    save_mutation = """
    mutation SaveInstallmentVsCash(
      $cashPrice: String!,
      $installmentCount: Int!,
      $inflationRateAnnual: String!
    ) {
      saveInstallmentVsCashSimulation(
        cashPrice: $cashPrice
        installmentCount: $installmentCount
        installmentTotal: "990.00"
        firstPaymentDelayDays: 30
        opportunityRateType: "manual"
        opportunityRateAnnual: "12.00"
        inflationRateAnnual: $inflationRateAnnual
        feesEnabled: true
        feesUpfront: "60.00"
        scenarioLabel: "Notebook"
      ) {
        message
        simulation { id toolId saved }
        calculation { result { recommendedOption } }
      }
    }
    """
    save_response = _graphql(
        client,
        save_mutation,
        {
            "cashPrice": "900.00",
            "installmentCount": 3,
            "inflationRateAnnual": "4.50",
        },
        token=token,
    )
    assert save_response.status_code == 200
    save_body = save_response.get_json()
    assert "errors" not in save_body
    simulation_id = save_body["data"]["saveInstallmentVsCashSimulation"]["simulation"][
        "id"
    ]

    goal_mutation = """
    mutation CreateGoalFromSimulation($simulationId: UUID!, $title: String!) {
      createGoalFromInstallmentVsCashSimulation(
        simulationId: $simulationId
        title: $title
        selectedOption: "cash"
      ) {
        message
        goal { id title targetAmount }
        simulation { goalId }
      }
    }
    """
    goal_response = _graphql(
        client,
        goal_mutation,
        {"simulationId": simulation_id, "title": "Notebook novo"},
        token=token,
    )
    assert goal_response.status_code == 200
    goal_body = goal_response.get_json()
    assert "errors" not in goal_body
    assert (
        goal_body["data"]["createGoalFromInstallmentVsCashSimulation"]["goal"][
            "targetAmount"
        ]
        == "900.00"
    )

    expense_mutation = """
    mutation CreatePlannedExpenseFromSimulation($simulationId: UUID!, $title: String!) {
      createPlannedExpenseFromInstallmentVsCashSimulation(
        simulationId: $simulationId
        title: $title
        selectedOption: "installment"
        firstDueDate: "2026-04-15"
      ) {
        message
        transactions { title isInstallment }
      }
    }
    """
    expense_response = _graphql(
        client,
        expense_mutation,
        {"simulationId": simulation_id, "title": "Notebook novo"},
        token=token,
    )
    assert expense_response.status_code == 200
    expense_body = expense_response.get_json()
    assert "errors" not in expense_body
    transactions = expense_body["data"][
        "createPlannedExpenseFromInstallmentVsCashSimulation"
    ]["transactions"]
    assert len(transactions) == 4
    assert any(item["isInstallment"] is True for item in transactions)
