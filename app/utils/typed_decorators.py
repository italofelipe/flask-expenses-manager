from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TypeVar, cast

from flask_apispec import doc as apispec_doc
from flask_apispec import use_kwargs as apispec_use_kwargs
from flask_jwt_extended import jwt_required as flask_jwt_required

from app.services.entitlement_service import require_entitlement

F = TypeVar("F", bound=Callable[..., object])


def typed_doc(*args: object, **kwargs: object) -> Callable[[F], F]:
    return cast(Callable[[F], F], apispec_doc(*args, **kwargs))


def typed_use_kwargs(*args: object, **kwargs: object) -> Callable[[F], F]:
    return cast(Callable[[F], F], apispec_use_kwargs(*args, **kwargs))


def typed_jwt_required(
    optional: bool = False,
    fresh: bool = False,
    refresh: bool = False,
    locations: str | Sequence[object] | None = None,
    verify_type: bool = True,
    skip_revocation_check: bool = False,
) -> Callable[[F], F]:
    return cast(
        Callable[[F], F],
        flask_jwt_required(
            optional=optional,
            fresh=fresh,
            refresh=refresh,
            locations=locations,
            verify_type=verify_type,
            skip_revocation_check=skip_revocation_check,
        ),
    )


def typed_require_entitlement(feature_key: str) -> Callable[[F], F]:
    return cast(Callable[[F], F], require_entitlement(feature_key))
