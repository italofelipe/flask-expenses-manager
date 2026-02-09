from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

import graphene
from dateutil.relativedelta import relativedelta
from flask_jwt_extended import create_access_token, get_jti
from graphql import GraphQLError
from werkzeug.security import check_password_hash, generate_password_hash

from app.controllers.transaction_controller import (
    _build_installment_amounts,
    _validate_recurring_payload,
    serialize_transaction,
)
from app.controllers.user_controller import assign_user_profile_fields
from app.extensions.database import db
from app.graphql.auth import get_current_user_required
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User
from app.models.user_ticker import UserTicker
from app.models.wallet import Wallet
from app.services.investment_service import InvestmentService
from app.services.transaction_analytics_service import TransactionAnalyticsService


def _to_float_or_none(value: Any) -> float | None:
    return float(value) if value is not None else None


def _parse_optional_date(value: str | None, field_name: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise GraphQLError(
            f"Parâmetro '{field_name}' inválido. Use o formato YYYY-MM-DD."
        ) from exc


def _parse_month(month: str) -> tuple[int, int]:
    try:
        year, month_number = map(int, month.split("-"))
    except ValueError as exc:
        raise GraphQLError("Formato de mês inválido. Use YYYY-MM.") from exc
    if month_number < 1 or month_number > 12:
        raise GraphQLError("Formato de mês inválido. Use YYYY-MM.")
    return year, month_number


def _wallet_to_graphql_payload(wallet: Wallet) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(wallet.id),
        "name": wallet.name,
        "value": float(wallet.value) if wallet.value is not None else None,
        "estimated_value_on_create_date": (
            float(wallet.estimated_value_on_create_date)
            if wallet.estimated_value_on_create_date is not None
            else None
        ),
        "ticker": wallet.ticker,
        "quantity": wallet.quantity,
        "register_date": wallet.register_date.isoformat(),
        "target_withdraw_date": (
            wallet.target_withdraw_date.isoformat()
            if wallet.target_withdraw_date
            else None
        ),
        "should_be_on_wallet": wallet.should_be_on_wallet,
    }
    if payload["ticker"] is None:
        payload.pop("estimated_value_on_create_date", None)
        payload.pop("ticker", None)
        payload.pop("quantity", None)
    else:
        payload.pop("value", None)
    return payload


def _user_to_graphql_payload(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "gender": user.gender,
        "birth_date": user.birth_date.isoformat() if user.birth_date else None,
        "monthly_income": _to_float_or_none(user.monthly_income),
        "net_worth": _to_float_or_none(user.net_worth),
        "monthly_expenses": _to_float_or_none(user.monthly_expenses),
        "initial_investment": _to_float_or_none(user.initial_investment),
        "monthly_investment": _to_float_or_none(user.monthly_investment),
        "investment_goal_date": (
            user.investment_goal_date.isoformat() if user.investment_goal_date else None
        ),
    }


def _user_basic_auth_payload(user: User) -> dict[str, str]:
    return {"id": str(user.id), "name": user.name, "email": user.email}


def _paginate(total: int, page: int, per_page: int) -> PaginationType:
    pages = (total + per_page - 1) // per_page if total else 0
    return PaginationType(total=total, page=page, per_page=per_page, pages=pages)


def _serialize_transaction_items(
    transactions: list[Transaction],
) -> list[TransactionTypeObject]:
    return [
        TransactionTypeObject(**serialize_transaction(item)) for item in transactions
    ]


def _apply_type_filter(query: Any, raw_type: str | None) -> Any:
    if not raw_type:
        return query
    try:
        return query.filter(Transaction.type == TransactionType(raw_type.lower()))
    except ValueError as exc:
        raise GraphQLError(
            "Parâmetro 'type' inválido. Use 'income' ou 'expense'."
        ) from exc


