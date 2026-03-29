"""
seed_local.py — Popula o banco de desenvolvimento local com dados de demonstração.

Uso:
    python scripts/seed_local.py        # Adiciona dados sem apagar existentes
    python scripts/seed_local.py --reset  # Apaga e recria todas as tabelas
"""

import argparse
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

# Ensure repo root is on sys.path so app can be imported when running from any dir
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from werkzeug.security import generate_password_hash  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions.database import db  # noqa: E402
from app.models.account import Account  # noqa: E402
from app.models.credit_card import CreditCard  # noqa: E402
from app.models.goal import Goal  # noqa: E402
from app.models.tag import Tag  # noqa: E402
from app.models.transaction import (  # noqa: E402
    Transaction,
    TransactionStatus,
    TransactionType,
)
from app.models.user import User  # noqa: E402
from app.models.wallet import Wallet  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed local development database.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate all tables before seeding.",
    )
    return parser.parse_args()


def _reset_db() -> None:
    print("Dropping all tables...")
    db.drop_all()
    print("Recreating all tables...")
    db.create_all()
    print("✓ Tables reset.")


def _seed_user() -> User:
    demo_email = "demo@auraxis.com"
    existing = User.query.filter_by(email=demo_email).first()
    if existing:
        print(f"  Demo user already exists (id={existing.id}), skipping.")
        return existing

    user = User(
        name="Demo Auraxis",
        email=demo_email,
        password=generate_password_hash("Demo@1234"),
        monthly_income_net=Decimal("8500.00"),
    )
    db.session.add(user)
    db.session.flush()  # populate id before returning
    print(f"✓ Criado: Usuário '{user.name}' ({user.email})")
    return user


def _seed_tags(user_id: object) -> list[Tag]:
    tag_names = ["Alimentação", "Transporte", "Saúde", "Lazer", "Moradia"]
    tags: list[Tag] = []
    for name in tag_names:
        tag = Tag(user_id=user_id, name=name)
        db.session.add(tag)
        tags.append(tag)
        print(f"✓ Criado: Tag '{name}'")
    db.session.flush()
    return tags


def _seed_accounts(user_id: object) -> list[Account]:
    account_names = ["Conta Corrente", "Conta Poupança", "Conta Investimentos"]
    accounts: list[Account] = []
    for name in account_names:
        account = Account(user_id=user_id, name=name)
        db.session.add(account)
        accounts.append(account)
        print(f"✓ Criado: Conta '{name}'")
    db.session.flush()
    return accounts


def _seed_credit_cards(user_id: object) -> list[CreditCard]:
    card_names = ["Cartão Nubank", "Cartão Inter"]
    cards: list[CreditCard] = []
    for name in card_names:
        card = CreditCard(user_id=user_id, name=name)
        db.session.add(card)
        cards.append(card)
        print(f"✓ Criado: Cartão '{name}'")
    db.session.flush()
    return cards


def _seed_transactions(
    user_id: object,
    tags: list[Tag],
    accounts: list[Account],
) -> list[Transaction]:
    """Create 24 transactions: 12 income + 12 expense, one pair per month."""
    today = date.today()
    transactions: list[Transaction] = []

    expense_data = [
        ("Aluguel", Decimal("1800.00"), "Moradia"),
        ("Mercado", Decimal("850.00"), "Alimentação"),
        ("Gasolina", Decimal("320.00"), "Transporte"),
        ("Academia", Decimal("120.00"), "Saúde"),
        ("Streaming", Decimal("55.00"), "Lazer"),
        ("Farmácia", Decimal("200.00"), "Saúde"),
        ("Restaurante", Decimal("280.00"), "Alimentação"),
        ("Uber", Decimal("180.00"), "Transporte"),
        ("Aluguel", Decimal("1800.00"), "Moradia"),
        ("Supermercado", Decimal("920.00"), "Alimentação"),
        ("Plano de Saúde", Decimal("450.00"), "Saúde"),
        ("Cinema", Decimal("95.00"), "Lazer"),
    ]

    tag_by_name = {tag.name: tag for tag in tags}

    # Build a lookup with fallback for accented names
    def _find_tag(name: str) -> Tag:
        return tag_by_name.get(name, tags[0])

    for i in range(12):
        # Calculate month offset: start 11 months ago up to current month
        month_offset = 11 - i
        # Compute the first day of the target month
        target_month_first = date(today.year, today.month, 1) - timedelta(
            days=month_offset * 30
        )
        # Normalise to actual first-of-month
        due_date = date(target_month_first.year, target_month_first.month, 5)

        # Income transaction (salary)
        income = Transaction(
            user_id=user_id,
            title="Salário",
            amount=Decimal("8500.00"),
            type=TransactionType.INCOME,
            status=TransactionStatus.PAID,
            due_date=due_date,
            tag_id=_find_tag("Alimentação").id,
            account_id=accounts[0].id,
        )
        db.session.add(income)
        transactions.append(income)
        print(f"✓ Criado: Transação 'Salário' ({due_date.strftime('%Y-%m')})")

        # Expense transaction (rotated from expense_data list)
        expense_title, expense_amount, expense_tag_name = expense_data[i]
        expense_tag = _find_tag(expense_tag_name)
        expense = Transaction(
            user_id=user_id,
            title=expense_title,
            amount=expense_amount,
            type=TransactionType.EXPENSE,
            status=TransactionStatus.PAID,
            due_date=due_date,
            tag_id=expense_tag.id,
            account_id=accounts[0].id,
        )
        db.session.add(expense)
        transactions.append(expense)
        month_str = due_date.strftime("%Y-%m")
        print(
            f"✓ Criado: Transação '{expense_title}' R$ {expense_amount} ({month_str})"
        )

    db.session.flush()
    return transactions


