import os
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
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

        if ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File extension '{ext}' not allowed. Permitted types: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )

        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        content = await file.read(max_bytes + 1)
        file_size = len(content)
        if file_size > max_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB."
            )

        content_type = self._validate_file_type(ext, content)
        unique_name = f"{uuid.uuid4().hex}{ext}"
        stored_path = os.path.join(self.base_dir, unique_name)

        with open(stored_path, "wb") as f:
            f.write(content)

        return unique_name, original_name, file_size, content_type

    def get_path(self, identifier: str) -> str:
        if not identifier or Path(identifier).name != identifier:
            raise ValueError("Invalid storage identifier")
        base_path = Path(self.base_dir).resolve()
        path = (base_path / identifier).resolve()
        if path.parent != base_path:
            raise ValueError("Invalid storage identifier")
        return str(path)

    def delete(self, identifier: str) -> bool:
        path = self.get_path(identifier)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    @staticmethod
    def _validate_file_type(extension: str, content: bytes) -> str:
        if extension == ".pdf" and content.startswith(b"%PDF-"):
            return "application/pdf"
        if extension == ".png" and content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if extension in {".jpg", ".jpeg"} and content.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if extension == ".docx":
            try:
                with zipfile.ZipFile(BytesIO(content)) as archive:
                    members = set(archive.namelist())
                if "[Content_Types].xml" in members and "word/document.xml" in members:
                    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            except (zipfile.BadZipFile, OSError):
                pass
        if extension == ".txt":
            try:
                decoded = content.decode("utf-8-sig")
                if "\x00" not in decoded:
                    return "text/plain"
            except UnicodeDecodeError:
                pass

        raise HTTPException(
            status_code=400,
            detail="File content does not match its allowed file type.",
        )

# Global storage instance
storage = LocalStorageBackend()
