"""
One-time SQLite migration helper for adding new columns to existing tables
without losing data. Safe to run multiple times; it will skip columns that
already exist (errors are caught and printed as Skip/Err).

Usage (from project root, with venv activated):
  python scripts/migrate_sqlite.py
"""
import os
import sys
from sqlalchemy import text

# Add project root to sys.path so `app` is importable when run directly
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402


def add_column(sql: str) -> None:
    try:
        db.session.execute(text(sql))
        db.session.commit()
        print("OK:", sql)
    except Exception as e:  # noqa: BLE001
        # Likely the column already exists; print and continue
        print("Skip/Err:", sql, "->", e)


def main() -> None:
    app = create_app()
    with app.app_context():
        # Users: new profile/geo/blacklist columns
        add_column("ALTER TABLE users ADD COLUMN latitude FLOAT")
        add_column("ALTER TABLE users ADD COLUMN longitude FLOAT")
        add_column("ALTER TABLE users ADD COLUMN blacklist_reason VARCHAR(300)")
        add_column("ALTER TABLE users ADD COLUMN bio TEXT")
        add_column("ALTER TABLE users ADD COLUMN skills VARCHAR(300)")
        add_column("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(300)")

        # Ensure any new tables exist
        # (e.g., reviews, ngos, flags, blocks, statements)
        db.create_all()
        print("Done. You can restart the server now.")


if __name__ == "__main__":
    main()
