from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, cast
from uuid import UUID

from flask import Flask, current_app

from app.application.services.transaction_application_service import (
    TransactionApplicationService,
)
from app.services.transaction_analytics_service import TransactionAnalyticsService

TRANSACTION_DEPENDENCIES_EXTENSION_KEY = "transaction_dependencies"


@dataclass(frozen=True)
class TransactionDependencies:
    """Container for transaction dependency factories."""

    analytics_service_factory: Callable[[UUID], TransactionAnalyticsService]
    transaction_application_service_factory: Callable[
        [UUID], TransactionApplicationService
    ]


def _analytics_service_factory(user_id: UUID) -> TransactionAnalyticsService:
    # Keep compatibility with legacy monkeypatch targets:
    # app.controllers.transaction.report_resources.TransactionAnalyticsService
    from . import report_resources as report_resources_module

    service_cls = getattr(
        report_resources_module,
        "TransactionAnalyticsService",
        TransactionAnalyticsService,
    )
    return cast(TransactionAnalyticsService, service_cls(user_id))


def _default_dependencies() -> TransactionDependencies:
    def _transaction_application_service_factory(
        user_id: UUID,
    ) -> TransactionApplicationService:
        return TransactionApplicationService(
            user_id=user_id,
            analytics_service_factory=_analytics_service_factory,
        )

    return TransactionDependencies(
        analytics_service_factory=_analytics_service_factory,
        transaction_application_service_factory=(
            _transaction_application_service_factory
        ),
    )


def register_transaction_dependencies(
    app: Flask,
    dependencies: TransactionDependencies | None = None,
) -> None:
    if dependencies is None:
        dependencies = _default_dependencies()
    app.extensions.setdefault(TRANSACTION_DEPENDENCIES_EXTENSION_KEY, dependencies)


def get_transaction_dependencies() -> TransactionDependencies:
    configured = current_app.extensions.get(TRANSACTION_DEPENDENCIES_EXTENSION_KEY)
    if isinstance(configured, TransactionDependencies):
        return configured
    fallback = _default_dependencies()
    current_app.extensions[TRANSACTION_DEPENDENCIES_EXTENSION_KEY] = fallback
    return fallback
