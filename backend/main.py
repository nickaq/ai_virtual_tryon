"""FastAPI application for AI Virtual Try-On service.

Architecture:
  Shop Layer   — products, orders, uploads, try-on initiation (/api/*)
  AI Engine    — AI processing, job management, results (/ai/*)
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
from pathlib import Path
from pydantic import ValidationError

from .config import settings
from .models.db_models import Product, Order, OrderItem, Upload, TryOnJob
from .utils.error_handler import (
    ApiError,
    api_error_handler,
    validation_error_handler,
)
from .routers import products, orders, tryon, uploads, ai_engine
from ai.workers import job_queue, start_worker

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

    # Start background worker
    start_worker()

    logger.info(f"Service started on {settings.host}:{settings.port}")

    yield

    # Shutdown
    logger.info("Shutting down service...")


# Create FastAPI app
app = FastAPI(
    title="AI Virtual Try-On Service",
    description="AI-powered virtual clothing try-on — Shop Layer + AI Engine",
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

# ── Shop Layer routers ──────────────────────────────────────────────
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(tryon.router)
app.include_router(uploads.router)

# ── AI Engine router ────────────────────────────────────────────────
app.include_router(ai_engine.router)

# Mount static file serving for results and artifacts
app.mount("/results", StaticFiles(directory=str(settings.results_path)), name="results")
app.mount("/artifacts", StaticFiles(directory=str(settings.artifacts_path)), name="artifacts")

# Mount uploads for serving uploaded files
uploads_dir = Path("./storage/uploads")
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

# Mount products
products_dir = Path("./storage/products")
products_dir.mkdir(parents=True, exist_ok=True)
app.mount("/products", StaticFiles(directory=str(products_dir)), name="products")


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
