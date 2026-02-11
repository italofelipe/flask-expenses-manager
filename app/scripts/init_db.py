import logging

from app import create_app
from app.extensions.database import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = create_app()

with app.app_context():
    db.create_all()
    logger.info("Database tables created successfully.")