def _apply_status_filter(query: Any, raw_status: str | None) -> Any:
    if not raw_status:
        return query
    try:
        return query.filter(Transaction.status == TransactionStatus(raw_status.lower()))
    except ValueError as exc:
        raise GraphQLError(
            "Parâmetro 'status' inválido. "
            "Use paid, pending, cancelled, postponed ou overdue."
        ) from exc


def _apply_due_date_range_filter(
    query: Any,
    start_date: str | None,
    end_date: str | None,
) -> Any:
    parsed_start_date = _parse_optional_date(start_date, "start_date")
    parsed_end_date = _parse_optional_date(end_date, "end_date")
    if parsed_start_date and parsed_end_date and parsed_start_date > parsed_end_date:
        raise GraphQLError("Parâmetro 'start_date' não pode ser maior que 'end_date'.")
    if parsed_start_date:
        query = query.filter(Transaction.due_date >= parsed_start_date)
    if parsed_end_date:
        query = query.filter(Transaction.due_date <= parsed_end_date)
    return query


def _get_owned_wallet_or_error(
    investment_id: UUID,
    user_id: UUID,
    *,
    forbidden_message: str,
) -> Wallet:
    investment = cast(Wallet | None, Wallet.query.filter_by(id=investment_id).first())
    if not investment:
        raise GraphQLError("Investimento não encontrado")
    if str(investment.user_id) != str(user_id):
        raise GraphQLError(forbidden_message)
    return investment


class UserType(graphene.ObjectType):
    id = graphene.ID(required=True)
    name = graphene.String(required=True)
    email = graphene.String(required=True)
    gender = graphene.String()
    birth_date = graphene.String()
    monthly_income = graphene.Float()
    net_worth = graphene.Float()
    monthly_expenses = graphene.Float()
    initial_investment = graphene.Float()
    monthly_investment = graphene.Float()
    investment_goal_date = graphene.String()


class AuthPayloadType(graphene.ObjectType):
    token = graphene.String()
    user = graphene.Field(UserType)
    message = graphene.String(required=True)


class TransactionTypeObject(graphene.ObjectType):
    id = graphene.ID(required=True)
    title = graphene.String(required=True)
    amount = graphene.String(required=True)
    type = graphene.String(required=True)
    due_date = graphene.String(required=True)
    start_date = graphene.String()
    end_date = graphene.String()
    description = graphene.String()
    observation = graphene.String()
    is_recurring = graphene.Boolean(required=True)
    is_installment = graphene.Boolean(required=True)
    installment_count = graphene.Int()
    tag_id = graphene.String()
    account_id = graphene.String()
    credit_card_id = graphene.String()
    status = graphene.String(required=True)
    currency = graphene.String(required=True)
    created_at = graphene.String()
    updated_at = graphene.String()


class PaginationType(graphene.ObjectType):
    total = graphene.Int(required=True)
    page = graphene.Int(required=True)
    per_page = graphene.Int(required=True)
    pages = graphene.Int()


class TransactionListPayloadType(graphene.ObjectType):
    items = graphene.List(TransactionTypeObject, required=True)
    pagination = graphene.Field(PaginationType, required=True)


class TransactionSummaryPayloadType(graphene.ObjectType):
    month = graphene.String(required=True)
    income_total = graphene.Float(required=True)
    expense_total = graphene.Float(required=True)
    items = graphene.List(TransactionTypeObject, required=True)
    pagination = graphene.Field(PaginationType, required=True)


class DashboardStatusCountsType(graphene.ObjectType):
    paid = graphene.Int(required=True)
    pending = graphene.Int(required=True)
    cancelled = graphene.Int(required=True)
    postponed = graphene.Int(required=True)
    overdue = graphene.Int(required=True)


class DashboardCountsType(graphene.ObjectType):
    total_transactions = graphene.Int(required=True)
    income_transactions = graphene.Int(required=True)
    expense_transactions = graphene.Int(required=True)
    status = graphene.Field(DashboardStatusCountsType, required=True)


class DashboardTotalsType(graphene.ObjectType):
    income_total = graphene.Float(required=True)
    expense_total = graphene.Float(required=True)
    balance = graphene.Float(required=True)


