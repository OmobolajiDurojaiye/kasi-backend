from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()

def patch_database():
    with app.app_context():
        try:
            print("Adding is_admin column...")
            db.session.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0;"))
        except Exception as e:
            print(f"Notice (is_admin): {e}")

        try:
            print("Adding admin_role column...")
            db.session.execute(text("ALTER TABLE users ADD COLUMN admin_role VARCHAR(50) DEFAULT 'None';"))
        except Exception as e:
            print(f"Notice (admin_role): {e}")
            
        try:
            print("Adding account_status column...")
            db.session.execute(text("ALTER TABLE users ADD COLUMN account_status VARCHAR(20) DEFAULT 'active';"))
        except Exception as e:
            print(f"Notice (account_status): {e}")

        db.session.commit()
        print("Successfully patched 'users' table with Admin Schema using SQLAlchemy!")

if __name__ == "__main__":
    patch_database()
