from __future__ import annotations

from app.models.subscription import Subscription
from app.models.user import User
from app.services.email_provider import EmailMessage, get_default_email_provider

_PAYMENT_CONFIRMED_EVENTS = {"PAYMENT_RECEIVED", "PAYMENT_CONFIRMED"}
_PAYMENT_FAILED_EVENTS = {"PAYMENT_OVERDUE", "subscription.past_due"}
_CANCELED_EVENTS = {"subscription.canceled", "SUBSCRIPTION_DELETED"}


def _plan_label(subscription: Subscription) -> str:
    if subscription.billing_cycle is None:
        return str(subscription.plan_code)
    return f"{subscription.plan_code} {str(subscription.billing_cycle.value)}"


def dispatch_billing_email(
    *, user: User, subscription: Subscription, event_type: str
) -> None:
    provider = get_default_email_provider()
    plan_label = _plan_label(subscription)

    if event_type in _PAYMENT_CONFIRMED_EVENTS:
        provider.send(
            EmailMessage(
                to_email=str(user.email),
                subject="Pagamento confirmado na Auraxis",
                html=(
                    "<p>Seu pagamento foi confirmado com sucesso.</p>"
                    f"<p>Plano ativo: <strong>{plan_label}</strong></p>"
                ),
                text=(
                    "Seu pagamento foi confirmado com sucesso. "
                    f"Plano ativo: {plan_label}."
                ),
                tag="billing_payment_confirmed",
            )
        )
        return

    if event_type in _PAYMENT_FAILED_EVENTS:
        provider.send(
            EmailMessage(
                to_email=str(user.email),
                subject="Pagamento pendente na Auraxis",
                html=(
                    "<p>Identificamos uma pendencia no pagamento da sua assinatura.</p>"
                    f"<p>Plano impactado: <strong>{plan_label}</strong></p>"
                ),
                text=(
                    "Identificamos uma pendencia no pagamento da sua assinatura. "
                    f"Plano impactado: {plan_label}."
                ),
                tag="billing_payment_failed",
            )
        )
        return

    if event_type in _CANCELED_EVENTS:
        provider.send(
            EmailMessage(
                to_email=str(user.email),
                subject="Assinatura cancelada na Auraxis",
                html=(
                    "<p>Sua assinatura foi cancelada.</p>"
                    f"<p>Plano anterior: <strong>{plan_label}</strong></p>"
                ),
                text=(f"Sua assinatura foi cancelada. Plano anterior: {plan_label}."),
                tag="billing_subscription_canceled",
            )
        )
