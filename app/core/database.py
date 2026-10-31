import logging
from datetime import datetime, timezone
from sqlalchemy import create_engine, event, inspect, text
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
        audit_columns = {column["name"] for column in inspect(connection).get_columns("audit_logs")}
        has_prev_hash = "prev_hash" in audit_columns
        has_entry_hash = "entry_hash" in audit_columns
        if has_prev_hash != has_entry_hash:
            raise RuntimeError("audit_logs has a partially migrated hash-chain schema")
        added_chain_columns = not has_prev_hash
        if added_chain_columns:
            if dialect_name == "postgresql":
                connection.execute(text("DROP TRIGGER IF EXISTS trg_audit_log_append_only ON audit_logs"))
            elif dialect_name == "sqlite":
                connection.execute(text("DROP TRIGGER IF EXISTS trg_prevent_audit_update"))
                connection.execute(text("DROP TRIGGER IF EXISTS trg_prevent_audit_delete"))

            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN prev_hash VARCHAR(64)"))
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN entry_hash VARCHAR(64)"))
            connection.commit()

        connection.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_audit_logs_entry_hash ON audit_logs (entry_hash)"
        ))
        connection.commit()

        if added_chain_columns:
            from app.services.audit import ZERO_HASH, compute_entry_hash

            rows = connection.execute(text("""
                SELECT id, actor_id, actor_email, action, entity_type, entity_id,
                       ip_address, before_state, after_state, created_at
                FROM audit_logs ORDER BY id ASC
            """)).mappings().all()
            previous_hash = ZERO_HASH
            for row in rows:
                created_at = row["created_at"]
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                entry = dict(row)
                entry["created_at"] = created_at
                entry["prev_hash"] = previous_hash
                entry_hash = compute_entry_hash(entry, previous_hash)
                connection.execute(
                    text("UPDATE audit_logs SET prev_hash = :prev_hash, entry_hash = :entry_hash WHERE id = :id"),
                    {"prev_hash": previous_hash, "entry_hash": entry_hash, "id": row["id"]},
                )
                previous_hash = entry_hash
            connection.commit()

        if dialect_name == "postgresql":
            connection.execute(text("""
                CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
                RETURNS TRIGGER AS $$
                BEGIN
                    RAISE EXCEPTION 'audit_logs is append-only: UPDATE or DELETE is strictly prohibited';
                END;
                $$ LANGUAGE plpgsql;
            """))
            connection.execute(text("DROP TRIGGER IF EXISTS trg_audit_log_append_only ON audit_logs"))
            connection.execute(text("""
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
    except Exception:
        logger.exception("Could not install or migrate the append-only audit log")
        raise
