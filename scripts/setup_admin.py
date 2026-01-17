"""
Setup script for initializing admin user
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.settings import settings
from src.utils.auth import get_password_hash
import getpass

def main():
    print("Code Review Assistant - Admin Setup")
    print("=" * 40)

    if settings.admin_password_hash:
        print("Admin password is already set.")
        reset = input("Do you want to reset it? (y/N): ").lower().strip()
        if reset != 'y':
            print("Setup cancelled.")
            return

    # Get admin password
    while True:
        password = getpass.getpass("Enter admin password: ")
        if len(password) < 8:
            print("Password must be at least 8 characters long.")
            continue

        confirm = getpass.getpass("Confirm admin password: ")
        if password != confirm:
            print("Passwords do not match. Please try again.")
            continue

        break

    # Hash the password
    hashed_password = get_password_hash(password)

    # Update settings (in a real app, this would update a database)
    print(f"Admin password hash: {hashed_password}")
    print("Please add this to your .env file:")
    print(f"ADMIN_PASSWORD_HASH={hashed_password}")
    print("\nSetup complete!")

if __name__ == "__main__":
    main()