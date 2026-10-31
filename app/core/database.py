import logging
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

logger = logging.getLogger("drishti.db")

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

# Enable foreign keys and WAL for SQLite
if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def setup_audit_triggers(connection):
    """Enforce append-only semantics on audit_logs table via database trigger."""
    dialect_name = engine.dialect.name
    try:
        if dialect_name == "postgresql":
            connection.execute(text("""
                CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
                RETURNS TRIGGER AS $$
                BEGIN
                    RAISE EXCEPTION 'audit_logs is append-only: UPDATE or DELETE is strictly prohibited';
                END;
                $$ LANGUAGE plpgsql;
                
                DROP TRIGGER IF EXISTS trg_audit_log_append_only ON audit_logs;
                CREATE TRIGGER trg_audit_log_append_only
                BEFORE UPDATE OR DELETE ON audit_logs
                FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_modification();
            """))
            connection.commit()
            logger.info("PostgreSQL append-only trigger installed on audit_logs")
        elif dialect_name == "sqlite":
            connection.execute(text("""
                CREATE TRIGGER IF NOT EXISTS trg_prevent_audit_update
                BEFORE UPDATE ON audit_logs
                BEGIN
                    SELECT RAISE(ABORT, 'audit_logs is append-only: UPDATE is strictly prohibited');
                END;
            """))
            connection.execute(text("""
                CREATE TRIGGER IF NOT EXISTS trg_prevent_audit_delete
                BEFORE DELETE ON audit_logs
                BEGIN
                    SELECT RAISE(ABORT, 'audit_logs is append-only: DELETE is strictly prohibited');
                END;
            """))
            connection.commit()
            logger.info("SQLite append-only triggers installed on audit_logs")
    except Exception as e:
        logger.warning(f"Could not install audit trigger (table may not exist yet): {e}")
