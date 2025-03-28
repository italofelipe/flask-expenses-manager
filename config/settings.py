import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev")
    DEBUG = os.getenv("FLASK_DEBUG", "True") == "True"
    SQLALCHEMY_DATABASE_URI = (
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    DEBUG = True
    
    