class DashboardCategoryType(graphene.ObjectType):
    tag_id = graphene.String()
    category_name = graphene.String(required=True)
    total_amount = graphene.Float(required=True)
    transactions_count = graphene.Int(required=True)


class DashboardCategoriesType(graphene.ObjectType):
    expense = graphene.List(DashboardCategoryType, required=True)
    income = graphene.List(DashboardCategoryType, required=True)


class TransactionDashboardPayloadType(graphene.ObjectType):
    month = graphene.String(required=True)
    totals = graphene.Field(DashboardTotalsType, required=True)
    counts = graphene.Field(DashboardCountsType, required=True)
    top_categories = graphene.Field(DashboardCategoriesType, required=True)


class WalletType(graphene.ObjectType):
    id = graphene.ID(required=True)
    name = graphene.String(required=True)
    value = graphene.Float()
    estimated_value_on_create_date = graphene.Float()
    ticker = graphene.String()
    quantity = graphene.Int()
    register_date = graphene.String(required=True)
    target_withdraw_date = graphene.String()
    should_be_on_wallet = graphene.Boolean(required=True)


class WalletHistoryItemType(graphene.ObjectType):
    original_quantity = graphene.Float()
    original_value = graphene.Float()
    change_type = graphene.String()
    change_date = graphene.String()


class WalletHistoryPayloadType(graphene.ObjectType):
    items = graphene.List(WalletHistoryItemType, required=True)
    pagination = graphene.Field(PaginationType, required=True)


class WalletListPayloadType(graphene.ObjectType):
    items = graphene.List(WalletType, required=True)
    pagination = graphene.Field(PaginationType, required=True)


class TickerType(graphene.ObjectType):
    id = graphene.ID(required=True)
    symbol = graphene.String(required=True)
    quantity = graphene.Float(required=True)
    type = graphene.String()


