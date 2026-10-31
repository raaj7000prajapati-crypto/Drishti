import os
import uuid
from abc import ABC, abstractmethod
from typing import Tuple
from fastapi import HTTPException, UploadFile
from app.core.config import settings

class StorageBackend(ABC):
    @abstractmethod
    async def save(self, file: UploadFile) -> Tuple[str, str, int, str]:
        """Returns: (stored_filename_or_path, original_filename, size_bytes, content_type)"""
        pass

    @abstractmethod
    def get_path(self, identifier: str) -> str:
        pass

    @abstractmethod
    def delete(self, identifier: str) -> bool:
        pass

class LocalStorageBackend(StorageBackend):
    def __init__(self, base_dir: str = settings.STORAGE_DIR):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    async def save(self, file: UploadFile) -> Tuple[str, str, int, str]:
        original_name = file.filename or "file.bin"
        ext = os.path.splitext(original_name)[1].lower()
        
        # Check extension
        if ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File extension '{ext}' not allowed. Permitted types: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )

        content = await file.read()
        file_size = len(content)
        
        # Check size (10MB default)
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if file_size > max_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB."
            )

        unique_name = f"{uuid.uuid4().hex}{ext}"
        stored_path = os.path.join(self.base_dir, unique_name)
        
        with open(stored_path, "wb") as f:
            f.write(content)
            
        content_type = file.content_type or "application/octet-stream"
        return unique_name, original_name, file_size, content_type

    def get_path(self, identifier: str) -> str:
        return os.path.join(self.base_dir, identifier)

    def delete(self, identifier: str) -> bool:
        path = self.get_path(identifier)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

# Global storage instance
storage = LocalStorageBackend()
