"""Model Standardization Module

Provides utilities for proper conversion between Pydantic models and dictionaries
to ensure consistent data handling throughout the parsing pipeline.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Set
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ModelStandardizer:
    """Standardizes data model usage and conversion"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def to_dict(self, model: Union[BaseModel, Dict, Any]) -> Dict[str, Any]:
        """Convert a Pydantic model to a dictionary safely.
        
        Args:
            model: The Pydantic model, dictionary, or other object to convert
            
        Returns:
            Dictionary representation of the model
        """
        if model is None:
            return {}
            
        # Already a dictionary
        if isinstance(model, dict):
            return model
            
        # Pydantic v2 model
        if hasattr(model, 'model_dump') and callable(model.model_dump):
            return model.model_dump()
            
        # Pydantic v1 model
        if hasattr(model, 'dict') and callable(model.dict):
            return model.dict()
            
        # Try attribute-based conversion
        if hasattr(model, '__dict__'):
            # Filter out private attributes
            return {k: v for k, v in model.__dict__.items() if not k.startswith('_')}
            
        # List of models
        if isinstance(model, list):
            return [self.to_dict(item) for item in model]
            
        # Just return the original if it's a simple type
        if isinstance(model, (str, int, float, bool)) or model is None:
            return model
            
        # Fallback - stringify
        self.logger.warning(f"Unable to properly convert type {type(model)} to dict, returning string representation")
        return {"value": str(model)}
    
    def format_date(self, date_value: Any) -> str:
        """Format date objects to consistent string format.
        
        Args:
            date_value: Date object or string to format
            
        Returns:
            Formatted date string or empty string if None
        """
        if date_value is None:
            return ""
            
        # Already a string
        if isinstance(date_value, str):
            return date_value
            
        # DateTime object
        if isinstance(date_value, datetime):
            try:
                return date_value.strftime("%b %Y")  # Format as "Jan 2022"
            except Exception as e:
                self.logger.warning(f"Error formatting date {date_value}: {e}")
                return str(date_value)
                
        # Try to convert to string
        return str(date_value)
    
    def standardize_resume_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Standardize resume data by ensuring consistent formats and types.
        
        Args:
            data: Dictionary of resume data
            
        Returns:
            Standardized resume data dictionary
        """
        if not data:
            return {}
            
        standardized = {}
        
        # Process education entries
        if 'education' in data and data['education']:
            standardized['education'] = []
            for edu in data['education']:
                edu_dict = self.to_dict(edu)
                # Format dates
                if 'start_date' in edu_dict:
                    edu_dict['start_date'] = self.format_date(edu_dict['start_date'])
                if 'end_date' in edu_dict:
                    edu_dict['end_date'] = self.format_date(edu_dict['end_date'])
                standardized['education'].append(edu_dict)
        
        # Process experience entries
        if 'experience' in data and data['experience']:
            standardized['experience'] = []
            for exp in data['experience']:
                exp_dict = self.to_dict(exp)
                # Format dates
                if 'start_date' in exp_dict:
                    exp_dict['start_date'] = self.format_date(exp_dict['start_date'])
                if 'end_date' in exp_dict:
                    exp_dict['end_date'] = self.format_date(exp_dict['end_date'])
                # Ensure description length is appropriate
                if 'description' in exp_dict and exp_dict['description']:
                    # Limit to 1000 chars instead of 400-500 for more complete descriptions
                    if len(exp_dict['description']) > 1000:
                        exp_dict['description'] = exp_dict['description'][:1000]
                standardized['experience'].append(exp_dict)
        
        # Process military experience entries
        if 'military' in data and data['military']:
            standardized['military'] = []
            for mil in data['military']:
                mil_dict = self.to_dict(mil)
                # Format dates
                if 'start_date' in mil_dict:
                    mil_dict['start_date'] = self.format_date(mil_dict['start_date'])
                if 'end_date' in mil_dict:
                    mil_dict['end_date'] = self.format_date(mil_dict['end_date'])
                standardized['military'].append(mil_dict)
        
        # Process skills
        if 'skills' in data and data['skills']:
            if isinstance(data['skills'], dict):
                # Skills are already categorized
                standardized['skills'] = {}
                for category, skills in data['skills'].items():
                    standardized['skills'][category] = [self.to_dict(skill) if not isinstance(skill, str) else skill for skill in skills]
            else:
                # Skills are a list
                standardized['skills'] = [self.to_dict(skill) if not isinstance(skill, str) else skill for skill in data['skills']]
        
        # Copy all other fields directly
        for key, value in data.items():
            if key not in standardized:
                standardized[key] = value
        
        return standardized


def get_model_standardizer() -> ModelStandardizer:
    """Factory function to create and configure a model standardizer
    
    Returns:
        Configured ModelStandardizer instance
    """
    return ModelStandardizer()