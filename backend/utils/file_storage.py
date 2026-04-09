"""File storage and validation utilities."""
import os
import uuid
import shutil
from pathlib import Path
from fastapi import UploadFile, HTTPException

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "./storage/uploads")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME_PREFIXES = ("image/",)


def validate_image_file(file: UploadFile) -> None:
    """Validate uploaded image file type and size."""
    content_type = file.content_type or ""
    if not any(content_type.startswith(p) for p in ALLOWED_MIME_PREFIXES):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Check size by reading (we'll need content anyway)
    # Size check happens after reading in upload_file


async def upload_file(file: UploadFile, subfolder: str = "") -> str:
    """Save an uploaded file and return the public URL path."""
    # Validate content type
    validate_image_file(file)

    # Read content
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size must be less than 10MB")

    # Create directory
    upload_path = Path(UPLOAD_DIR) / subfolder
    upload_path.mkdir(parents=True, exist_ok=True)

    # Generate unique filename
    ext = Path(file.filename or "upload.bin").suffix
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = upload_path / filename

    # Write file
    with open(file_path, "wb") as f:
        f.write(content)

    # Return relative URL path
    return f"/uploads/{subfolder}/{filename}" if subfolder else f"/uploads/{filename}"
