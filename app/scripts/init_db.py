from app.extensions.database import db
from app import create_app

app = create_app()

with app.app_context():
    db.create_all()
    print("Tabelas criadas com sucesso.")