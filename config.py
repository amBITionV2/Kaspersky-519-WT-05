import os


class Config:
    """Base configuration for the Flask application."""

    # Security
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-in-production")

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///app.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Flask-WTF
    WTF_CSRF_ENABLED = True

    # Logging
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

    # Web3 / Blockchain
    ETH_RPC_URL = os.environ.get("ETH_RPC_URL", "")  # e.g. https://sepolia.infura.io/v3/<KEY>
    ETH_CHAIN_NAME = os.environ.get("ETH_CHAIN_NAME", "")
    # Internal blockchain batching (number of statements per block)
    BLOCK_SIZE = int(os.environ.get("BLOCK_SIZE", "10"))
