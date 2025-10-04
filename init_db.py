"""Initialize the SQLite database and create all tables.

Usage (cmd):
  myenv\Scripts\activate.bat
  python init_db.py
"""
from extensions import db
from app import create_app


def main() -> None:
    app = create_app()
    with app.app_context():
        # Import models to register them with SQLAlchemy metadata
        import models  # noqa: F401
        db.create_all()
        print("Database initialized and tables created.")


if __name__ == "__main__":
    main()
