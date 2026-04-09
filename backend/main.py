"""FastAPI application for AI Virtual Try-On service."""
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import uuid
import logging
from typing import Optional
from pathlib import Path
from pydantic import ValidationError

from .config import settings
from .models.job import Job, JobStatus
from .models.requests import TryOnRequest, TryOnResponse, StatusResponse
from ai.workers import job_queue, start_worker
from .database import engine, Base
from .models.db_models import Product, Order, OrderItem, Upload, TryOnJob
from .utils.error_handler import (
    ApiError,
    api_error_handler,
    validation_error_handler,
    generic_error_handler,
)
from .routers import products, orders, tryon, uploads

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ai-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup
    logger.info("Starting AI Virtual Try-On Service...")

    # Ensure storage directories exist
    settings.ensure_directories()

    # Create DB tables (if not exist — tables already created by Prisma migrations)
    # Base.metadata.create_all(bind=engine)  # Uncomment if you need to create tables

    # Start background worker
    start_worker()

    logger.info(f"Service started on {settings.host}:{settings.port}")

    yield

    # Shutdown
    logger.info("Shutting down service...")


# Create FastAPI app
app = FastAPI(
    title="AI Virtual Try-On Service",
    description="AI-powered virtual clothing try-on service with product catalog and orders",
    version="2.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register exception handlers
app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(ValidationError, validation_error_handler)

# Register API routers
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(tryon.router)
app.include_router(uploads.router)

# Mount static file serving for results and artifacts
app.mount("/results", StaticFiles(directory=str(settings.results_path)), name="results")
app.mount("/artifacts", StaticFiles(directory=str(settings.artifacts_path)), name="artifacts")

# Mount uploads for serving uploaded files
uploads_dir = Path("./storage/uploads")
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "AI Virtual Try-On",
        "version": "2.0.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    stats = job_queue.get_stats()
    return {"status": "healthy", "queue_stats": stats}


@app.post("/ai/process")
async def process_with_paths(request_data: dict):
    """
    Process images using file paths (internal AI processing endpoint).
    """
    from .models.ai_requests import AIProcessRequest, AIProcessResponse
    from ai.workers.processor import process_job

    try:
        req = AIProcessRequest(**request_data)

        job = Job(
            job_id=req.job_id,
            user_image_path=req.user_image_path,
            product_image_path=req.product_image_path,
            cloth_category=req.cloth_category,
            generation_mode=req.generation_mode,
            pose_hint=req.pose_hint,
            mask_hint=req.mask_hint,
            realism_level=req.realism_level,
            preserve_face=req.preserve_face,
            preserve_background=req.preserve_background,
            max_retries=req.max_retries,
        )

        process_job(job)

        if job.status == JobStatus.DONE:
            result_relative_path = f"storage/results/{job.job_id}.png"
            return AIProcessResponse(
                job_id=job.job_id,
                status="DONE",
                result_path=result_relative_path,
                quality_score=job.quality_score,
            ).model_dump()
        else:
            return AIProcessResponse(
                job_id=job.job_id,
                status="FAILED",
                error_code=job.error_code,
                error_message=job.error_message,
            ).model_dump()
    except Exception as e:
        import traceback

        logger.error(f"Processing error: {e}")
        traceback.print_exc()
        return AIProcessResponse(
            job_id=request_data.get("job_id", "unknown"),
            status="FAILED",
            error_code="PROCESSING_ERROR",
            error_message=str(e),
        ).model_dump()


@app.post("/api/tryon/submit", response_model=TryOnResponse)
async def submit_tryon(
    user_image: Optional[UploadFile] = File(None),
    user_image_url: Optional[str] = Form(None),
    product_image: Optional[UploadFile] = File(None),
    product_image_url: Optional[str] = Form(None),
    product_id: Optional[str] = Form(None),
    cloth_category: Optional[str] = Form(None),
    generation_mode: str = Form("quality"),
    pose_hint: Optional[str] = Form(None),
    mask_hint: Optional[str] = Form(None),
    preserve_face: bool = Form(True),
    preserve_background: bool = Form(True),
    realism_level: int = Form(3),
    max_retries: int = Form(2),
):
    """Submit a virtual try-on job (legacy endpoint)."""
    job_id = str(uuid.uuid4())

    user_image_path = None
    if user_image:
        upload_path = settings.uploads_path / f"{job_id}_user{Path(user_image.filename).suffix}"
        with open(upload_path, "wb") as f:
            content = await user_image.read()
            f.write(content)
        user_image_path = str(upload_path)
    elif not user_image_url:
        raise HTTPException(status_code=400, detail="Either user_image file or user_image_url must be provided")

    product_image_path = None
    if product_image:
        upload_path = settings.products_path / f"{job_id}_product{Path(product_image.filename).suffix}"
        with open(upload_path, "wb") as f:
            content = await product_image.read()
            f.write(content)
        product_image_path = str(upload_path)
    elif not product_image_url:
        raise HTTPException(status_code=400, detail="Either product_image file or product_image_url must be provided")

    job = Job(
        job_id=job_id,
        user_image_path=user_image_path,
        user_image_url=user_image_url,
        product_id=product_id,
        product_image_path=product_image_path,
        product_image_url=product_image_url,
        cloth_category=cloth_category,
        generation_mode=generation_mode,
        pose_hint=pose_hint,
        mask_hint=mask_hint,
        max_retries=max_retries,
        preserve_face=preserve_face,
        preserve_background=preserve_background,
        realism_level=realism_level,
    )

    await job_queue.submit_job(job)

    return TryOnResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        message="Job submitted successfully",
    )


@app.get("/api/tryon/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str):
    """Get status of a try-on job (legacy endpoint)."""
    job = await job_queue.get_job(job_id)

    if job is None:
        from fastapi import HTTPException  # already imported
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return StatusResponse(
        job_id=job.job_id,
        status=job.status,
        result_image_url=job.result_image_url,
        quality_score=job.quality_score,
        debug_artifacts=job.debug_artifacts if settings.debug else None,
        error_code=job.error_code,
        error_message=job.error_message,
        retry_count=job.retry_count,
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )


@app.get("/api/tryon/result/{job_id}")
async def get_result(job_id: str):
    """Get result image for a completed job (legacy endpoint)."""
    job = await job_queue.get_job(job_id)

    if job is None:
        from fastapi import HTTPException  # already imported
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job.status != JobStatus.DONE:
        from fastapi import HTTPException  # already imported
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed. Current status: {job.status}",
        )

    result_path = settings.results_path / f"{job_id}.png"

    if not result_path.exists():
        from fastapi import HTTPException  # already imported
        raise HTTPException(status_code=404, detail="Result image not found")

    return FileResponse(result_path, media_type="image/png")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
