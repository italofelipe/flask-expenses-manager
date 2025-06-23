import datetime

from app.extensions.database import db
from app.models.transaction import Transaction, TransactionStatus


def mark_overdue_transactions() -> int:
    today = datetime.datetime.now(datetime.timezone.utc).date()
    transactions = Transaction.query.filter(
        Transaction.due_date < today,
        Transaction.status == TransactionStatus.PENDING,
        Transaction.deleted.is_(False),
    ).all()

    for t in transactions:
        t.status = TransactionStatus.OVERDUE

    db.session.commit()
    return len(transactions)
