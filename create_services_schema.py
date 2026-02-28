from app import create_app
from app.extensions import db
from app.modules.services.models import Service, Availability, Booking

app = create_app()

def create_tables():
    with app.app_context():
        print("Creating Service Scheduling tables if they don't exist...")
        # Since we use SQLite safely, we can just call create_all. 
        # It won't drop existing tables.
        db.create_all()
        print("Done!")

if __name__ == '__main__':
    create_tables()
