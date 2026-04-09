# API Documentation

## Base URL
```
http://localhost:8000
```

## Job Status Flow
```
QUEUED → PROCESSING → DONE | FAILED
```

---

## Shop Layer

### Products

#### GET /api/products
List products with filtering and pagination.

**Query Parameters:**
- `page` (int, optional) — Page number (default: 1)
- `limit` (int, optional) — Items per page (default: 20, max: 100)
- `category` (string, optional) — Filter by category: `jackets`, `pants`, `shirts`, `shoes`, `accessories`
- `search` (string, optional) — Full-text search in name and description
- `minPrice` (float, optional) — Minimum price filter
- `maxPrice` (float, optional) — Maximum price filter
- `season` (string, optional) — Season filter: `spring`, `summer`, `fall`, `winter`, `all-season`

**Response (200):**
```json
{
  "products": [
    {
      "id": "cm65yw7fh0000144hfpnqbuvp",
      "name": "Premium Wool Coat",
      "description": "...",
      "price": 299.99,
      "category": "jackets",
      "sizes": ["S", "M", "L", "XL"],
      "colors": ["Black", "Dark Gray"],
      "season": "winter",
      "composition": "90% wool, 10% cashmere",
      "inStock": true,
      "imageUrl": null
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 10,
    "totalPages": 1
  }
}
```

#### GET /api/products/{product_id}
Get a single product by ID.

**Response (200):** Single product object (same schema as above).

**Response (404):**
```json
{ "detail": "Product not found" }
```

---

### Orders

#### POST /api/orders
Create a new order.

**Request Body:**
```json
{
  "items": [
    {
      "productId": "cm65yw7fh0000144hfpnqbuvp",
      "quantity": 2,
      "selectedSize": "M",
      "selectedColor": "Black"
    }
  ],
  "contactName": "John Doe",
  "email": "john@example.com",
  "phone": "+1234567890",
  "address": "123 Main St",
  "city": "Kyiv",
  "postalCode": "01001",
  "country": "Ukraine"
}
```

**Response (201):**
```json
{
  "orderId": "...",
  "status": "PENDING",
  "total": 599.98
}
```

#### GET /api/orders
List the 20 most recent orders with items and product details.

**Response (200):**
```json
{
  "orders": [
    {
      "id": "...",
      "status": "PENDING",
      "total": 599.98,
      "createdAt": "2026-...",
      "items": [...]
    }
  ]
}
```

---

### Try-On (Shop-Facing)

#### POST /api/try-on/upload
Upload a user photo to initiate a virtual try-on job.

**Rate Limit:** 5 requests per hour per IP.

