from datetime import date

from app.models.user import User


def validate_user_profile_data(user: User) -> list[str]:
    errors = []

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

    if user.gender and user.gender.lower() not in ["masculino", "feminino", "outro"]:
        errors.append("Gênero deve ser 'masculino', 'feminino' ou 'outro'.")

    return errors
