from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config.settings import Config
from dotenv import load_dotenv
from app.controllers import all_routes
from app.extensions.database import db

load_dotenv()

def create_app():
    print("Creating Flask app")
    instance = Flask(__name__)
    instance.config.from_object(Config)
    db.init_app(instance)
    
    from app.controllers import app_bp
    
    for bp in all_routes:
        instance.register_blueprint(bp)

    return instance