"""
Education Service
Handles database operations for education entries with proper transaction management
"""
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from ..utils.date_normalizer import normalize_education_dates

logger = logging.getLogger(__name__)

class EducationService:
    """Service for managing education entries in the database"""
    
    def __init__(self, db_session: Session):
        """
        Initialize education service
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
    
    def create_education_entries(self, candidate_id: int, education_entries: List[Dict[str, Any]]) -> bool:
        """
        Create education entries for a candidate with transaction management
        
        Args:
            candidate_id: ID of the candidate
            education_entries: List of education entry dictionaries
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not education_entries:
            return True
            
        try:
            # Start transaction
            self.db.begin()
            
            # Process each education entry
            for entry in education_entries:
                # Normalize dates
                start_date, end_date = normalize_education_dates(
                    entry.get('start_date', ''),
                    entry.get('end_date', '')
                )
                
                # Create education entry
                education_entry = {
                    'candidate_id': candidate_id,
                    'institution': entry.get('institution', ''),
                    'degree': entry.get('degree', ''),
                    'field_of_study': entry.get('field_of_study', ''),
                    'start_date': start_date,
                    'end_date': end_date,
                    'gpa': entry.get('gpa'),
                    'description': entry.get('description', '')
                }
                
                # Insert into database
                self.db.execute(
                    """
                    INSERT INTO education (
                        candidate_id, institution, degree, field_of_study,
                        start_date, end_date, gpa, description
                    ) VALUES (
                        :candidate_id, :institution, :degree, :field_of_study,
                        :start_date, :end_date, :gpa, :description
                    )
                    """,
                    education_entry
                )
            
            # Commit transaction
            self.db.commit()
            return True
            
        except SQLAlchemyError as e:
            # Rollback transaction on error
            self.db.rollback()
            logger.error(f"Error creating education entries: {str(e)}")
            return False
    
    def update_education_entries(self, candidate_id: int, education_entries: List[Dict[str, Any]]) -> bool:
        """
        Update education entries for a candidate with transaction management
        
        Args:
            candidate_id: ID of the candidate
            education_entries: List of education entry dictionaries
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Start transaction
            self.db.begin()
            
            # Delete existing entries
            self.db.execute(
                "DELETE FROM education WHERE candidate_id = :candidate_id",
                {'candidate_id': candidate_id}
            )
            
            # Create new entries
            success = self.create_education_entries(candidate_id, education_entries)
            
            if success:
                self.db.commit()
            else:
                self.db.rollback()
                
            return success
            
        except SQLAlchemyError as e:
            # Rollback transaction on error
            self.db.rollback()
            logger.error(f"Error updating education entries: {str(e)}")
            return False
    
    def get_education_entries(self, candidate_id: int) -> List[Dict[str, Any]]:
        """
        Get education entries for a candidate
        
        Args:
            candidate_id: ID of the candidate
            
        Returns:
            List of education entry dictionaries
        """
        try:
            result = self.db.execute(
                """
                SELECT * FROM education 
                WHERE candidate_id = :candidate_id 
                ORDER BY start_date DESC
                """,
                {'candidate_id': candidate_id}
            )
            
            entries = []
            for row in result:
                entry = dict(row)
                # Convert dates to strings if needed
                if entry.get('start_date'):
                    entry['start_date'] = entry['start_date'].strftime('%Y-%m')
                if entry.get('end_date'):
                    entry['end_date'] = entry['end_date'].strftime('%Y-%m')
                entries.append(entry)
                
            return entries
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting education entries: {str(e)}")
            return [] 