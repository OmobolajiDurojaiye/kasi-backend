from app.extensions import db
from datetime import datetime


class TelegramBot(db.Model):
    __tablename__ = 'telegram_bots'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    bot_token = db.Column(db.String(200), nullable=False)
    bot_username = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='telegram_bot')

    def to_dict(self):
        return {
            'id': self.id,
            'bot_username': self.bot_username,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
