from . import resources as _resources  # noqa: F401
from .blueprint import shared_entries_bp
from .dependencies import register_shared_entries_dependencies

__all__ = ["shared_entries_bp", "register_shared_entries_dependencies"]
