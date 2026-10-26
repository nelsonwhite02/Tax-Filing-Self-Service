from getpass import getpass
from sqlalchemy import func
from passlib.context import CryptContext

from app.core.database import SessionLocal
from app.models.user import User

password_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def main():
    email = input("Administrator email: ").strip().lower()
    if not email or "@" not in email:
        raise SystemExit("Enter a valid email address.")

    password = getpass("Create administrator password (minimum 12 characters): ")
    confirmation = getpass("Confirm administrator password: ")

    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters.")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    full_name = input("Administrator full name: ").strip()
    if not full_name:
        raise SystemExit("Full name is required.")

    db = SessionLocal()
    try:
        existing = db.query(User).filter(func.lower(User.email) == email).first()
        if existing:
            raise SystemExit("That email already exists. No account was changed.")

        admin = User(
            full_name=full_name,
            email=email,
            password_hash=password_context.hash(password),
            role="admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print(f"Administrator account created successfully (user ID: {admin.id}).")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
