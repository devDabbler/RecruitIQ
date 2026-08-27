"""
In-repo text splitter. API-compatible with the RecursiveCharacterTextSplitter
interface popularized by langchain (removed from this project in Phase 1b),
without the dependency.
"""
import re
from typing import List, Optional, Dict, Any, Callable


class CustomTextSplitter:
    """
    A custom text splitter that divides text into chunks based on separators.
    Similar to langchain's RecursiveCharacterTextSplitter but without the dependencies.
    """
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None,
        keep_separator: bool = True,
    ):
        """
        Initialize the text splitter.
        
        Args:
            chunk_size: Maximum size of chunks to return
            chunk_overlap: Overlap in characters between chunks
            separators: List of separators to split on, ordered by priority
            keep_separator: Whether to keep the separator in the chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", ", ", " ", ""]
        self.keep_separator = keep_separator
    
    def split_text(self, text: str) -> List[str]:
        """
        Split text into multiple components based on separators.
        
        Args:
            text: The text to split
            
        Returns:
            List of text chunks
        """
        # Return if text is empty or None
        if not text:
            return []
            
        # First, try to split on the first separator
        if not self.separators:
            return [text]
            
        # Get the appropriate separator to use
        separator = self.separators[0]
        
        # Split the text by separator
        splits = text.split(separator)
        
        # Create the merged chunks based on chunk size and overlap
        chunks = []
        current_chunk = []
        current_length = 0
        
        for split in splits:
            # Skip empty splits
            if not split:
                continue
                
            # If adding this split will make the chunk too big, finalize the current chunk
            if current_chunk and current_length + len(split) + len(separator) > self.chunk_size:
                # Add the current chunk to the list of chunks
                chunks.append(separator.join(current_chunk))
                
                # Create a new chunk with overlap by keeping some of the previous content
                overlap_chunk = []
                overlap_length = 0
                
                # Add splits from the end of the previous chunk to maintain overlap
                for item in reversed(current_chunk):
                    if overlap_length + len(item) + len(separator) > self.chunk_overlap:
                        break
                    overlap_chunk.insert(0, item)
                    overlap_length += len(item) + len(separator)
                
                # Start a new chunk with the overlap content
                current_chunk = overlap_chunk
                current_length = overlap_length
            
            # Add the current split to the chunk
            current_chunk.append(split)
            current_length += len(split) + len(separator)
        
        # Add the last chunk if there's anything
        if current_chunk:
            chunks.append(separator.join(current_chunk))
        
        # If any of the chunks are still too big, recursively split them using the next separator
        final_chunks = []
        
        for chunk in chunks:
            if len(chunk) > self.chunk_size and len(self.separators) > 1:
                # Create a new splitter with the next level of separators
                recursive_splitter = CustomTextSplitter(
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap,
                    separators=self.separators[1:],
                    keep_separator=self.keep_separator,
                )
                
                # Recursively split and add the sub-chunks
                sub_chunks = recursive_splitter.split_text(chunk)
                final_chunks.extend(sub_chunks)
            else:
                final_chunks.append(chunk)
        
        return final_chunks


class RecursiveCharacterTextSplitter(CustomTextSplitter):
    """
    Implementation of the RecursiveCharacterTextSplitter to match langchain's API.
    """
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None,
        **kwargs
    ):
        """Initialize with parameters to match langchain's API."""
        super().__init__(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
            **kwargs
        ) 