**Form Data:**
- `productId` (string, required) — Product ID to try on
- `photo` (File, required) — User photo (max 10MB, image/*)

**Response (201):**
```json
{
  "jobId": "...",
  "status": "QUEUED",
  "message": "Photo uploaded. Processing started."
}
```

**Response (429):**
```json
{ "detail": "Rate limit exceeded. Please try again later." }
```

#### GET /api/try-on/{job_id}
Get current status of a try-on job.

**Response (200):**
```json
{
  "id": "...",
  "status": "DONE",
  "productId": "...",
  "userPhotoUrl": "/uploads/try-on/user-photos/...",
  "resultPhotoUrl": "storage/results/...",
  "errorMessage": null,
  "createdAt": "...",
  "updatedAt": "..."
}
```

---

## AI Engine Layer

### POST /ai/process
Internal endpoint for path-based AI processing. Called by the shop layer.

**Request Body:**
```json
{
  "job_id": "uuid-string",
  "user_image_path": "/absolute/path/to/user.jpg",
  "product_image_path": "/absolute/path/to/product.jpg",
  "cloth_category": "upper_body",
  "generation_mode": "quality",
  "warp_mode": "tps",
  "refinement_mode": "img2img",
  "realism_level": 3,
  "preserve_face": true,
  "preserve_background": true,
  "max_retries": 2
}
```

**Response (200):**
```json
{
  "job_id": "...",
  "status": "DONE",
  "result_path": "storage/results/{job_id}.png",
  "quality_score": 0.85,
  "error_code": null,
  "error_message": null
}
```

### POST /ai/tryon/submit
Submit a virtual try-on job via file upload or URL (legacy endpoint).

**Form Data:**
- `user_image` (File, optional) or `user_image_url` (string, optional) — User photo
- `product_image` (File, optional) or `product_image_url` (string, optional) — Garment image
- `product_id` (string, optional) — Product ID
- `cloth_category` (string, optional) — Garment type
- `generation_mode` (string, default: `"quality"`) — `"fast"` or `"quality"`
- `warp_mode` (string, default: `"tps"`) — `"affine"` or `"tps"`
- `refinement_mode` (string, default: `"img2img"`) — `"img2img"` or `"inpainting"`
- `preserve_face` (bool, default: true)
- `preserve_background` (bool, default: true)
- `realism_level` (int, default: 3) — 1–5 scale
- `max_retries` (int, default: 2) — 0–3

**Response (200):**
```json
{
  "job_id": "...",
  "status": "QUEUED",
  "message": "Job submitted successfully"
}
```

### GET /ai/tryon/status/{job_id}
Get detailed status of a try-on job with quality metrics.

**Response (200):**
```json
{
  "job_id": "...",
  "status": "DONE",
  "result_image_url": "/results/{job_id}.png",
  "quality_score": 0.85,
  "debug_artifacts": {
    "person_mask": "/artifacts/{job_id}/person_mask.png",
    "quality_report": "/artifacts/{job_id}/quality_report.json"
  },
  "error_code": null,
  "error_message": null,
  "retry_count": 0,
  "created_at": "...",
  "updated_at": "...",
  "started_at": "...",
  "completed_at": "..."
}
```

### GET /ai/tryon/result/{job_id}
Download the result image for a completed job.

**Response (200):** PNG image file.

**Response (400):**
```json
{ "detail": "Job is not completed. Current status: PROCESSING" }
```

---

## System Endpoints

### GET /
Service info.
```json
{ "service": "AI Virtual Try-On", "version": "2.0.0", "status": "running" }
```

### GET /health
Health check with queue statistics.
```json
{ "status": "healthy", "queue_stats": { "pending": 0, "processing": 0, "completed": 5 } }
```

---

## Error Responses

All endpoints return errors in the format:
```json
{ "detail": "Error description" }
```

**HTTP Status Codes:**
- `400` — Bad Request (invalid input data)
- `404` — Not Found (resource does not exist)
- `429` — Too Many Requests (rate limit exceeded)
- `500` — Internal Server Error

**AI Error Codes (in job status):**
- `INVALID_IMAGE_FORMAT` — Unsupported image type
- `IMAGE_TOO_LARGE` — Image exceeds size limit
- `SEGMENTATION_FAILED` — Person segmentation failed
- `POSE_FAILED` — Pose detection failed
- `WARP_FAILED` — Garment alignment/warping failed
- `DIFFUSION_ERROR` — Diffusion refinement failed
- `QUALITY_CHECK_FAILED` — Quality check failed
- `STORAGE_ERROR` — File storage error
- `TIMEOUT` — Operation timed out
- `UNKNOWN_ERROR` — Unexpected error

---

## Security

### Rate Limiting
- Try-on upload: 5 requests/hour per IP
- Other endpoints: no limits (configurable)

### File Upload
- Maximum size: 10MB
- Allowed types: image/*
- Auto-cleanup after 7 days

### Data Privacy
- Personal data is not logged
- User photos are protected and accessible only by job ID
- Automatic deletion after processing

---

## Development

### Testing API

```bash
# List products
curl http://localhost:8000/api/products

# Get product by ID
curl http://localhost:8000/api/products/cm65yw7fh0000144hfpnqbuvp

# Create order
curl -X POST http://localhost:8000/api/orders \
  -H "Content-Type: application/json" \
  -d '{"items":[...],"contactName":"...","email":"...",...}'

# Upload try-on photo
curl -X POST http://localhost:8000/api/try-on/upload \
  -F "productId=..." \
  -F "photo=@/path/to/photo.jpg"

# Check job status
curl http://localhost:8000/api/try-on/{jobId}
```

### Logs

Logs are stored in the `logs/` directory:
- `error.log` — errors only
- `combined.log` — all logs

Personal data is automatically filtered from logs.
