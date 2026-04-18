from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.subscription import Subscription
    from app.models.user import User

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
    from app.services.outbound_queue import get_default_outbound_queue

    plan_label = _plan_label(subscription)
    to_email = str(user.email)

    if event_type in _PAYMENT_CONFIRMED_EVENTS:
        get_default_outbound_queue().enqueue_send_email(
            to_email=to_email,
            subject="Pagamento confirmado na Auraxis",
            html=(
                "<p>Seu pagamento foi confirmado com sucesso.</p>"
                f"<p>Plano ativo: <strong>{plan_label}</strong></p>"
            ),
            text=(
                f"Seu pagamento foi confirmado com sucesso. Plano ativo: {plan_label}."
            ),
            tag="billing_payment_confirmed",
        )
        return

    if event_type in _PAYMENT_FAILED_EVENTS:
        get_default_outbound_queue().enqueue_send_email(
            to_email=to_email,
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
        return

    if event_type in _CANCELED_EVENTS:
        get_default_outbound_queue().enqueue_send_email(
            to_email=to_email,
            subject="Assinatura cancelada na Auraxis",
            html=(
                "<p>Sua assinatura foi cancelada.</p>"
                f"<p>Plano anterior: <strong>{plan_label}</strong></p>"
            ),
            text=(f"Sua assinatura foi cancelada. Plano anterior: {plan_label}."),
            tag="billing_subscription_canceled",
        )
