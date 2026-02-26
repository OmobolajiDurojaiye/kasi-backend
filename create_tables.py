from app import create_app
from app.extensions import db

app = create_app()
with app.app_context():
    print("Creating all database tables...")
    db.create_all()
    print("Done! Database tables created successfully.")
