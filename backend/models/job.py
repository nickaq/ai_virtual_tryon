"""Job status tracking and data models."""
from enum import Enum
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job processing status."""
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    FAILED = "FAILED"


class ErrorCode(str, Enum):
    """Error codes for job failures."""
    INVALID_IMAGE_FORMAT = "INVALID_IMAGE_FORMAT"
    IMAGE_TOO_LARGE = "IMAGE_TOO_LARGE"
    SEGMENTATION_FAILED = "SEGMENTATION_FAILED"
    POSE_FAILED = "POSE_FAILED"
    WARP_FAILED = "WARP_FAILED"
    DIFFUSION_ERROR = "DIFFUSION_ERROR"
    TIMEOUT = "TIMEOUT"
    STORAGE_ERROR = "STORAGE_ERROR"
    QUALITY_CHECK_FAILED = "QUALITY_CHECK_FAILED"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class Job(BaseModel):
    """Job data model for tracking try-on requests."""
    
    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(default=JobStatus.QUEUED, description="Current job status")
    
    # Input data
    user_image_path: Optional[str] = None
    user_image_url: Optional[str] = None
    product_id: Optional[str] = None
    product_image_path: Optional[str] = None
    product_image_url: Optional[str] = None
    cloth_category: Optional[str] = None
    pose_hint: Optional[str] = None
    mask_hint: Optional[str] = None
    
    # Processing options
    generation_mode: str = Field(default="quality", description="Processing mode: 'fast' or 'quality'")
    warp_mode: str = Field(default="tps", description="Warping method: 'tps' (Thin-Plate Spline) or 'affine'")
    refinement_mode: str = Field(default="img2img", description="Diffusion refinement: 'img2img' or 'inpainting'")
    max_retries: int = Field(default=2, description="Maximum retry attempts")
    preserve_face: bool = Field(default=True, description="Preserve face in result")
    preserve_background: bool = Field(default=True, description="Preserve background in result")
    realism_level: int = Field(default=3, ge=1, le=5, description="Realism level 1-5")
    
    # Output data
    result_image_url: Optional[str] = None
    quality_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Quality assessment score")
    
    # Debug artifacts
    debug_artifacts: Dict[str, str] = Field(default_factory=dict, description="Debug artifact URLs")
    
    # Error information
    error_code: Optional[ErrorCode] = None
    error_message: Optional[str] = None
    
    # Tracking
    retry_count: int = Field(default=0, description="Current retry count")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    model_config = {"use_enum_values": True}
    
    def mark_processing(self):
        """Mark job as processing."""
        self.status = JobStatus.PROCESSING
        self.started_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
    
    def mark_done(self, result_url: str, quality_score: float):
        """Mark job as successfully completed."""
        self.status = JobStatus.DONE
        self.result_image_url = result_url
        self.quality_score = quality_score
        self.completed_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
    
    def mark_failed(self, error_code: ErrorCode, error_message: str):
        """Mark job as failed."""
        self.status = JobStatus.FAILED
        self.error_code = error_code
        self.error_message = error_message
        self.completed_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
    
    def can_retry(self) -> bool:
        """Check if job can be retried."""
        return self.retry_count < self.max_retries
    
    def increment_retry(self):
        """Increment retry counter."""
        self.retry_count += 1
        self.updated_at = datetime.now(timezone.utc)
