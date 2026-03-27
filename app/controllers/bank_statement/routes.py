from __future__ import annotations

from .blueprint import bank_statement_bp
from .resources import confirm_bank_statement, preview_bank_statement

_ROUTES_REGISTERED = False


def register_bank_statement_routes() -> None:
    global _ROUTES_REGISTERED
    if _ROUTES_REGISTERED:
        return

    bank_statement_bp.add_url_rule(
        "/preview",
        view_func=preview_bank_statement,
        methods=["POST"],
    )
    bank_statement_bp.add_url_rule(
        "/confirm",
        view_func=confirm_bank_statement,
        methods=["POST"],
    )

    _ROUTES_REGISTERED = True


register_bank_statement_routes()
