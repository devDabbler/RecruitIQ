import os
import uuid
from typing import Dict, Optional
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class StorageService:
    """Service for storing and retrieving documents."""
    
    def __init__(self, storage_dir: str = "storage"):
        """Initialize the storage service.
        
        Args:
            storage_dir: Base directory for storing files
        """
        self.storage_dir = storage_dir
        self._ensure_storage_dir()
    
    def _ensure_storage_dir(self):
        """Ensure the storage directory exists."""
        os.makedirs(self.storage_dir, exist_ok=True)
    
    async def store_document(
        self, 
        file_path: str, 
        file_name: str, 
        content_type: str, 
        metadata: Optional[Dict] = None
    ) -> str:
        """Store a document and return its ID.
        
        Args:
            file_path: Path to the file to store
            file_name: Original filename
            content_type: MIME type of the file
            metadata: Additional metadata to store
            
        Returns:
            A unique ID for the stored document
        """
        # Generate a unique ID for the document
        file_id = str(uuid.uuid4())
        
        # Create a directory for this document
        doc_dir = os.path.join(self.storage_dir, file_id)
        os.makedirs(doc_dir, exist_ok=True)
        
        # Copy the file to the storage directory using aiofiles for async I/O
        import aiofiles
        dest_path = os.path.join(doc_dir, file_name)
        async with aiofiles.open(file_path, 'rb') as src, aiofiles.open(dest_path, 'wb') as dst:
            content = await src.read()
            await dst.write(content)
        
        # Store metadata
        if metadata is None:
            metadata = {}
        
        metadata.update({
            'file_name': file_name,
            'content_type': content_type,
            'original_path': file_path
        })
        
        # Save metadata to a JSON file asynchronously
        import json
        async with aiofiles.open(os.path.join(doc_dir, 'metadata.json'), 'w') as f:
            await f.write(json.dumps(metadata))
        
        logger.info(f"Stored document {file_id} at {dest_path}")
        return file_id
    
    async def get_document_path(self, file_id: str) -> str:
        """Get the path to a stored document.
        
        Args:
            file_id: ID of the document to retrieve
            
        Returns:
            Path to the document
        """
        doc_dir = os.path.join(self.storage_dir, file_id)
        import aiofiles.os
        if not await aiofiles.os.path.exists(doc_dir):
            raise FileNotFoundError(f"Document with ID {file_id} not found")
        
        # Find the main file (not metadata.json)
        files = [f for f in await aiofiles.os.listdir(doc_dir) if f != 'metadata.json']
        if not files:
            raise FileNotFoundError(f"No files found for document {file_id}")
        
        return os.path.join(doc_dir, files[0])
    
    async def get_document_metadata(self, file_id: str) -> Dict:
        """Get metadata for a stored document.
        
        Args:
            file_id: ID of the document
            
        Returns:
            Document metadata
        """
        metadata_path = os.path.join(self.storage_dir, file_id, 'metadata.json')
        import aiofiles
        import json
        if not await aiofiles.os.path.exists(metadata_path):
            raise FileNotFoundError(f"Metadata for document {file_id} not found")
        async with aiofiles.open(metadata_path, 'r') as f:
            content = await f.read()
            return json.loads(content)
