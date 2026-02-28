from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()

def add_column():
    with app.app_context():
        try:
            db.session.execute(text("ALTER TABLE users ADD COLUMN account_status VARCHAR(20) DEFAULT 'active'"))
            db.session.commit()
            print("Successfully added account_status column to users table.")
        except Exception as e:
            print("Error adding column (it might already exist):", e)
            db.session.rollback()

if __name__ == '__main__':
    add_column()
