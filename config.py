"""
Central configuration for the application.
All tunable values (thresholds, keys, paths) live here and are read
from environment variables, so nothing sensitive is hard-coded and
thresholds can be changed without touching business logic.
"""

import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    BASE_DIR = BASE_DIR
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    # NOTE: Flask-SQLAlchemy resolves a *relative* sqlite:/// path against
    # Flask's instance_path (an "instance/" folder), not the project root
    # or the process's current working directory. To avoid that surprise
    # (a very common student pitfall), we always use an absolute path
    # here, built from BASE_DIR, unless the person has already provided
    # an absolute DATABASE_URL of their own.
    _env_db_url = os.environ.get("DATABASE_URL", "").strip()
    if _env_db_url and _env_db_url != "sqlite:///database/portfolio.db":
        SQLALCHEMY_DATABASE_URI = _env_db_url
    else:
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "database", "portfolio.db")

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # LLM configuration (optional). If LLM_API_KEY is blank, the AI
    # services fall back to rule-based / template answers so that the
    # app remains fully functional (and honest) without an API key.
    LLM_API_KEY = os.environ.get("LLM_API_KEY", "").strip()
    LLM_API_URL = os.environ.get("LLM_API_URL", "https://api.anthropic.com/v1/messages")
    LLM_MODEL = os.environ.get("LLM_MODEL", "claude-3-5-haiku-20241022")

    # Market data (optional external API). Falls back to bundled CSVs.
    MARKET_DATA_API_KEY = os.environ.get("MARKET_DATA_API_KEY", "").strip()
    MARKET_DATA_API_URL = os.environ.get("MARKET_DATA_API_URL", "").strip()

    # Risk thresholds - configurable, not hard-coded "magic numbers"
    # scattered through the business logic.
    CONCENTRATION_THRESHOLD_PERCENT = float(
        os.environ.get("CONCENTRATION_THRESHOLD_PERCENT", 40)
    )
    DRAWDOWN_ALERT_THRESHOLD_PERCENT = float(
        os.environ.get("DRAWDOWN_ALERT_THRESHOLD_PERCENT", -10)
    )
    ANOMALY_CONTAMINATION = float(os.environ.get("ANOMALY_CONTAMINATION", 0.05))

    DATA_DIR = os.path.join(BASE_DIR, "data")
    MARKET_DATA_CSV = os.path.join(DATA_DIR, "market_data.csv")
    KNOWLEDGE_DOCS_DIR = os.path.join(BASE_DIR, "knowledge_base", "documents")

    # Allowed tables/columns for the NL-to-SQL engine. This whitelist is
    # the core safety mechanism for that feature.
    NLSQL_ALLOWED_TABLES = {"holdings", "transactions", "alerts"}
