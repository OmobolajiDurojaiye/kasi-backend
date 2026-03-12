from app.extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    business_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    
    # Profile / Branding Fields
    phone = db.Column(db.String(20))
    address = db.Column(db.String(255))
    logo_url = db.Column(db.String(255))
    bank_name = db.Column(db.String(50))
    account_number = db.Column(db.String(20))
    account_name = db.Column(db.String(100))

    is_admin = db.Column(db.Boolean, default=False)
    admin_role = db.Column(db.String(50), default='None')
    account_status = db.Column(db.String(20), default='active')
    kasi_credits = db.Column(db.Integer, default=5) # 5 Free starting credits
    ai_instructions = db.Column(db.Text, nullable=True) # Custom merchant rules

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'business_name': self.business_name,
            'phone': self.phone,
            'address': self.address,
            'logo_url': self.logo_url,
            'bank_name': self.bank_name,
            'account_number': self.account_number,
            'account_name': self.account_name,
            'is_admin': self.is_admin,
            'admin_role': self.admin_role,
            'account_status': self.account_status,
            'kasi_credits': self.kasi_credits,
            'ai_instructions': self.ai_instructions,
            'created_at': self.created_at.isoformat()
        }

class Announcement(db.Model):
    __tablename__ = 'announcements'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), default='info') # info, warning, success
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'type': self.type,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat()
        }

class CreditTransaction(db.Model):
    __tablename__ = 'credit_transactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False) # e.g. +100 or -1
    transaction_type = db.Column(db.String(50), nullable=False) # 'purchase', 'ai_generation', 'refund', 'bonus'
    reference_id = db.Column(db.String(100), nullable=True) # Paystack ref, if applicable
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('credit_transactions', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'amount': self.amount,
            'transaction_type': self.transaction_type,
            'reference_id': self.reference_id,
            'description': self.description,
            'created_at': self.created_at.isoformat()
        }

class Integration(db.Model):
    __tablename__ = 'integrations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    platform = db.Column(db.String(50), nullable=False) # "whatsapp", "telegram"
    instance_name = db.Column(db.String(100), unique=True, nullable=True) # e.g., "kasi_whatsapp_user_5"
    connection_status = db.Column(db.String(20), default="disconnected")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('integrations', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'platform': self.platform,
            'instance_name': self.instance_name,
            'connection_status': self.connection_status,
            'created_at': self.created_at.isoformat()
        }

class WaitlistEntry(db.Model):
    __tablename__ = 'waitlist_entries'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False, unique=True)
    phone_number = db.Column(db.String(50), nullable=False)
    instagram_handle = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone_number': self.phone_number,
            'instagram_handle': self.instagram_handle,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class IdempotencyKey(db.Model):
    __tablename__ = 'idempotency_keys'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    response_code = db.Column(db.Integer, nullable=False)
    response_body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) # Optional, mostly track logged in user
    action = db.Column(db.String(100), nullable=False)
    resource_details = db.Column(db.Text, nullable=True) # JSON dump of what changed
    ip_address = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('audit_logs', lazy=True))