from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(300), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    filename = db.Column(db.String(300), nullable=False)         # original filename
    stored_name = db.Column(db.String(300), nullable=False)      # file on disk
    category = db.Column(db.String(100))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    expiry_date = db.Column(db.Date)        
    reminder_at = db.Column(db.DateTime)    
    nonce_b64 = db.Column(db.String(100))   # encryption nonce


class Share(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("document.id"), nullable=False)
    shared_with = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    shared_at = db.Column(db.DateTime, default=datetime.utcnow)

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    action = db.Column(db.String(200))
    detail = db.Column(db.String(1000))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
