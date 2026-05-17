"""LGPD versioned consents REST controller (issue #1259)."""

from __future__ import annotations

from . import routes as _routes  # noqa: F401
from .blueprint import consents_bp
from .resources import ConsentCollectionResource, ConsentRevokeResource

__all__ = [
    "consents_bp",
    "ConsentCollectionResource",
    "ConsentRevokeResource",
]
