"""Minio Storage Service
Provides interface to Minio object storage for storing and retrieving files.
"""

import os
import uuid
import logging
from typing import Dict, Optional, Any, BinaryIO, Tuple
from pathlib import Path
from io import BytesIO
import mimetypes
from datetime import timedelta

from minio import Minio
from minio.error import S3Error
from fastapi import UploadFile, HTTPException

from backend.core.config import settings

logger = logging.getLogger(__name__)

class MinioStorageService:
    """Service for storing and retrieving documents using Minio object storage."""
    
    def __init__(self):
        """Initialize the Minio storage service."""
        self.client = None
        self.bucket_name = settings.minio_bucket_name
        self._initialized = False
        
        # Log initialization attempt
        logger.info(f"MinioStorageService initialized with endpoint {settings.minio_endpoint}")
    
    def _initialize_client(self):
        """Lazy initialization of the Minio client."""
        if self.client is None:
            try:
                self.client = Minio(
                    endpoint=settings.minio_endpoint,
                    access_key=settings.minio_access_key,
                    secret_key=settings.minio_secret_key,
                    secure=settings.minio_secure
                )
                self._ensure_bucket()
                self._initialized = True
                logger.info(f"Successfully initialized Minio client with endpoint {settings.minio_endpoint}")
            except Exception as e:
                logger.warning(f"Failed to initialize Minio client: {e}")
                self._initialized = False
                raise

    def _ensure_bucket(self):
        """Ensure the required bucket exists."""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Bucket {self.bucket_name} created.")
            else:
                logger.info(f"Bucket {self.bucket_name} already exists.")
        except S3Error as e:
            logger.error(f"Error ensuring bucket exists: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error ensuring bucket exists: {str(e)}")
            raise
    
    async def store_document(
        self, 
        file_path: str, 
        file_name: str, 
        content_type: Optional[str] = None, 
        metadata: Optional[Dict] = None
    ) -> str:
        """Store a document in Minio and return its ID.
        
        Args:
            file_path: Path to the file to store
            file_name: Original filename
            content_type: MIME type of the file
            metadata: Additional metadata to store
            
        Returns:
            A unique ID for the stored document
        """
        # Lazy initialize the client
        if not self._initialized:
            self._initialize_client()
        
        # Generate a unique ID for the document
        file_id = str(uuid.uuid4())
        # Extra debug information before upload
        try:
            file_size = os.path.getsize(file_path)
        except Exception:
            file_size = "unknown"
        logger.info(
            f"Uploading to MinIO: file_id={file_id}, file_name={file_name}, size={file_size} bytes, content_type={content_type}"
        )
        
        # Determine content type if not provided
        if not content_type:
            content_type, _ = mimetypes.guess_type(file_name)
            if not content_type:
                content_type = "application/octet-stream"
        
        # Prepare metadata
        if metadata is None:
            metadata = {}
        
        metadata.update({
            'file_name': file_name,
            'content_type': content_type,
            'original_path': file_path
        })
        
        # Upload the file to Minio
        try:
            # Create object name with structure: {file_id}/{file_name}
            object_name = f"{file_id}/{file_name}"
            
            # Upload file to Minio
            self.client.fput_object(
                self.bucket_name,
                object_name,
                file_path,
                content_type=content_type,
                metadata=metadata
            )
            
            logger.info(f"Stored document in Minio: bucket={self.bucket_name}, object={object_name}")
            return file_id
        except S3Error as e:
            logger.error(f"Error storing document in Minio: {str(e)}")
            raise
    
    async def store_document_from_bytes(
        self,
        content: bytes,
        file_name: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """Store a document in Minio from bytes and return its ID.
        
        Args:
            content: File content as bytes
            file_name: Original filename
            content_type: MIME type of the file
            metadata: Additional metadata to store
            
        Returns:
            A unique ID for the stored document
        """
        file_id = str(uuid.uuid4())
        object_name = f"{file_id}/{file_name}"
        try:
            self.client.put_object(
                self.bucket_name,
                object_name,
                BytesIO(content),
                length=len(content),
                content_type=content_type,
                metadata=metadata
            )
            logger.info(f"Stored document in Minio: bucket={self.bucket_name}, object={object_name}")
            return file_id
        except S3Error as e:
            logger.error(f"Error storing document in Minio: {str(e)}")
            raise
    
    async def get_document_info(self, file_id: str) -> Tuple[str, Dict]:
        """Get document information from Minio.
        
        Args:
            file_id: ID of the document to retrieve
            
        Returns:
            Tuple of (object_name, metadata)
        """
        try:
            objects = self.client.list_objects(
                self.bucket_name,
                prefix=f"{file_id}/",
                recursive=True
            )
            for obj in objects:
                object_name = obj.object_name
                stat = self.client.stat_object(self.bucket_name, object_name)
                metadata = stat.metadata
                logger.info(f"Retrieved document info from Minio: bucket={self.bucket_name}, object={object_name}")
                return object_name, metadata

            # Fallback for legacy uploads where the object name was just the file_id without the trailing filename
            try:
                legacy_stat = self.client.stat_object(self.bucket_name, file_id)
                legacy_metadata = legacy_stat.metadata
                logger.info(
                    f"Retrieved document info (legacy format) from Minio: bucket={self.bucket_name}, object={file_id}"
                )
                return file_id, legacy_metadata
            except S3Error:
                pass  # Continue to raise below if not found

            raise FileNotFoundError(f"Document with ID {file_id} not found")
        except S3Error as e:
            logger.error(f"Error retrieving document info from Minio: {str(e)}")
            raise
    
    async def get_document_stream(self, file_id: str) -> Tuple[BinaryIO, Dict[str, str]]:
        """Get a document's content as a stream.
        
        Args:
            file_id: ID of the document
            
        Returns:
            Tuple of (file_stream, metadata)
        """
        try:
            # Get the object name and metadata
            object_name, metadata = await self.get_document_info(file_id)
            
            # Get the object data as a stream
            response = self.client.get_object(self.bucket_name, object_name)
            
            return response, {
                "content_type": metadata.get("content_type", "application/octet-stream"),
                "file_name": metadata.get("file_name", object_name.split("/")[-1]),
                "file_id": file_id
            }
        except (FileNotFoundError, S3Error) as e:
            logger.error(f"Error retrieving document stream: {str(e)}")
            raise
    
    async def get_document_presigned_url(self, file_id: str, expires_in_seconds: int = 3600) -> Dict[str, str]:
        """Generate a pre-signed URL for accessing a document.
        
        Args:
            file_id: ID of the document
            expires_in_seconds: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Dict with URL and metadata about the file
        """
        try:
            # Get the object name and metadata
            object_name, metadata = await self.get_document_info(file_id)
            
            # Always force inline disposition so browsers can render previews instead of forcing a download
            resp_headers = {
                "response-content-disposition": "inline"
            }
            # If we know the content type, explicitly set it to help some browsers render correctly
            if metadata.get("content_type"):
                resp_headers["response-content-type"] = metadata["content_type"]

            url = self.client.presigned_get_object(
                self.bucket_name,
                object_name,
                expires=timedelta(seconds=expires_in_seconds),
                response_headers=resp_headers
            )
            
            return {
                "url": url,
                "content_type": metadata.get("content_type", "application/octet-stream"),
                "file_name": metadata.get("file_name", object_name.split("/")[-1]),
                "file_id": file_id
            }
        
        except (FileNotFoundError, S3Error) as e:
            logger.error(f"Error generating pre-signed URL: {str(e)}")
            raise

    async def document_exists(self, file_id: str) -> bool:
        """Check whether a document with the given file_id exists in MinIO.

        Args:
            file_id: The ID of the document to validate.

        Returns:
            True if the document exists, otherwise False.
        """
        try:
            await self.get_document_info(file_id)
            return True
        except FileNotFoundError:
            return False
        except S3Error as e:
            logger.error(f"Error checking document existence: {str(e)}")
            return False

    def upload_file(self, file_id: str, file_data: bytes) -> bool:
        try:
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=file_id,
                data=BytesIO(file_data),
                length=len(file_data),
                content_type='application/pdf'
            )
            return True
        except Exception as e:
            logger.error(f"Error uploading file {file_id}: {e}")
            return False

    def get_presigned_url(self, file_id: str) -> str:
        try:
            return self.client.presigned_get_object(self.bucket_name, file_id)
        except Exception as e:
            logger.error(f"Error generating pre-signed URL for file {file_id}: {e}")
            return ""

def get_minio_storage_service() -> MinioStorageService:
    """Factory function to get a MinioStorageService instance."""
    return MinioStorageService()
