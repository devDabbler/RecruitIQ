"""
Migration to add indexes to the candidates table for better query performance.
"""

from sqlalchemy import text
from backend.utils.database import engine

def add_candidate_indexes():
    """Add indexes to the candidates table."""
    with engine.connect() as conn:
        # Add indexes for better query performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_candidate_first_name ON candidates(first_name);",
            "CREATE INDEX IF NOT EXISTS idx_candidate_last_name ON candidates(last_name);",
            "CREATE INDEX IF NOT EXISTS idx_candidate_status ON candidates(status);",
            "CREATE INDEX IF NOT EXISTS idx_candidate_position_applied ON candidates(position_applied);",
            "CREATE INDEX IF NOT EXISTS idx_candidate_created_at ON candidates(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_candidate_name_search ON candidates(first_name, last_name);",
            "CREATE INDEX IF NOT EXISTS idx_candidate_status_position ON candidates(status, position_applied);",
            "CREATE INDEX IF NOT EXISTS idx_candidate_created_status ON candidates(created_at, status);",
        ]
        
        for index_sql in indexes:
            try:
                conn.execute(text(index_sql))
                conn.commit()
                print(f"Successfully created index: {index_sql}")
            except Exception as e:
                print(f"Error creating index {index_sql}: {e}")

if __name__ == "__main__":
    add_candidate_indexes() 