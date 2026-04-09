"""
Try-On API router (Shop Layer).

Handles photo upload for virtual try-on and job status retrieval.
This is the shop-facing interface — it accepts user uploads and delegates
to the AI Engine for processing via direct function call (no HTTP self-call).
"""
import uuid
import logging
import asyncio
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from ..database import get_db
from ..models.db_models import Upload, TryOnJob
from ..models.schemas import TryOnUploadResponse, TryOnStatusResponse
from ..utils.rate_limit import rate_limiter
from ..utils.file_storage import upload_file, validate_image_file

logger = logging.getLogger("ai-service")

router = APIRouter(prefix="/api/try-on", tags=["try-on"])


def _cuid() -> str:
    """Generate a short unique ID (similar to cuid)."""
    return uuid.uuid4().hex[:25]


async def _process_job_async(
    job_id: str,
    user_image_path: str,
    product_image_path: str,
):
    """
    Process a try-on job asynchronously.
    Updates the TryOnJob status in the database and calls the AI processing
    pipeline directly via function import (no HTTP self-call).
    """
    from ..database import SessionLocal
    from ..models.job import Job, JobStatus
    from ai.workers.processor import process_job

    db = SessionLocal()
    try:
        # Mark job as PROCESSING
        job_record = db.query(TryOnJob).filter(TryOnJob.id == job_id).first()
        if job_record:
            job_record.status = "PROCESSING"
            job_record.startedAt = datetime.now(timezone.utc)
            db.commit()

        # Create Job model and process directly
        job = Job(
            job_id=job_id,
            user_image_path=user_image_path,
            product_image_path=product_image_path,
            cloth_category="upper_body",
            generation_mode="quality",
            realism_level=3,
            preserve_face=True,
            preserve_background=True,
        )

        await process_job(job)

        # Persist result into the database
        job_record = db.query(TryOnJob).filter(TryOnJob.id == job_id).first()
        if job_record:
            job_record.status = "DONE" if job.status == JobStatus.DONE else "FAILED"
            job_record.resultPath = f"storage/results/{job.job_id}.png" if job.status == JobStatus.DONE else None
            job_record.qualityScore = job.quality_score
            job_record.errorCode = job.error_code
            job_record.errorMessage = job.error_message
            job_record.completedAt = datetime.now(timezone.utc)
            db.commit()

    except Exception as e:
        logger.error(f"AI processing error for job {job_id}: {e}")
        job_record = db.query(TryOnJob).filter(TryOnJob.id == job_id).first()
        if job_record:
            job_record.status = "FAILED"
            job_record.errorCode = "AI_SERVICE_ERROR"
            job_record.errorMessage = str(e)
            job_record.completedAt = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()


@router.post("/upload", response_model=TryOnUploadResponse, status_code=201)
async def upload_tryon(
    request: Request,
    photo: UploadFile = File(...),
    productId: str = Form(...),
    db: Session = Depends(get_db),
):
    """Upload a user photo and start a virtual try-on job for the given product."""
    # Enforce per-IP rate limiting (5 requests per hour)
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
    rl_result = rate_limiter.check(ip, max_requests=5, window_seconds=3600)
    if rl_result["limited"]:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")

    # Validate that the uploaded file is a valid image
    validate_image_file(photo)

    # Persist user photo to disk
    user_photo_path = await upload_file(photo, "try-on/user-photos")

    # Determine file size for the Upload record
    await photo.seek(0)
    content = await photo.read()
    file_size = len(content)

    # Create Upload records (user photo + product image placeholder)
    user_upload = Upload(
        id=_cuid(),
        filename=photo.filename or "photo.jpg",
        filepath=user_photo_path,
        mimeType=photo.content_type or "image/jpeg",
        size=file_size,
    )
    db.add(user_upload)

    product_upload = Upload(
        id=_cuid(),
        filename="product.jpg",
        filepath=f"/products/{productId}.jpg",
        mimeType="image/jpeg",
        size=0,
    )
    db.add(product_upload)

    # Create the TryOnJob record
    job = TryOnJob(
        id=_cuid(),
        productId=productId,
        userImageId=user_upload.id,
        productImageId=product_upload.id,
        status="QUEUED",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Resolve absolute image paths for the AI engine
    project_root = Path(__file__).resolve().parent.parent.parent
    abs_user_path = str(project_root / "storage" / "uploads" / user_photo_path.lstrip("/"))
    abs_product_path = str(project_root / "storage" / "products" / f"{productId}.jpg")

    # Fire-and-forget async processing (direct call, no HTTP self-call)
    asyncio.create_task(
        _process_job_async(job.id, abs_user_path, abs_product_path)
    )

    return TryOnUploadResponse(
        jobId=job.id,
        status=job.status,
        message="Photo uploaded. Processing started.",
    )


@router.get("/{job_id}", response_model=TryOnStatusResponse)
def get_tryon_status(job_id: str, db: Session = Depends(get_db)):
    """Get the current status of a try-on job by its ID."""
    job = db.query(TryOnJob).filter(TryOnJob.id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Resolve user photo URL from the linked Upload record
    user_photo_url = None
    if job.user_image:
        user_photo_url = job.user_image.filepath

    return TryOnStatusResponse(
        id=job.id,
        status=job.status,
        productId=job.productId,
        userPhotoUrl=user_photo_url,
        resultPhotoUrl=job.resultPath,
        errorMessage=job.errorMessage,
        createdAt=job.createdAt,
        updatedAt=job.updatedAt,
    )
