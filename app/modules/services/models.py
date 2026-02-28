from app.extensions import db
from datetime import datetime

class Service(db.Model):
    __tablename__ = 'services'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False) 
    description = db.Column(db.Text, default='')
    service_type = db.Column(db.String(50), default='in_shop') # 'in_shop', 'home_service'
    price = db.Column(db.Float, nullable=False)
    duration = db.Column(db.Integer, default=30) # Duration in minutes
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('services', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'description': self.description,
            'service_type': self.service_type,
            'price': self.price,
            'duration': self.duration,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class Availability(db.Model):
    __tablename__ = 'availabilities'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False) # 0 = Monday, 6 = Sunday
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    user = db.relationship('User', backref=db.backref('availabilities', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'day_of_week': self.day_of_week,
            'start_time': self.start_time.strftime('%H:%M') if self.start_time else None,
            'end_time': self.end_time.strftime('%H:%M') if self.end_time else None,
            'is_active': self.is_active,
        }

class Booking(db.Model):
    __tablename__ = 'bookings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False) # merchant
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=False)
    
    booking_date = db.Column(db.Date, nullable=False)
    booking_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    
    status = db.Column(db.String(20), default='Confirmed') # Confirmed, Completed, Cancelled
    location_type = db.Column(db.String(50), default='in_shop') # in_shop, home_service
    notes = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('bookings', lazy=True))
    customer = db.relationship('Customer', backref=db.backref('bookings', lazy=True))
    service = db.relationship('Service')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'customer': self.customer.to_dict() if self.customer else None,
            'service': self.service.to_dict() if self.service else None,
            'booking_date': self.booking_date.isoformat() if self.booking_date else None,
            'booking_time': self.booking_time.strftime('%H:%M') if self.booking_time else None,
            'end_time': self.end_time.strftime('%H:%M') if self.end_time else None,
            'status': self.status,
            'location_type': self.location_type,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