class Query(graphene.ObjectType):
    me = graphene.Field(UserType)
    transactions = graphene.Field(
        TransactionListPayloadType,
        page=graphene.Int(default_value=1),
        per_page=graphene.Int(default_value=10),
        type=graphene.String(),
        status=graphene.String(),
        start_date=graphene.String(),
        end_date=graphene.String(),
    )
    transaction_summary = graphene.Field(
        TransactionSummaryPayloadType,
        month=graphene.String(required=True),
        page=graphene.Int(default_value=1),
        page_size=graphene.Int(default_value=10),
    )
    transaction_dashboard = graphene.Field(
        TransactionDashboardPayloadType, month=graphene.String(required=True)
    )
    wallet_entries = graphene.Field(
        WalletListPayloadType,
        page=graphene.Int(default_value=1),
        per_page=graphene.Int(default_value=10),
    )
    wallet_history = graphene.Field(
        WalletHistoryPayloadType,
        investment_id=graphene.UUID(required=True),
        page=graphene.Int(default_value=1),
        per_page=graphene.Int(default_value=5),
    )
    tickers = graphene.List(TickerType)

    def resolve_me(self, info: graphene.ResolveInfo) -> UserType:
        user = get_current_user_required()
        return UserType(**_user_to_graphql_payload(user))

    def resolve_transactions(
        self,
        info: graphene.ResolveInfo,
        page: int,
        per_page: int,
        type: str | None = None,
        status: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> TransactionListPayloadType:
        user = get_current_user_required()
        query = Transaction.query.filter_by(user_id=user.id, deleted=False)
        query = _apply_type_filter(query, type)
        query = _apply_status_filter(query, status)
        query = _apply_due_date_range_filter(query, start_date, end_date)

        total = query.count()
        items = (
            query.order_by(Transaction.due_date.desc(), Transaction.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return TransactionListPayloadType(
            items=_serialize_transaction_items(items),
            pagination=_paginate(total=total, page=page, per_page=per_page),
        )

    def resolve_transaction_summary(
        self,
        info: graphene.ResolveInfo,
        month: str,
        page: int,
        page_size: int,
    ) -> TransactionSummaryPayloadType:
        user = get_current_user_required()
        year, month_number = _parse_month(month)
        analytics = TransactionAnalyticsService(user.id)
        transactions = analytics.get_month_transactions(
            year=year, month_number=month_number
        )
        aggregates = analytics.get_month_aggregates(
            year=year, month_number=month_number
        )

        total = len(transactions)
        start = (page - 1) * page_size
        end = start + page_size
        paged_items = transactions[start:end]
        return TransactionSummaryPayloadType(
            month=month,
            income_total=float(aggregates["income_total"]),
            expense_total=float(aggregates["expense_total"]),
            items=_serialize_transaction_items(paged_items),
            pagination=_paginate(total=total, page=page, per_page=page_size),
        )

    def resolve_transaction_dashboard(
        self, info: graphene.ResolveInfo, month: str
    ) -> TransactionDashboardPayloadType:
        user = get_current_user_required()
        year, month_number = _parse_month(month)
        analytics = TransactionAnalyticsService(user.id)
        aggregates = analytics.get_month_aggregates(
            year=year, month_number=month_number
        )
        status_counts = analytics.get_status_counts(
            year=year, month_number=month_number
        )
        top_expense = analytics.get_top_categories(
            year=year,
            month_number=month_number,
            transaction_type=TransactionType.EXPENSE,
        )
        top_income = analytics.get_top_categories(
            year=year,
            month_number=month_number,
            transaction_type=TransactionType.INCOME,
        )

        return TransactionDashboardPayloadType(
            month=month,
            totals=DashboardTotalsType(
                income_total=float(aggregates["income_total"]),
                expense_total=float(aggregates["expense_total"]),
                balance=float(aggregates["balance"]),
            ),
            counts=DashboardCountsType(
                total_transactions=aggregates["total_transactions"],
                income_transactions=aggregates["income_transactions"],
                expense_transactions=aggregates["expense_transactions"],
                status=DashboardStatusCountsType(
                    paid=status_counts["paid"],
                    pending=status_counts["pending"],
                    cancelled=status_counts["cancelled"],
                    postponed=status_counts["postponed"],
                    overdue=status_counts["overdue"],
                ),
            ),
            top_categories=DashboardCategoriesType(
                expense=[DashboardCategoryType(**item) for item in top_expense],
                income=[DashboardCategoryType(**item) for item in top_income],
            ),
        )

    def resolve_wallet_entries(
        self, info: graphene.ResolveInfo, page: int, per_page: int
    ) -> WalletListPayloadType:
        user = get_current_user_required()
        pagination = (
            Wallet.query.filter_by(user_id=user.id)
            .order_by(Wallet.created_at.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
        items = [
            WalletType(**_wallet_to_graphql_payload(item)) for item in pagination.items
        ]
        return WalletListPayloadType(
            items=items,
            pagination=_paginate(
                total=pagination.total,
                page=pagination.page,
                per_page=pagination.per_page,
            ),
        )

    def resolve_wallet_history(
        self,
        info: graphene.ResolveInfo,
        investment_id: UUID,
        page: int,
        per_page: int,
    ) -> WalletHistoryPayloadType:
        user = get_current_user_required()
        investment = _get_owned_wallet_or_error(
            investment_id,
            user.id,
            forbidden_message=(
                "Você não tem permissão para ver o histórico deste investimento."
            ),
        )

        history = investment.history or []
        sorted_history = sorted(
            history,
            key=lambda item: (
                item.get("originalQuantity", 0) or 0,
                item.get("changeDate", ""),
            ),
            reverse=True,
        )
        total = len(sorted_history)
        if per_page <= 0:
            items = sorted_history
            current_per_page = total or 1
            current_page = 1
        else:
            start = (page - 1) * per_page
            end = start + per_page
            items = sorted_history[start:end]
            current_page = page
            current_per_page = per_page

        pages = (
            (total + current_per_page - 1) // current_per_page
            if current_per_page and total
            else 0
        )
        mapped_items = [
            WalletHistoryItemType(
                original_quantity=item.get("originalQuantity"),
                original_value=item.get("originalValue"),
                change_type=item.get("changeType"),
                change_date=item.get("changeDate"),
            )
            for item in items
        ]
        return WalletHistoryPayloadType(
            items=mapped_items,
            pagination=PaginationType(
                total=total, page=current_page, per_page=current_per_page, pages=pages
            ),
        )

    def resolve_tickers(self, info: graphene.ResolveInfo) -> list[TickerType]:
        user = get_current_user_required()
        tickers = UserTicker.query.filter_by(user_id=user.id).all()
        return [
            TickerType(
                id=str(item.id),
                symbol=item.symbol,
                quantity=item.quantity,
                type=item.type,
            )
            for item in tickers
        ]


class RegisterUserMutation(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        email = graphene.String(required=True)
        password = graphene.String(required=True)

    Output = AuthPayloadType

    def mutate(
        self, info: graphene.ResolveInfo, name: str, email: str, password: str
    ) -> AuthPayloadType:
        if User.query.filter_by(email=email).first():
            raise GraphQLError("Email already registered")

        user = User(name=name, email=email, password=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        return AuthPayloadType(
            message="User created successfully",
            user=UserType(**_user_basic_auth_payload(user)),
        )


class LoginMutation(graphene.Mutation):
    class Arguments:
        email = graphene.String()
        name = graphene.String()
        password = graphene.String(required=True)

    Output = AuthPayloadType

    def mutate(
        self,
        info: graphene.ResolveInfo,
        password: str,
        email: str | None = None,
        name: str | None = None,
    ) -> AuthPayloadType:
        if not (email or name):
            raise GraphQLError("Missing credentials")
        user = (
            User.query.filter_by(email=email).first()
            if email
            else User.query.filter_by(name=name).first()
        )
        if not user or not check_password_hash(user.password, password):
            raise GraphQLError("Invalid credentials")

        token = create_access_token(
            identity=str(user.id), expires_delta=timedelta(hours=1)
        )
        jti = get_jti(token)
        if user.current_jti != jti:
            user.current_jti = jti
            db.session.commit()
        return AuthPayloadType(
            message="Login successful",
            token=token,
            user=UserType(**_user_basic_auth_payload(user)),
        )


class LogoutMutation(graphene.Mutation):
    ok = graphene.Boolean(required=True)
    message = graphene.String(required=True)

    def mutate(self, info: graphene.ResolveInfo) -> LogoutMutation:
        user = get_current_user_required()
        user.current_jti = None
        db.session.commit()
        return LogoutMutation(ok=True, message="Logout successful")


class UpdateUserProfileMutation(graphene.Mutation):
    class Arguments:
        gender = graphene.String()
        birth_date = graphene.String()
        monthly_income = graphene.Float()
        net_worth = graphene.Float()
        monthly_expenses = graphene.Float()
        initial_investment = graphene.Float()
        monthly_investment = graphene.Float()
        investment_goal_date = graphene.String()

    user = graphene.Field(UserType, required=True)

    def mutate(
        self, info: graphene.ResolveInfo, **kwargs: Any
    ) -> UpdateUserProfileMutation:
        user = get_current_user_required()
        result = assign_user_profile_fields(user, kwargs)
        if result["error"]:
            raise GraphQLError(str(result["message"]))
        errors = user.validate_profile_data()
        if errors:
            raise GraphQLError(f"Erro de validação: {errors}")
        db.session.commit()
        return UpdateUserProfileMutation(
            user=UserType(**_user_to_graphql_payload(user))
        )


class CreateTransactionMutation(graphene.Mutation):
    class Arguments:
        title = graphene.String(required=True)
        amount = graphene.String(required=True)
        type = graphene.String(required=True)
        due_date = graphene.String(required=True)
        description = graphene.String()
        observation = graphene.String()
        is_recurring = graphene.Boolean(default_value=False)
        is_installment = graphene.Boolean(default_value=False)
        installment_count = graphene.Int()
        currency = graphene.String(default_value="BRL")
        status = graphene.String(default_value="pending")
        start_date = graphene.String()
        end_date = graphene.String()
        tag_id = graphene.UUID()
        account_id = graphene.UUID()
        credit_card_id = graphene.UUID()

    items = graphene.List(TransactionTypeObject, required=True)
    message = graphene.String(required=True)

    def mutate(
        self, info: graphene.ResolveInfo, **kwargs: Any
    ) -> CreateTransactionMutation:
        user = get_current_user_required()
        due_date = _parse_optional_date(kwargs.get("due_date"), "due_date")
        if due_date is None:
            raise GraphQLError("Parâmetro 'due_date' é obrigatório.")
        start_date = _parse_optional_date(kwargs.get("start_date"), "start_date")
        end_date = _parse_optional_date(kwargs.get("end_date"), "end_date")
        recurring_error = _validate_recurring_payload(
            is_recurring=bool(kwargs.get("is_recurring", False)),
            due_date=due_date,
            start_date=start_date,
            end_date=end_date,
        )
        if recurring_error:
            raise GraphQLError(recurring_error)

        tx_type = str(kwargs["type"]).lower()
        tx_status = str(kwargs.get("status", "pending")).lower()
        amount = Decimal(str(kwargs["amount"]))

        if kwargs.get("is_installment") and kwargs.get("installment_count"):
            count = int(kwargs["installment_count"])
            if count < 1:
                raise GraphQLError("'installment_count' deve ser maior que zero.")
            group_id = uuid4()
            installment_amounts = _build_installment_amounts(amount, count)
            created: list[Transaction] = []
            for idx in range(count):
                month_due_date = due_date + relativedelta(months=idx)
                created.append(
                    Transaction(
                        user_id=UUID(str(user.id)),
                        title=f"{kwargs['title']} ({idx + 1}/{count})",
                        amount=installment_amounts[idx],
                        type=TransactionType(tx_type),
                        due_date=month_due_date,
                        start_date=start_date,
                        end_date=end_date,
                        description=kwargs.get("description"),
                        observation=kwargs.get("observation"),
                        is_recurring=bool(kwargs.get("is_recurring", False)),
                        is_installment=True,
                        installment_count=count,
                        tag_id=kwargs.get("tag_id"),
                        account_id=kwargs.get("account_id"),
                        credit_card_id=kwargs.get("credit_card_id"),
                        status=TransactionStatus(tx_status),
                        currency=str(kwargs.get("currency", "BRL")),
                        installment_group_id=group_id,
                    )
                )
            db.session.add_all(created)
            db.session.commit()
            return CreateTransactionMutation(
                message="Transações parceladas criadas com sucesso",
                items=[
                    TransactionTypeObject(**serialize_transaction(item))
                    for item in created
                ],
            )

        transaction = Transaction(
            user_id=UUID(str(user.id)),
            title=kwargs["title"],
            amount=amount,
            type=TransactionType(tx_type),
            due_date=due_date,
            start_date=start_date,
            end_date=end_date,
            description=kwargs.get("description"),
            observation=kwargs.get("observation"),
            is_recurring=bool(kwargs.get("is_recurring", False)),
            is_installment=bool(kwargs.get("is_installment", False)),
            installment_count=kwargs.get("installment_count"),
            tag_id=kwargs.get("tag_id"),
            account_id=kwargs.get("account_id"),
            credit_card_id=kwargs.get("credit_card_id"),
            status=TransactionStatus(tx_status),
            currency=str(kwargs.get("currency", "BRL")),
        )
        db.session.add(transaction)
        db.session.commit()
        return CreateTransactionMutation(
            message="Transação criada com sucesso",
            items=[TransactionTypeObject(**serialize_transaction(transaction))],
        )


class DeleteTransactionMutation(graphene.Mutation):
    class Arguments:
        transaction_id = graphene.UUID(required=True)

    ok = graphene.Boolean(required=True)
    message = graphene.String(required=True)

    def mutate(
        self, info: graphene.ResolveInfo, transaction_id: UUID
    ) -> DeleteTransactionMutation:
        user = get_current_user_required()
        transaction = Transaction.query.filter_by(
            id=transaction_id, deleted=False
        ).first()
        if not transaction:
            raise GraphQLError("Transação não encontrada.")
        if str(transaction.user_id) != str(user.id):
            raise GraphQLError("Você não tem permissão para deletar esta transação.")
        transaction.deleted = True
        db.session.commit()
        return DeleteTransactionMutation(
            ok=True, message="Transação deletada com sucesso (soft delete)."
        )


class AddWalletEntryMutation(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        value = graphene.Float()
        ticker = graphene.String()
        quantity = graphene.Int()
        register_date = graphene.String()
        target_withdraw_date = graphene.String()
        should_be_on_wallet = graphene.Boolean(required=True)

    item = graphene.Field(WalletType, required=True)

    def mutate(
        self, info: graphene.ResolveInfo, **kwargs: Any
    ) -> AddWalletEntryMutation:
        user = get_current_user_required()
        validated_data = {
            "name": kwargs["name"],
            "value": kwargs.get("value"),
            "ticker": kwargs.get("ticker"),
            "quantity": kwargs.get("quantity"),
            "register_date": _parse_optional_date(
                kwargs.get("register_date"), "register_date"
            )
            or date.today(),
            "target_withdraw_date": _parse_optional_date(
                kwargs.get("target_withdraw_date"), "target_withdraw_date"
            ),
            "should_be_on_wallet": kwargs["should_be_on_wallet"],
        }
        estimated_value = InvestmentService.calculate_estimated_value(validated_data)
        wallet = Wallet(
            user_id=user.id,
            name=validated_data["name"],
            value=validated_data.get("value"),
            estimated_value_on_create_date=estimated_value,
            ticker=validated_data.get("ticker"),
            quantity=validated_data.get("quantity"),
            register_date=validated_data["register_date"],
            target_withdraw_date=validated_data.get("target_withdraw_date"),
            should_be_on_wallet=validated_data["should_be_on_wallet"],
        )
        db.session.add(wallet)
        db.session.commit()
        return AddWalletEntryMutation(
            item=WalletType(**_wallet_to_graphql_payload(wallet))
        )


class UpdateWalletEntryMutation(graphene.Mutation):
    class Arguments:
        investment_id = graphene.UUID(required=True)
        name = graphene.String()
        value = graphene.Float()
        ticker = graphene.String()
        quantity = graphene.Int()
        register_date = graphene.String()
        target_withdraw_date = graphene.String()
        should_be_on_wallet = graphene.Boolean()

    item = graphene.Field(WalletType, required=True)

    def mutate(
        self, info: graphene.ResolveInfo, investment_id: UUID, **kwargs: Any
    ) -> UpdateWalletEntryMutation:
        user = get_current_user_required()
        investment = _get_owned_wallet_or_error(
            investment_id,
            user.id,
            forbidden_message="Você não tem permissão para editar este investimento.",
        )

        original_quantity = investment.quantity
        original_value = investment.value
        for key in ["name", "ticker", "quantity", "should_be_on_wallet"]:
            if key in kwargs and kwargs[key] is not None:
                setattr(investment, key, kwargs[key])
        if "value" in kwargs and kwargs["value"] is not None:
            investment.value = Decimal(str(kwargs["value"]))
        if "register_date" in kwargs and kwargs["register_date"]:
            investment.register_date = _parse_optional_date(
                kwargs["register_date"], "register_date"
            )
        if "target_withdraw_date" in kwargs:
            investment.target_withdraw_date = _parse_optional_date(
                kwargs.get("target_withdraw_date"), "target_withdraw_date"
            )

        if investment.ticker:
            estimated_value = InvestmentService.calculate_estimated_value(
                {"ticker": investment.ticker, "quantity": investment.quantity}
            )
            investment.estimated_value_on_create_date = estimated_value

        if (
            original_quantity != investment.quantity
            or original_value != investment.value
        ):
            history = investment.history or []
            history.append(
                {
                    "originalQuantity": original_quantity,
                    "originalValue": (
                        float(original_value) if original_value is not None else None
                    ),
                    "newQuantity": investment.quantity,
                    "newValue": (
                        float(investment.value)
                        if investment.value is not None
                        else None
                    ),
                    "changeType": "update",
                    "changeDate": datetime.utcnow().isoformat(),
                }
            )
            investment.history = history

        db.session.commit()
        return UpdateWalletEntryMutation(
            item=WalletType(**_wallet_to_graphql_payload(investment))
        )


class DeleteWalletEntryMutation(graphene.Mutation):
    class Arguments:
        investment_id = graphene.UUID(required=True)

    ok = graphene.Boolean(required=True)
    message = graphene.String(required=True)

    def mutate(
        self, info: graphene.ResolveInfo, investment_id: UUID
    ) -> DeleteWalletEntryMutation:
        user = get_current_user_required()
        investment = _get_owned_wallet_or_error(
            investment_id,
            user.id,
            forbidden_message="Você não tem permissão para remover este investimento.",
        )
        db.session.delete(investment)
        db.session.commit()
        return DeleteWalletEntryMutation(
            ok=True, message="Investimento removido com sucesso"
        )


class AddTickerMutation(graphene.Mutation):
    class Arguments:
        symbol = graphene.String(required=True)
        quantity = graphene.Float(required=True)
        type = graphene.String()

    item = graphene.Field(TickerType, required=True)

    def mutate(
        self,
        info: graphene.ResolveInfo,
        symbol: str,
        quantity: float,
        type: str | None = None,
    ) -> AddTickerMutation:
        user = get_current_user_required()
        normalized_symbol = symbol.upper()
        exists = UserTicker.query.filter_by(
            user_id=user.id, symbol=normalized_symbol
        ).first()
        if exists:
            raise GraphQLError("Ticker já adicionado")
        ticker = UserTicker(
            symbol=normalized_symbol,
            quantity=quantity,
            type=type,
            user_id=user.id,
        )
        db.session.add(ticker)
        db.session.commit()
        return AddTickerMutation(
            item=TickerType(
                id=str(ticker.id),
                symbol=ticker.symbol,
                quantity=ticker.quantity,
                type=ticker.type,
            )
        )


class DeleteTickerMutation(graphene.Mutation):
    class Arguments:
        symbol = graphene.String(required=True)

    ok = graphene.Boolean(required=True)
    message = graphene.String(required=True)

    def mutate(self, info: graphene.ResolveInfo, symbol: str) -> DeleteTickerMutation:
        user = get_current_user_required()
        ticker = UserTicker.query.filter_by(
            user_id=user.id, symbol=symbol.upper()
        ).first()
        if not ticker:
            raise GraphQLError("Ticker não encontrado")
        db.session.delete(ticker)
        db.session.commit()
        return DeleteTickerMutation(ok=True, message="Ticker removido com sucesso")


class Mutation(graphene.ObjectType):
    register_user = RegisterUserMutation.Field()
    login = LoginMutation.Field()
    logout = LogoutMutation.Field()
    update_user_profile = UpdateUserProfileMutation.Field()
    create_transaction = CreateTransactionMutation.Field()
    delete_transaction = DeleteTransactionMutation.Field()
    add_wallet_entry = AddWalletEntryMutation.Field()
    update_wallet_entry = UpdateWalletEntryMutation.Field()
    delete_wallet_entry = DeleteWalletEntryMutation.Field()
    add_ticker = AddTickerMutation.Field()
    delete_ticker = DeleteTickerMutation.Field()


schema = graphene.Schema(query=Query, mutation=Mutation)
