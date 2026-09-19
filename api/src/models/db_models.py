from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Boolean, DateTime
from ..database import Base

def utcnow():
    return datetime.now(timezone.utc)

class NotificationTemplate(Base):
    __tablename__ = "notification_templates"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    subject_template = Column(Text, nullable=False)
    body_template = Column(Text, nullable=False)
    language = Column(String(10), nullable=False, default="en")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "subject_template": self.subject_template,
            "body_template": self.body_template,
            "language": self.language,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

class UserPreferences(Base):
    __tablename__ = "user_preferences"

    user_id = Column(String(64), primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    email_opt_out = Column(Boolean, nullable=False, default=False)
    preferred_language = Column(String(10), nullable=False, default="en")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "email": self.email,
            "email_opt_out": self.email_opt_out,
            "preferred_language": self.preferred_language,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
