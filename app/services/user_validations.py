from datetime import date

from app.models.user import User


def _validate_dates(user: User) -> list[str]:
    errors: list[str] = []
    if user.birth_date:
        if not isinstance(user.birth_date, date):
            errors.append("Data de nascimento inválida.")
        elif user.birth_date > date.today():
            errors.append("Data de nascimento não pode ser no futuro.")

    if user.investment_goal_date:
        if not isinstance(user.investment_goal_date, date):
            errors.append("Data de meta de investimento inválida.")
        elif user.investment_goal_date < date.today():
            errors.append("Data limite de investimento deve ser futura.")
    return errors


def _validate_non_negative_values(user: User) -> list[str]:
    errors: list[str] = []
    for field_name in [
        "monthly_income",
        "net_worth",
        "monthly_expenses",
        "initial_investment",
        "monthly_investment",
    ]:
        value = getattr(user, field_name)
        if value is not None and value < 0:
            errors.append(
                f"{field_name.replace('_', ' ').capitalize()} "
                f"não pode ser negativo."
            )
    return errors


def _validate_financial_coherence(user: User) -> list[str]:
    errors: list[str] = []
    monthly_income = getattr(user, "monthly_income", None)
    monthly_expenses = getattr(user, "monthly_expenses", None)
    monthly_investment = getattr(user, "monthly_investment", None)
    net_worth = getattr(user, "net_worth", None)
    initial_investment = getattr(user, "initial_investment", None)

    if (
        monthly_income is not None
        and monthly_expenses is not None
        and monthly_expenses > monthly_income
    ):
        errors.append("Gastos mensais não podem ser maiores que a renda mensal.")

    if (
        monthly_income is not None
        and monthly_expenses is not None
        and monthly_investment is not None
        and monthly_investment > (monthly_income - monthly_expenses)
    ):
        errors.append(
            "Investimento mensal não pode ser maior que a capacidade "
            "de aporte (renda - gastos)."
        )

    if (
        net_worth is not None
        and initial_investment is not None
        and initial_investment > net_worth
    ):
        errors.append(
            "Investimento inicial não pode ser maior que o patrimônio líquido."
        )
    return errors


def _validate_gender(user: User) -> list[str]:
    if user.gender and user.gender.lower() not in ["masculino", "feminino", "outro"]:
        return ["Gênero deve ser 'masculino', 'feminino' ou 'outro'."]
    return []


def validate_user_profile_data(user: User) -> list[str]:
    errors: list[str] = []
    errors.extend(_validate_dates(user))
    errors.extend(_validate_non_negative_values(user))
    errors.extend(_validate_financial_coherence(user))
    errors.extend(_validate_gender(user))
    return errors
