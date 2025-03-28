from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config.settings import Config
from dotenv import load_dotenv


load_dotenv()  # Carrega variáveis do .env

db = SQLAlchemy()

def create_app():
    print("Creating Flask app")
    instance = Flask(__name__)
    instance.config.from_object(Config)
    db.init_app(instance)
    from app.routes import app as app_bp
    instance.register_blueprint(app_bp)

    return instance