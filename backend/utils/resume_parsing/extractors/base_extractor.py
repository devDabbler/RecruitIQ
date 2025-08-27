from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseExtractor(ABC):
    """Abstract base class for all resume data extractors."""

    @abstractmethod
    def extract(self, raw_text: str, file_path: str) -> Dict[str, Any]:
        """
        Extracts information from the raw text of a resume.

        Args:
            raw_text (str): The raw text content of the resume.
            file_path (str): The path to the original resume file.

        Returns:
            Dict[str, Any]: A dictionary containing the extracted resume data.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the extractor."""
        pass
