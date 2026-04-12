"""Застосунок FastAPI для сервісу AI-віртуальної примірочної.

Архітектура:
  Шар магазину — товари, замовлення, завантаження, ініціація примірки (/api/*)
  Шар AI рушія   — обробка ШІ, управління завданнями, результати (/ai/*)
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
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

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ai-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Контекстний менеджер життєвого циклу для подій запуску/зупинки."""
    # Запуск
    logger.info("Starting AI Virtual Try-On Service...")

    # Перевірка існування директорій сховища
    settings.ensure_directories()

    # Запуск фонового процесу
    start_worker()

    logger.info(f"Service started on {settings.host}:{settings.port}")

    yield

    # Зупинка
    logger.info("Shutting down service...")


# Створення застосунку FastAPI
app = FastAPI(
    title="AI Virtual Try-On Service",
    description="AI-powered virtual clothing try-on — Shop Layer + AI Engine",
    version="2.0.0",
    lifespan=lifespan,
)

# Додавання CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Реєстрація обробників винятків
app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(ValidationError, validation_error_handler)

# ── Маршрути шару магазину ──────────────────────────────────────────────
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(tryon.router)
app.include_router(uploads.router)

# ── Маршрути шару AI рушія ────────────────────────────────────────────────
app.include_router(ai_engine.router)

# Монтування обслуговування статичних файлів для результатів та артефактів
app.mount("/results", StaticFiles(directory=str(settings.results_path)), name="results")
app.mount("/artifacts", StaticFiles(directory=str(settings.artifacts_path)), name="artifacts")

# Монтування завантажень для обслуговування завантажених файлів
app.mount("/uploads", StaticFiles(directory=str(settings.uploads_path)), name="uploads")

# Монтування товарів
app.mount("/products", StaticFiles(directory=str(settings.products_path)), name="products")


@app.get("/")
async def root():
    """Кореневий ендпоінт."""
    return {
        "service": "AI Virtual Try-On",
        "version": "2.0.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    """Ендпоінт перевірки стану (Health check)."""
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
