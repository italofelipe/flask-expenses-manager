"""Purge hard-deleted Auraxis accounts (LGPD — ARC #885).

Accounts are soft-deleted and anonymised immediately upon user request
(``DELETE /user/me``). This script performs the final hard-delete after a
configurable grace period (default: 30 days), permanently removing the
database row so no trace of the account remains.

Usage::

    python scripts/purge_deleted_accounts.py [--grace-days N] [--dry-run]

Exit codes:
    0 — completed successfully (even if 0 rows purged)
    1 — unrecoverable error
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from app.extensions.database import db  # noqa: E402
from app.models.user import User  # noqa: E402

_DEFAULT_GRACE_DAYS = 30

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Purge soft-deleted Auraxis accounts.")
    parser.add_argument(
        "--grace-days",
        type=int,
        default=_DEFAULT_GRACE_DAYS,
        help=f"Days after soft-delete before hard purge (default: {_DEFAULT_GRACE_DAYS})",  # noqa: E501
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log eligible accounts without deleting them.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    grace_days: int = args.grace_days
    dry_run: bool = args.dry_run

    try:
        app = create_app(enable_http_runtime=False)
    except Exception:
        logger.exception(
            "purge_deleted_accounts: failed to initialise application factory"
        )
        return 1

    with app.app_context():
        try:
            cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
                days=grace_days
            )
            eligible: list[User] = (
                db.session.query(User)
                .filter(User.deleted_at.isnot(None), User.deleted_at < cutoff)
                .all()
            )
            count = len(eligible)

            if dry_run:
                logger.info(
                    "purge_deleted_accounts: DRY RUN — %s eligible "
                    "(grace_days=%s, cutoff=%s)",
                    count,
                    grace_days,
                    cutoff.isoformat(),
                )
                for user in eligible:
                    logger.info(
                        "  would purge user_id=%s deleted_at=%s",
                        user.id,
                        user.deleted_at,
                    )
                return 0

            for user in eligible:
                logger.info(
                    "purge_deleted_accounts: hard-deleting user_id=%s deleted_at=%s",
                    user.id,
                    user.deleted_at,
                )
                db.session.delete(user)

            db.session.commit()
        except Exception:
            logger.exception("purge_deleted_accounts: unhandled error during purge")
            return 1

    logger.info(
        "purge_deleted_accounts: done — accounts_hard_deleted=%s grace_days=%s",
        count,
        grace_days,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
