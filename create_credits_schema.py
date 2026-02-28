from app import create_app
from app.extensions import db
from app.modules.auth.models import User, CreditTransaction
from sqlalchemy import text

app = create_app()

def run_migration():
    with app.app_context():
        try:
            # 1. Add kasi_credits column to existing users if they don't have it
            print("Adding kasi_credits column...")
            db.session.execute(text("ALTER TABLE users ADD COLUMN kasi_credits INTEGER DEFAULT 5;"))
            
            # Backfill any existing users with 5 free credits
            db.session.execute(text("UPDATE users SET kasi_credits = 5 WHERE kasi_credits IS NULL;"))
            db.session.commit()
            print("Successfully patched 'users' table.")
        except Exception as e:
            # It likely already exists, ignore
            db.session.rollback()
            print("Notice on users table:", e)
            
        try:
            # 2. Create the CreditTransaction table
            print("Creating credit_transactions table...")
            CreditTransaction.__table__.create(db.engine)
            print("Successfully created 'credit_transactions' table.")
        except Exception as e:
            db.session.rollback()
            print("Notice on credit_transactions table (might exist):", e)

if __name__ == '__main__':
    run_migration()
