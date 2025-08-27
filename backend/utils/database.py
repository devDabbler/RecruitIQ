from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError
import logging
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
SQLALCHEMY_DATABASE_URL = settings.postgres_conn

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
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