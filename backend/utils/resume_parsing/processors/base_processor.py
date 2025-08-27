"""
Base Processor Abstract Class
Defines interface for all document processors
"""
import abc
from typing import Dict, Any, Optional, Union


class BaseProcessor(abc.ABC):
    """Abstract base class for all document processors"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize processor with configuration
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
    
    @abc.abstractmethod
    async def process(self, input_data: Any) -> Any:
        """
        Process input data and return processed output
        
        Args:
            input_data: Input data to process (type varies by processor)
            
        Returns:
            Processed output (type varies by processor)
        """
        pass