from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError
import logging
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
SQLALCHEMY_DATABASE_URL = settings.postgres_conn

# Pool sizing is a production-incident lesson (2026-08-28, first hour live):
# many endpoints are `async def` but use this sync engine, so ORM calls run on
# the event loop. One dashboard view fans out ~8 parallel API calls; with the
# default pool (5+10) and 30s pool_timeout, exhaustion blocked the event loop
# itself on checkout and froze the whole server, /health included. A larger
# pool makes exhaustion rare; the short pool_timeout makes it survivable - the
# stalled request 500s in 5s and the loop moves on, instead of a death spiral.
# The real fix (async sessions or sync endpoints) is future work.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=5,
    pool_recycle=1800,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
def verify_postgres_connection():
    """
    Verify PostgreSQL connection by executing a simple query.
    Returns True if connection successful, False otherwise.
    """
    try:
        # Create a new connection
        with engine.connect() as connection:
            # Execute a simple query
            result = connection.execute(text("SELECT 1")).scalar()
            if result == 1:
                # Extract connection information for logging
                db_url = SQLALCHEMY_DATABASE_URL.split('@')[-1].split('/') 
                host_port = db_url[0]
                db_name = db_url[1].split('?')[0] if '?' in db_url[1] else db_url[1]
                logger.info(f"Successfully connected to PostgreSQL database '{db_name}' at {host_port}")
                return True
            return False
    except SQLAlchemyError as e:
        logger.error(f"Failed to connect to PostgreSQL database: {str(e)}")
        return False