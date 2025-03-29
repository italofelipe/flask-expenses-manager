import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev")
    # JWT config
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret-key")
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_TYPE = "Bearer"
    
    DEBUG = os.getenv("FLASK_DEBUG", "True") == "True"
    
    # Database config
    SQLALCHEMY_DATABASE_URI = (
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    DEBUG = True