"""Generate end-of-month AI recap insights for all active users (#1386, slice B).

Run on the 1st of each month (cron). For the month that just ended, every user
with at least one daily insight gets a consolidated monthly recap. Idempotent:
users that already have a recap for the period are skipped.

The recap is exempt from the per-user daily/monthly caps and cost ceiling.

Usage:
    python scripts/generate_monthly_recaps.py
"""

import logging
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from app.services.ai_monthly_report_service import (  # noqa: E402
    generate_monthly_recaps_for_all,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    try:
        app = create_app(enable_http_runtime=False)
    except Exception:
        logger.exception("monthly_recap: failed to initialise application factory")
        return 1

    with app.app_context():
        try:
            generated = generate_monthly_recaps_for_all(reference_date=date.today())
        except Exception:
            logger.exception("monthly_recap: unhandled error in batch generation")
            return 1

    logger.info("monthly_recap: done — recaps generated=%s", generated)
    return 0


if __name__ == "__main__":
    sys.exit(main())
