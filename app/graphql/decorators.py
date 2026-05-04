"""GraphQL resolver decorators.

Two composable decorators eliminate the standard boilerplate found in ~23 resolvers:

    @resolver_with_user_context(ServiceClass)
        Gets the authenticated user from the request context, instantiates
        ``ServiceClass.with_defaults(user_id)``, and injects the service as
        the third positional argument (after ``self``/root and ``info``).

    @graphql_error_adapter(*exception_types)
        Catches any of the listed domain exceptions and re-raises them as
        ``GraphQLError`` via ``build_public_graphql_error``. The exception must
        expose ``.message`` and ``.code`` attributes (all ApplicationError
        subclasses do).

Usage (compose outermost → innermost, execution order is opposite):

    @log_graphql_resolver("deleteTransaction")          # 1st: logging
    @resolver_with_user_context(TransactionService)     # 2nd: auth + inject
    @graphql_error_adapter(TransactionApplicationError) # 3rd: error mapping
    def mutate(self, info, service, transaction_id):
        service.delete_transaction(transaction_id)
        return DeleteTransactionMutation(ok=True, message="Deleted.")

The resolver body shrinks from ~8 lines to 2-3, and auth is guaranteed by
construction rather than by convention.

For resolvers with custom error-code mappings (e.g. goal/wallet presenters),
pass ``error_fn`` with a callable that receives the exception and raises a
``GraphQLError``:

    @graphql_error_adapter(WalletApplicationError, error_fn=raise_wallet_graphql_error)
    def mutate(self, info, service, investment_id): ...
"""

from __future__ import annotations

import functools
from typing import Any, Callable, Type, TypeVar  # noqa: UP035
from uuid import UUID

from graphql import GraphQLError

from app.graphql.errors import build_public_graphql_error, to_public_graphql_code

F = TypeVar("F", bound=Callable[..., Any])


def resolver_with_user_context(service_class: Any) -> Callable[[F], F]:
    """Inject an authenticated service instance into a Graphene resolver.

    The wrapped resolver receives ``service`` as the third positional argument
    (after ``root`` and ``info``). ``get_current_user_required()`` is called
    inside the wrapper, so the resolver body can skip the auth boilerplate.
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(root: Any, info: Any, *args: Any, **kwargs: Any) -> Any:
            from app.graphql.auth import get_current_user_required

            user = get_current_user_required()
            service = service_class.with_defaults(UUID(str(user.id)))
            return fn(root, info, service, *args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def graphql_error_adapter(
    *exception_types: Type[Exception],
    error_fn: Callable[[Any], None] | None = None,
) -> Callable[[F], F]:
    """Convert domain exceptions into ``GraphQLError`` instances.

    Args:
        *exception_types: Domain exception classes to intercept.
        error_fn: Optional callable ``(exc) -> NoReturn`` for custom code-mapping
            (e.g. ``raise_wallet_graphql_error``). When omitted, the adapter
            calls ``build_public_graphql_error(exc.message, code=...)``.
    """
    exc_tuple = tuple(exception_types)

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return fn(*args, **kwargs)
            except GraphQLError:
                raise
            except exc_tuple as exc:
                if error_fn is not None:
                    error_fn(exc)
                message = getattr(exc, "message", str(exc))
                code = getattr(exc, "code", "VALIDATION_ERROR") or "VALIDATION_ERROR"
                raise build_public_graphql_error(
                    message,
                    code=to_public_graphql_code(code),
                ) from exc

        return wrapper  # type: ignore[return-value]

    return decorator
