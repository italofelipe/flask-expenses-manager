"""Password verification and hashing service — SEC-GAP-06.

Provides Argon2id as the canonical hashing algorithm with transparent,
incremental migration from Werkzeug PBKDF2 hashes.

Migration strategy
------------------
- New users:  hash produced by ``hash_password()`` starts with ``$argon2id$``.
- Legacy users: hash starts with ``pbkdf2:sha256:`` (Werkzeug default).
  On first successful login, the PBKDF2 hash is silently replaced with
  Argon2id via the ``on_rehash`` callback.  No forced password-reset required.

Argon2id parameters (OWASP 2026 recommendations)
-------------------------------------------------
  time_cost=3, memory_cost=65536 (64 MiB), parallelism=4
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from collections.abc import Callable

from passlib.context import CryptContext

from app.extensions.integration_metrics import increment_metric

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Passlib context
# ---------------------------------------------------------------------------

_CRYPT_CTX = CryptContext(
    schemes=["argon2", "django_pbkdf2_sha256"],
    deprecated=["django_pbkdf2_sha256"],
    argon2__time_cost=3,
    argon2__memory_cost=65536,
    argon2__parallelism=4,
)

# ---------------------------------------------------------------------------
# Timing-attack guard — used when no user is found
# ---------------------------------------------------------------------------

_DUMMY_SALT = secrets.token_bytes(16)
_DUMMY_PBKDF2_ITERATIONS = 600_000


def _burn_hash_cycles(plain_password: str) -> None:
    hashlib.pbkdf2_hmac(
        "sha256",
        plain_password.encode("utf-8"),
        _DUMMY_SALT,
        _DUMMY_PBKDF2_ITERATIONS,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def hash_password(plain_password: str) -> str:
    """Return an Argon2id hash for *plain_password*."""
    return str(_CRYPT_CTX.hash(plain_password))


def needs_rehash(password_hash: str) -> bool:
    """Return True if *password_hash* should be upgraded to Argon2id."""
    if _is_werkzeug_pbkdf2(password_hash):
        return True
    try:
        return bool(_CRYPT_CTX.needs_update(password_hash))
    except Exception:
        # Unknown hash format — cannot determine upgrade need; leave as-is.
        return False


def verify_password_with_timing_protection(
    *,
    password_hash: str | None,
    plain_password: str,
    on_rehash: Callable[[str], None] | None = None,
) -> bool:
    """Verify *plain_password* against *password_hash*.

    - If no hash is stored (user not found), a dummy PBKDF2 computation is
      executed to equalise timing with the found-but-wrong-password path.
    - If the hash is a legacy PBKDF2 hash and the password is correct, the
      ``on_rehash`` callback is invoked with the new Argon2id hash so the
      caller can persist the upgrade transparently.

    Parameters
    ----------
    password_hash:
        Stored hash from the database (may be None when user not found).
    plain_password:
        Plain-text password to verify.
    on_rehash:
        Optional callback ``(new_hash: str) -> None`` called when the stored
        hash is outdated and has been re-hashed successfully.
    """
    if not password_hash:
        _burn_hash_cycles(plain_password)
        return False

    # Werkzeug PBKDF2 hashes start with "pbkdf2:sha256:". passlib's
    # django_pbkdf2_sha256 scheme expects a "pbkdf2_sha256$..." prefix.
    # We detect Werkzeug format and verify using werkzeug directly so we
    # don't need to reformat the stored hash.
    if _is_werkzeug_pbkdf2(password_hash):
        return _verify_werkzeug_and_maybe_rehash(
            password_hash=password_hash,
            plain_password=plain_password,
            on_rehash=on_rehash,
        )

    # Argon2id (or any other passlib-managed scheme)
    verified, new_hash = _CRYPT_CTX.verify_and_update(plain_password, password_hash)
    if verified and new_hash and on_rehash is not None:
        try:
            on_rehash(new_hash)
            increment_metric("password.hash.migrations")
            logger.info("password_hash_migrated scheme=argon2id")
        except Exception:
            logger.warning("password_hash_migration_failed", exc_info=True)
    return bool(verified)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_werkzeug_pbkdf2(password_hash: str) -> bool:
    # Werkzeug hashes: "pbkdf2:sha256:..." (legacy) or "scrypt:..." (newer default).
    # Both are handled by werkzeug.security.check_password_hash and both should be
    # migrated to Argon2id.
    return password_hash.startswith(("pbkdf2:", "scrypt:"))


def _verify_werkzeug_and_maybe_rehash(
    *,
    password_hash: str,
    plain_password: str,
    on_rehash: Callable[[str], None] | None,
) -> bool:
    from werkzeug.security import check_password_hash

    verified: bool = check_password_hash(password_hash, plain_password)
    if verified and on_rehash is not None:
        try:
            new_hash = hash_password(plain_password)
            on_rehash(new_hash)
            increment_metric("password.hash.migrations")
            logger.info("password_hash_migrated scheme=argon2id from=werkzeug_pbkdf2")
        except Exception:
            logger.warning("password_hash_migration_failed", exc_info=True)
    return verified
