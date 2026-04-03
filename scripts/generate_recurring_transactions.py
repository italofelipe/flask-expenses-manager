import logging
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from app.services.recurrence_service import RecurrenceService  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    try:
        app = create_app(enable_http_runtime=False)
    except Exception:
        logger.exception("recurrence: failed to initialise application factory")
        return 1

    with app.app_context():
        try:
            created = RecurrenceService.generate_missing_occurrences(
                reference_date=date.today()
            )
        except Exception:
            logger.exception(
                "recurrence: unhandled error in generate_missing_occurrences"
            )
            return 1

    logger.info("recurrence: done — transactions created=%s", created)
    return 0


if __name__ == "__main__":
    sys.exit(main())
