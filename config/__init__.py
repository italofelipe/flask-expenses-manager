import os


def _read_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _is_secret_weak(secret: str) -> bool:
    normalized = secret.strip().lower()
    return normalized in {"", "dev", "super-secret-key", "changeme"} or len(secret) < 32


def _runtime_environment_name() -> str:
    for env_name in ("AURAXIS_ENV", "APP_ENV", "FLASK_ENV"):
        raw = os.getenv(env_name)
        if raw is not None and raw.strip():
            return raw.strip().lower()
    return ""


def validate_security_configuration() -> None:
    enforce = _read_bool_env("SECURITY_ENFORCE_STRONG_SECRETS", True)

    is_debug = _read_bool_env("FLASK_DEBUG", False)
    is_testing = _read_bool_env("FLASK_TESTING", False)
    runtime_environment = _runtime_environment_name()
    secure_runtime = not is_debug and not is_testing

    if not enforce:
        if secure_runtime:
            raise RuntimeError(
                "Invalid runtime configuration: SECURITY_ENFORCE_STRONG_SECRETS "
                "must be true when FLASK_DEBUG=false and FLASK_TESTING=false."
            )
        return

    if runtime_environment in {"prod", "production"} and is_debug:
        raise RuntimeError(
            "Invalid runtime configuration: FLASK_DEBUG must be false in production."
        )

    if is_testing:
        return

    if is_debug:
        return

    secret_key = os.getenv("SECRET_KEY", "dev")
    jwt_secret_key = os.getenv("JWT_SECRET_KEY", "super-secret-key")
    weak = []
    if _is_secret_weak(secret_key):
        weak.append("SECRET_KEY")
    if _is_secret_weak(jwt_secret_key):
        weak.append("JWT_SECRET_KEY")

    if weak:
        raise RuntimeError(
            "Weak/invalid secrets for production runtime: "
            + ", ".join(weak)
            + ". Configure strong values in environment variables."
        )


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev")
    # JWT config
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret-key")
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_TYPE = "Bearer"

    DEBUG = _read_bool_env("FLASK_DEBUG", False)

    # Database config
    _DATABASE_URL = os.getenv("DATABASE_URL")
    SQLALCHEMY_DATABASE_URI = _DATABASE_URL or (
        f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}@"
        f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Brapi config
    BRAPI_KEY = os.getenv("BRAPI_KEY")


class DevelopmentConfig(Config):
    DEBUG = True
