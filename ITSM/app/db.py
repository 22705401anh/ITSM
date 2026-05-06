from sqlalchemy import create_engine, event, Engine, select, func
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import OperationalError
from typing import Generator
import logging
import os
import json

from app.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


# Global variables
engine = None
sqlite_engine = None  # Persistent reference to local fallback

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

def create_engine_for_url(url: str) -> Engine:
    """Helper to create the appropriate engine based on dialect."""
    if url.startswith("sqlite"):
        e = create_engine(
            url,
            echo=settings.SQLALCHEMY_ECHO,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        
        @event.listens_for(e, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()
            
        return e
    else:
        # PostgreSQL, MySQL, SQLServer, etc.
        return create_engine(
            url,
            echo=settings.SQLALCHEMY_ECHO,
            pool_pre_ping=True,
        )

def setup_database():
    """Attempt connections to Primary, then Secondary, then Fallback."""
    global engine
    
    # Check for local configuration file
    db_config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "config", "database.json")
    
    primary_url = settings.DATABASE_URL_PRIMARY
    secondary_url = settings.DATABASE_URL_SECONDARY
    
    if os.path.exists(db_config_path):
        try:
            with open(db_config_path, "r") as f:
                data = json.load(f)
                if data.get("database_url_primary"):
                    primary_url = data["database_url_primary"]
                if data.get("database_url_secondary"):
                    secondary_url = data["database_url_secondary"]
        except Exception as e:
            logger.error(f"Failed to read database configuration from {db_config_path}: {e}")
    
    urls_to_try = []
    if primary_url:
        urls_to_try.append(("Primary", primary_url))
    if secondary_url:
        urls_to_try.append(("Secondary", secondary_url))
        
    # Always include the local SQLite database as the final fallback
    urls_to_try.append(("Fallback (SQLite)", settings.DATABASE_URL))
    
    for name, url in urls_to_try:
        try:
            logger.info(f"Attempting to connect to {name} database...")
            test_engine = create_engine_for_url(url)
            
            # Test connection
            with test_engine.connect() as conn:
                pass
                
            logger.info(f"Successfully connected to {name} database.")
            
            # Assign global engine and re-bind session factory
            engine = test_engine
            SessionLocal.configure(bind=engine)
            
            # Perform schema synchronization
            logger.info(f"Initializing schema on {name} database...")
            Base.metadata.create_all(bind=engine)
            logger.info("Database schema synchronized successfully.")
            
            # Phase 1: Zero-Data-Loss Migration Check
            if engine.name != "sqlite":
                migrate_sqlite_to_primary(engine)
                
            return
            
        except OperationalError as e:
            logger.warning(f"Failed to connect to {name} database: {e}")
            continue
            
    raise Exception("Critical Error: All database connection attempts failed.")

def migrate_sqlite_to_primary(target_engine):
    """Automated Migration: Safely seeds an empty Primary DB from the local SQLite fallback."""
    global sqlite_engine
    if not sqlite_engine:
        sqlite_engine = create_engine_for_url(settings.DATABASE_URL)
        
    try:
        logger.info("Checking if Primary Database requires data migration from SQLite...")
        with target_engine.connect() as tgt_conn:
            with sqlite_engine.connect() as src_conn:
                # sorted_tables guarantees foreign-key dependencies are inserted in the correct order (parents first)
                for table in Base.metadata.sorted_tables:
                    try:
                        # Only migrate if the target table is completely empty
                        count = tgt_conn.scalar(select(func.count()).select_from(table))
                        if count == 0:
                            rows = src_conn.execute(table.select()).fetchall()
                            if rows:
                                logger.info(f"Migrating {len(rows)} records into table '{table.name}'...")
                                dict_rows = [row._mapping for row in rows]
                                tgt_conn.execute(table.insert(), dict_rows)
                                tgt_conn.commit()
                    except Exception as table_err:
                        logger.error(f"Migration error on table {table.name}: {table_err}")
                        tgt_conn.rollback()
        logger.info("Zero-Data-Loss Migration check completed.")
    except Exception as e:
        logger.error(f"Failed to execute SQLite to Primary migration: {e}")

def get_db() -> Generator[Session, None, None]:
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database and schema."""
    setup_database()

def drop_db():
    """Drop all database tables (use with caution)."""
    if engine:
        logger.warning("Dropping all database tables...")
        Base.metadata.drop_all(bind=engine)
        logger.warning("All database tables dropped.")
