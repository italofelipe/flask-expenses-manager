"""Unit tests for app/graphql/decorators.py."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from graphql import GraphQLError

from app.graphql.decorators import graphql_error_adapter, resolver_with_user_context

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@dataclass
class _FakeDomainError(Exception):
    message: str
    code: str


class _FakeService:
    def __init__(self, user_id: Any) -> None:
        self.user_id = user_id

    @classmethod
    def with_defaults(cls, user_id: Any) -> "_FakeService":
        return cls(user_id)

    def do_thing(self, value: int) -> int:
        return value * 2


class _FakeUser:
    def __init__(self) -> None:
        self.id = "00000000-0000-0000-0000-000000000001"


# ---------------------------------------------------------------------------
# resolver_with_user_context
# ---------------------------------------------------------------------------


class TestResolverWithUserContext:
    def test_injects_service_as_third_arg(self) -> None:
        captured: list[Any] = []

        @resolver_with_user_context(_FakeService)
        def my_resolver(root: Any, info: Any, service: _FakeService) -> None:
            captured.append(service)

        fake_user = _FakeUser()
        with patch(
            "app.graphql.decorators.resolver_with_user_context.__wrapped__", create=True
        ):
            with patch(
                "app.graphql.auth.get_current_user_required", return_value=fake_user
            ):
                my_resolver(None, MagicMock())

        assert len(captured) == 1
        assert isinstance(captured[0], _FakeService)

    def test_passes_args_through(self) -> None:
        received: list[Any] = []

        @resolver_with_user_context(_FakeService)
        def my_resolver(
            root: Any, info: Any, service: _FakeService, x: int, y: str
        ) -> None:
            received.extend([x, y])

        fake_user = _FakeUser()
        with patch(
            "app.graphql.auth.get_current_user_required", return_value=fake_user
        ):
            my_resolver(None, MagicMock(), 42, "hello")

        assert received == [42, "hello"]

    def test_raises_if_user_not_authenticated(self) -> None:
        @resolver_with_user_context(_FakeService)
        def my_resolver(root: Any, info: Any, service: _FakeService) -> None:
            pass

        with patch(
            "app.graphql.auth.get_current_user_required",
            side_effect=GraphQLError("Unauthorized"),
        ):
            with pytest.raises(GraphQLError):
                my_resolver(None, MagicMock())

    def test_service_user_id_is_set(self) -> None:
        captured_service: list[_FakeService] = []

        @resolver_with_user_context(_FakeService)
        def my_resolver(root: Any, info: Any, service: _FakeService) -> None:
            captured_service.append(service)

        fake_user = _FakeUser()
        with patch(
            "app.graphql.auth.get_current_user_required", return_value=fake_user
        ):
            my_resolver(None, MagicMock())

        from uuid import UUID

        assert captured_service[0].user_id == UUID(fake_user.id)

    def test_preserves_function_name(self) -> None:
        @resolver_with_user_context(_FakeService)
        def my_unique_resolver(root: Any, info: Any, service: _FakeService) -> None:
            pass

        assert my_unique_resolver.__name__ == "my_unique_resolver"


# ---------------------------------------------------------------------------
# graphql_error_adapter
# ---------------------------------------------------------------------------


class TestGraphQLErrorAdapter:
    def test_passes_through_on_success(self) -> None:
        @graphql_error_adapter(_FakeDomainError)
        def my_fn() -> str:
            return "ok"

        assert my_fn() == "ok"

    def test_converts_domain_exception(self) -> None:
        @graphql_error_adapter(_FakeDomainError)
        def my_fn() -> None:
            raise _FakeDomainError(message="Something went wrong", code="NOT_FOUND")

        with pytest.raises(GraphQLError) as exc_info:
            my_fn()

        # to_public_graphql_code maps NOT_FOUND to NOT_FOUND (known code)
        assert exc_info.value.extensions is not None
        assert exc_info.value.extensions.get("code") == "NOT_FOUND"

    def test_unknown_code_maps_to_validation_error(self) -> None:
        @graphql_error_adapter(_FakeDomainError)
        def my_fn() -> None:
            raise _FakeDomainError(message="oops", code="CUSTOM_UNKNOWN_CODE")

        with pytest.raises(GraphQLError) as exc_info:
            my_fn()

        assert exc_info.value.extensions is not None
        assert exc_info.value.extensions.get("code") == "VALIDATION_ERROR"

    def test_does_not_catch_unregistered_exceptions(self) -> None:
        @dataclass
        class OtherError(Exception):
            message: str

        @graphql_error_adapter(_FakeDomainError)
        def my_fn() -> None:
            raise OtherError(message="unregistered")

        with pytest.raises(OtherError):
            my_fn()

    def test_graphql_errors_pass_through_untouched(self) -> None:
        original = GraphQLError("already a gql error")

        @graphql_error_adapter(_FakeDomainError)
        def my_fn() -> None:
            raise original

        with pytest.raises(GraphQLError) as exc_info:
            my_fn()

        assert exc_info.value is original

    def test_custom_error_fn_is_called(self) -> None:
        called_with: list[Any] = []

        def my_error_fn(exc: _FakeDomainError) -> None:
            called_with.append(exc)
            raise GraphQLError("custom mapped error")

        @graphql_error_adapter(_FakeDomainError, error_fn=my_error_fn)
        def my_fn() -> None:
            raise _FakeDomainError(message="domain problem", code="CONFLICT")

        with pytest.raises(GraphQLError, match="custom mapped error"):
            my_fn()

        assert len(called_with) == 1
        assert called_with[0].message == "domain problem"

    def test_preserves_function_name(self) -> None:
        @graphql_error_adapter(_FakeDomainError)
        def my_unique_fn() -> None:
            pass

        assert my_unique_fn.__name__ == "my_unique_fn"

    def test_multiple_exception_types(self) -> None:
        @dataclass
        class ErrorA(Exception):
            message: str
            code: str

        @dataclass
        class ErrorB(Exception):
            message: str
            code: str

        @graphql_error_adapter(ErrorA, ErrorB)
        def my_fn(exc_type: type) -> None:
            raise exc_type(message="err", code="CONFLICT")

        for exc_type in (ErrorA, ErrorB):
            with pytest.raises(GraphQLError):
                my_fn(exc_type)
