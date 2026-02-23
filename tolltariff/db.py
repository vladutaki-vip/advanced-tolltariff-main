from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

engine = create_engine(settings.database_url, future=True, echo=False)

# SQLite performance pragmas for faster bulk imports (Render/containers)
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, connection_record):
        try:
            cur = dbapi_connection.cursor()
            # Use WAL for better concurrent reads during long imports
            cur.execute("PRAGMA journal_mode=WAL;")
            # Balance durability and speed; NORMAL is safe for most cases
            cur.execute("PRAGMA synchronous=NORMAL;")
            # Keep temp data in memory to reduce disk I/O
            cur.execute("PRAGMA temp_store=MEMORY;")
            # Increase memory-mapped I/O for faster reads/writes (128 MiB)
            cur.execute("PRAGMA mmap_size=134217728;")
            # Grow cache size (~20 MiB); negative means KB pages
            cur.execute("PRAGMA cache_size=-20000;")
            cur.close()
        except Exception:
            # Ignore if not supported by environment
            pass
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

# Dependency

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
