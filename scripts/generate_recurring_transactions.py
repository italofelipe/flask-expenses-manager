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


def main() -> None:
    app = create_app(enable_http_runtime=False)
    with app.app_context():
        created = RecurrenceService.generate_missing_occurrences(
            reference_date=date.today()
        )
        logger.info("Recurring transactions created=%s", created)


if __name__ == "__main__":
    main()