def _seed_goals(user_id: object) -> list[Goal]:
    goals_data = [
        {
            "title": "Reserva de Emergência",
            "target_amount": Decimal("30000.00"),
            "current_amount": Decimal("12000.00"),
            "target_date": date.today() + timedelta(days=365),
            "status": "active",
        },
        {
            "title": "Viagem Europa",
            "target_amount": Decimal("15000.00"),
            "current_amount": Decimal("3000.00"),
            "target_date": date.today() + timedelta(days=548),
            "status": "active",
        },
        {
            "title": "Notebook Novo",
            "target_amount": Decimal("5000.00"),
            "current_amount": Decimal("4800.00"),
            "target_date": date.today() + timedelta(days=60),
            "status": "active",
        },
    ]

    goals: list[Goal] = []
    for data in goals_data:
        goal = Goal(user_id=user_id, **data)
        db.session.add(goal)
        goals.append(goal)
        print(f"✓ Criado: Meta '{data['title']}' (alvo R$ {data['target_amount']})")

    db.session.flush()
    return goals


def _seed_wallet(user_id: object) -> list[Wallet]:
    today = date.today()
    entries_data = [
        {
            "name": "PETR4",
            "ticker": "PETR4",
            "quantity": 100,
            "value": None,
            "asset_class": "stock",
            "should_be_on_wallet": True,
        },
        {
            "name": "MXRF11",
            "ticker": "MXRF11",
            "quantity": 200,
            "value": None,
            "asset_class": "fii",
            "should_be_on_wallet": True,
        },
        {
            "name": "CDB Banco Inter",
            "ticker": None,
            "quantity": None,
            "value": Decimal("10000.00"),
            "asset_class": "cdb",
            "should_be_on_wallet": True,
        },
        {
            "name": "Bitcoin",
            "ticker": "BTC",
            "quantity": 1,
            "value": None,
            "asset_class": "crypto",
            "should_be_on_wallet": True,
        },
    ]

    entries: list[Wallet] = []
    for data in entries_data:
        entry = Wallet(
            user_id=user_id,
            name=data["name"],
            ticker=data["ticker"],
            quantity=data["quantity"],
            value=data["value"],
            asset_class=data["asset_class"],
            should_be_on_wallet=data["should_be_on_wallet"],
            register_date=today,
        )
        db.session.add(entry)
        entries.append(entry)
        print(f"✓ Criado: Carteira '{data['name']}' ({data['asset_class']})")

    db.session.flush()
    return entries


def run_seed(reset: bool = False) -> None:
    app = create_app(enable_http_runtime=False)

    with app.app_context():
        try:
            if reset:
                _reset_db()

            print("\n--- Seeding demo data ---\n")

            user = _seed_user()
            tags = _seed_tags(user.id)
            accounts = _seed_accounts(user.id)
            _seed_credit_cards(user.id)
            transactions = _seed_transactions(user.id, tags, accounts)
            goals = _seed_goals(user.id)
            wallet_entries = _seed_wallet(user.id)

            db.session.commit()

            print("\n--- Seed concluído com sucesso ---\n")
            print("  Usuários:     1")
            print(f"  Tags:         {len(tags)}")
            print(f"  Contas:       {len(accounts)}")
            print("  Cartões:      2")
            print(f"  Transações:   {len(transactions)}")
            print(f"  Metas:        {len(goals)}")
            print(f"  Carteira:     {len(wallet_entries)}")
            print()

        except Exception as exc:
            db.session.rollback()
            print(f"\n[ERRO] Seed falhou: {exc}", file=sys.stderr)
            raise


if __name__ == "__main__":
    args = _parse_args()
    run_seed(reset=args.reset)
