import logging
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, Text, Boolean, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import worker_settings

logger = logging.getLogger(__name__)

Base = declarative_base()

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

def get_engine(database_url: str = None):
    url = database_url or worker_settings.DATABASE_URL
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True)

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_worker_db():
    db = SessionLocal()
    try:
        return db
    except Exception as e:
        logger.error(f"Error opening DB session in worker: {e}")
        raise
