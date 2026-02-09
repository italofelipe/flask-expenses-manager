from datetime import date

from app import create_app
from app.services.recurrence_service import RecurrenceService


def main() -> None:
    app = create_app()
    with app.app_context():
        created = RecurrenceService.generate_missing_occurrences(
            reference_date=date.today()
        )
        print(f"Recurring transactions created: {created}")


if __name__ == "__main__":
    main()
