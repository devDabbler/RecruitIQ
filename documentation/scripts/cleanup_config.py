"""
Configuration file for the candidate cleanup script.
Update these settings to match your database configurations.
"""

import os

# PostgreSQL Configuration
POSTGRESQL_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'ats_db',           # Your actual database name
    'user': 'admin',                # Your actual PostgreSQL username
    'password': os.getenv('POSTGRES_PASSWORD', '')   # Set POSTGRES_PASSWORD env var
}

# Neo4j Configuration
NEO4J_CONFIG = {
    'uri': 'bolt://localhost:7687',  # Your actual Neo4j URI
    'user': 'neo4j',                # Your actual Neo4j username
    'password': os.getenv('NEO4J_PASSWORD', '')   # Set NEO4J_PASSWORD env var
}

# Alternative: Load from environment variables (recommended for production)
from dotenv import load_dotenv

# Uncomment these lines to load from .env file instead:
# load_dotenv()
# POSTGRESQL_CONFIG = {
#     'host': os.getenv('DB_HOST', 'localhost'),
#     'port': int(os.getenv('DB_PORT', 5432)),
#     'database': os.getenv('DB_NAME', 'ats_db'),
#     'user': os.getenv('DB_USER', 'admin'),
#     'password': os.getenv('DB_PASSWORD', 'admin123')
# }
# 
# NEO4J_CONFIG = {
#     'uri': os.getenv('NEO4J_URI', 'bolt://127.0.0.1:7687'),
#     'user': os.getenv('NEO4J_USER', 'neo4j'),
#     'password': os.getenv('NEO4J_PASSWORD', 'password')
# }

# Safety Settings
REQUIRE_CONFIRMATION = True  # Set to False to skip confirmation prompt
BACKUP_BEFORE_DELETE = False  # Set to True to create backup before deletion

# Logging Settings
LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR
LOG_TO_FILE = True  # Set to True to also log to file
LOG_FILE = 'cleanup_candidates.log' 