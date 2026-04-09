# AI Virtual Try-On

AI-powered virtual clothing try-on service. Users upload a photo and select a garment from the catalog — the system generates a realistic composite showing the person wearing the selected clothing.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Frontend (Next.js)                  │
│                   http://localhost:3000                   │
└───────────────────────┬─────────────────────────────────┘
                        │  REST API
┌───────────────────────▼─────────────────────────────────┐
│                   FastAPI Backend                        │
│                  http://localhost:8000                    │
│                                                          │
│  ┌──────────────────┐    ┌───────────────────────────┐  │
│  │   Shop Layer      │    │     AI Engine Layer        │  │
│  │                   │    │                            │  │
│  │  /api/products    │    │  /ai/process               │  │
│  │  /api/orders      │    │  /ai/tryon/submit          │  │
│  │  /api/uploads     │    │  /ai/tryon/status/{id}     │  │
│  │  /api/try-on/*    │    │  /ai/tryon/result/{id}     │  │
│  └──────────────────┘    └──────────┬────────────────┘  │
│                                      │                   │
│  ┌───────────────────────────────────▼────────────────┐  │
│  │              11-Step AI Pipeline                    │  │
│  │                                                     │  │
│  │  1. Validation & Loading (image_loader)             │  │
│  │  2. Human Analysis — Pose Detection (pose_detector) │  │
│  │  3. Segmentation (segmentation)                     │  │
│  │  4. Clothing Processing (garment_prep)              │  │
│  │  5. Geometric Alignment — TPS Warping (tps_warp)    │  │
│  │  6. Occlusion Handling (occlusion)                  │  │
│  │  7. Compositing (alignment)                         │  │
│  │  8. Diffusion Refinement (diffusion)                │  │
│  │  9. Quality Evaluation (quality_control)            │  │
│  │ 10. Storage (storage)                               │  │
│  │ 11. Response                                        │  │
│  └─────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

## Project Structure

```
ai_try_on/
├── ai/                       # AI processing engine
│   ├── services/             # Pipeline stage modules
│   │   ├── image_loader.py   # Stage 1: image loading & normalization
│   │   ├── pose_detector.py  # Stage 2: MediaPipe pose detection
│   │   ├── segmentation.py   # Stage 3: person/torso/arms/head segmentation
│   │   ├── garment_prep.py   # Stage 4: garment background removal & anchors
│   │   ├── tps_warp.py       # Stage 5: Thin-Plate Spline warping (own impl.)
│   │   ├── occlusion.py      # Stage 6: Z-order layered occlusion handling
│   │   ├── alignment.py      # Stage 7: alignment orchestration & compositing
│   │   ├── diffusion.py      # Stage 8: Stable Diffusion refinement (img2img/inpaint)
│   │   ├── quality_control.py# Stage 9: quality gate with structured reports
│   │   └── storage.py        # Stage 10: result & debug artifact storage
│   └── workers/
│       ├── processor.py      # Background job processor (11-step pipeline)
│       └── job_queue.py      # In-memory job queue
├── backend/                  # FastAPI application
│   ├── main.py               # App entrypoint, CORS, lifespan
│   ├── config.py             # Pydantic settings (env-based)
│   ├── database.py           # SQLAlchemy engine & session
│   ├── models/               # Data models
│   │   ├── job.py            # Job status & error codes
│   │   ├── db_models.py      # ORM models (Product, Order, TryOnJob, etc.)
│   │   ├── schemas.py        # Pydantic API schemas
│   │   ├── requests.py       # Try-on request/response models
│   │   └── ai_requests.py    # Internal AI processing request/response
│   ├── routers/              # API route modules
│   │   ├── products.py       # GET /api/products
│   │   ├── orders.py         # POST/GET /api/orders
│   │   ├── tryon.py          # POST /api/try-on/upload, GET /api/try-on/{id}
│   │   ├── uploads.py        # File upload utilities
│   │   └── ai_engine.py      # AI processing endpoints
│   └── utils/                # Shared utilities
│       ├── image_utils.py    # OpenCV/PIL helpers
│       ├── validation.py     # File format & size validation
│       ├── file_storage.py   # Disk file operations
│       ├── error_handler.py  # Global exception handlers
│       └── rate_limit.py     # IP-based rate limiting
├── frontend/                 # Next.js frontend application
├── experiments/              # Test scripts & seed data
├── docs/                     # API documentation
├── storage/                  # Runtime file storage (uploads, results, artifacts)
├── models/                   # ML model weights (gitignored)
└── docker/                   # Docker configuration
```

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+ (for frontend)
- SQLite (default) or PostgreSQL

### Backend Setup

```bash
# Install Python dependencies
pip install -r backend/requirements.txt

# Start the FastAPI server (port 8000)
cd ai_try_on
python -m backend.main

# Or with auto-reload for development
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev    # starts on http://localhost:3000
```

### Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `file:./dev.db` | SQLite/PostgreSQL connection string |
| `DIFFUSION_MODEL_ID` | `runwayml/stable-diffusion-v1-5` | Stable Diffusion model for refinement |
| `DIFFUSION_DEVICE` | `cpu` | Device for inference: `cpu`, `cuda`, `mps` |
| `QUALITY_THRESHOLD` | `0.7` | Minimum quality score (0.0–1.0) |
| `MAX_RETRIES` | `2` | Max diffusion retry attempts |
| `DEBUG` | `false` | Enable debug mode & artifact saving |
| `PORT` | `8000` | Backend server port |

## Key Features

- **TPS Warping** — Thin-Plate Spline deformation aligns garments to body pose with non-linear warping (own implementation)
- **Layered Occlusion** — Z-order compositing ensures correct arm-over-garment, head-over-all rendering
- **Dual Refinement** — Choice of img2img or inpainting Stable Diffusion for photorealistic output
- **Quality Gate** — Structured quality reports with per-check scores, thresholds, and retry recommendations
- **Debug Artifacts** — Every pipeline stage saves intermediate masks, composites, and metrics for analysis

## License

This project is developed as a diploma thesis. All rights reserved.
