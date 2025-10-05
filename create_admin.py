"""Create an admin user for the application.

Usage:
    myenv\Scripts\activate.bat
    python create_admin.py
"""

from extensions import db
from app import create_app
from models import User


def create_admin_user():
    """Create an admin user with default credentials."""
    app = create_app()

    with app.app_context():
        # Check if admin already exists
        existing_admin = User.query.filter_by(user_type='admin').first()
        if existing_admin:
            print(f"Admin user already exists: {existing_admin.username}")
            return

        # Create new admin user
        admin = User(
            username='admin',
            email='admin@dailyhelper.com',
            full_name='System Administrator',
            user_type='admin',
            reputation_score=100.0
        )
        admin.set_password('admin123')  # Default password

        db.session.add(admin)
        db.session.commit()

        print("✅ Admin user created successfully!")
        print("Username: admin")
        print("Email: admin@dailyhelper.com")
        print("Password: admin123")
        print("⚠️  Please change the password after first login!")


if __name__ == "__main__":
    create_admin_user()
