"""API request and response models."""
from typing import Optional, Dict
from pydantic import BaseModel, Field
from .job import JobStatus, ErrorCode


class TryOnRequest(BaseModel):
    """Request model for try-on job submission."""
    
    # Required: either URL or path will be provided
    user_image_url: Optional[str] = None
    user_image_path: Optional[str] = None
    
    product_id: Optional[str] = None
    product_image_url: Optional[str] = None
    product_image_path: Optional[str] = None
    
    # Optional parameters
    cloth_category: Optional[str] = Field(None, description="Type of garment: dress, pants, t-shirt, etc.")
    generation_mode: str = Field(default="quality", description="Processing mode: 'fast' or 'quality'")
    pose_hint: Optional[str] = Field(None, description="Optional pose keypoints data")
    mask_hint: Optional[str] = Field(None, description="Optional precomputed mask")
    
    # Constraints
    preserve_face: bool = Field(default=True, description="Preserve face and identity")
    preserve_background: bool = Field(default=True, description="Preserve background")
    realism_level: int = Field(default=3, ge=1, le=5, description="Realism level 1-5")
    max_retries: int = Field(default=2, ge=0, le=3, description="Maximum retry attempts")


class TryOnResponse(BaseModel):
    """Response model for job submission."""
    
    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Initial job status")
    message: str = Field(default="Job submitted successfully")


class StatusResponse(BaseModel):
    """Response model for status check."""
    
    job_id: str
    status: JobStatus
    
    # Optional fields based on status
    result_image_url: Optional[str] = None
    quality_score: Optional[float] = None
    debug_artifacts: Optional[Dict[str, str]] = None
    
    # Error information
    error_code: Optional[ErrorCode] = None
    error_message: Optional[str] = None
    
    # Metadata
    retry_count: int = 0
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
