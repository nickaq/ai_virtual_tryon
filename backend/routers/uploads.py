"""
Uploads API router.
Handles generic file uploads with validation and persistence.
"""
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.db_models import Upload
from ..models.schemas import UploadResponse
from ..utils.file_storage import upload_file, validate_image_file

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


def _cuid() -> str:
    """Generate a short unique ID (similar to cuid)."""
    return uuid.uuid4().hex[:25]


@router.post("", response_model=UploadResponse)
async def upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload an image file. Validates type/size, saves to disk, and returns metadata."""
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")

    # Validate that the file is a supported image format
    validate_image_file(file)

    # Write the file to the uploads directory
    filepath = await upload_file(file, "uploads")

    # Determine file size for the database record
    await file.seek(0)
    content = await file.read()
    file_size = len(content)

    # Persist the Upload record
    upload_record = Upload(
        id=_cuid(),
        filename=file.filename or "file",
        filepath=filepath,
        mimeType=file.content_type or "application/octet-stream",
        size=file_size,
    )
    db.add(upload_record)
    db.commit()
    db.refresh(upload_record)

    return UploadResponse(
        id=upload_record.id,
        filename=upload_record.filename,
        filepath=upload_record.filepath,
        size=upload_record.size,
    )
