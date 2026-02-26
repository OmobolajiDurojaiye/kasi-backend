from app import create_app
from app.extensions import db
import os

# Explicitly import models to ensure they are discovered by SQLAlchemy
from app.modules.auth.models import User
from app.modules.invoices.models import Invoice, Customer
from app.modules.products.models import Product
from app.modules.telegram.models import TelegramBot

app = create_app()
with app.app_context():
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
    print(f"Current Database URI: {db_uri}")
    
    # Extract path from sqlite:///path
    if db_uri.startswith('sqlite:///'):
        db_path = db_uri.replace('sqlite:///', '')
        print(f"Target Database File: {db_path}")
        print(f"Database Directory exists: {os.path.exists(os.path.dirname(db_path))}")

    print("Creating all database tables...")
    db.create_all()
    print("Verification: Tables in database:")
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print(f"Tables found: {tables}")
    
    if 'users' in tables:
        print("SUCCESS: 'users' table created!")
    else:
        print("WARNING: 'users' table is STILL MISSING!")
    
    print("Done! Force creation sequence complete.")

