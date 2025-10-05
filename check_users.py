#!/usr/bin/env python3
"""Check user data in the database."""

from app import create_app
from models import User

def check_users():
    app = create_app()
    with app.app_context():
        # Check if admin user exists
        admin = User.query.filter_by(username='admin').first()
        if admin:
            print(f'Admin user found:')
            print(f'  Username: {admin.username}')
            print(f'  Email: {admin.email}')
            print(f'  Full Name: {repr(admin.full_name)}')
            print(f'  User Type: {admin.user_type}')
        else:
            print('Admin user not found')

        # Check total users
        total_users = User.query.count()
        print(f'Total users in database: {total_users}')

        # List all users for debugging
        all_users = User.query.all()
        print(f'\nAll users:')
        for user in all_users:
            print(f'  {user.username} - {user.email} - Full Name: {repr(user.full_name)}')

if __name__ == "__main__":
    check_users()
