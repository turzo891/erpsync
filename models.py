"""
Database models for ERP sync state tracking
"""
from sqlalchemy import create_engine, Column, String, DateTime, Integer, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()


class SyncRecord(Base):
    """Track sync state for each document"""
    __tablename__ = 'sync_records'

    id = Column(Integer, primary_key=True)
    doctype = Column(String(200), nullable=False, index=True)
    docname = Column(String(200), nullable=False, index=True)

    # Timestamps
    cloud_modified = Column(DateTime, nullable=True)
    local_modified = Column(DateTime, nullable=True)
    last_synced = Column(DateTime, nullable=True)

    # Sync metadata
    sync_hash_cloud = Column(String(64), nullable=True)  # MD5 hash of cloud data
    sync_hash_local = Column(String(64), nullable=True)  # MD5 hash of local data
    sync_direction = Column(String(20), nullable=True)   # 'cloud_to_local', 'local_to_cloud', 'bidirectional'

    # Status
    is_syncing = Column(Boolean, default=False)  # Prevent concurrent syncs
    sync_status = Column(String(50), default='pending')  # pending, synced, conflict, error
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SyncLog(Base):
    """Audit log for all sync operations"""
    __tablename__ = 'sync_logs'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    doctype = Column(String(200), nullable=False)
    docname = Column(String(200), nullable=False)

    action = Column(String(50), nullable=False)  # create, update, delete
    direction = Column(String(20), nullable=False)  # cloud_to_local, local_to_cloud

    status = Column(String(50), nullable=False)  # success, failed, conflict
    message = Column(Text, nullable=True)

    # Store change details (optional)
    changes_json = Column(Text, nullable=True)


class ConflictRecord(Base):
    """Track conflicts that need manual resolution"""
    __tablename__ = 'conflict_records'

    id = Column(Integer, primary_key=True)
    doctype = Column(String(200), nullable=False)
    docname = Column(String(200), nullable=False)

    cloud_data = Column(Text, nullable=False)  # JSON string
    local_data = Column(Text, nullable=False)  # JSON string

    cloud_modified = Column(DateTime, nullable=False)
    local_modified = Column(DateTime, nullable=False)

    resolved = Column(Boolean, default=False)
    resolution = Column(String(50), nullable=True)  # cloud_wins, local_wins, merge
    resolved_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class WebhookQueue(Base):
    """Queue for webhook events to process"""
    __tablename__ = 'webhook_queue'

    id = Column(Integer, primary_key=True)
    source = Column(String(20), nullable=False)  # 'cloud' or 'local'

    doctype = Column(String(200), nullable=False)
    docname = Column(String(200), nullable=False)
    action = Column(String(50), nullable=False)  # create, update, delete

    payload = Column(Text, nullable=False)  # JSON string

    processed = Column(Boolean, default=False)
    processing = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    processed_at = Column(DateTime, nullable=True)

    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)


# Database connection
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///sync_state.db')
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(engine)
    print("Database initialized successfully")


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        return db
    finally:
        pass  # Don't close here, let caller handle it


if __name__ == '__main__':
    init_db()
