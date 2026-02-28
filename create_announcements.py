from app import create_app
from app.extensions import db
from app.modules.auth.models import Announcement

app = create_app()

def create_table():
    with app.app_context():
        try:
            Announcement.__table__.create(db.engine)
            print("Successfully created announcements table.")
        except Exception as e:
            print("Error creating table (it might already exist):", e)
            db.session.rollback()

if __name__ == '__main__':
    create_table()
