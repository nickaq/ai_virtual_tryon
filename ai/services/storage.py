"""Stage 7: Result storage and artifact management."""
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Optional
import json

from backend.config import settings
from backend.models.job import ErrorCode


class StorageError(Exception):
    """Error during storage operations."""
    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.STORAGE_ERROR):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


def save_image(image: np.ndarray, file_path: Path) -> str:
    """
    Save image to file.
    
    Args:
        image: Image as numpy array (BGR)
        file_path: Output file path
        
    Returns:
        File path as string
        
    Raises:
        StorageError: If save fails
    """
    try:
        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save image
        success = cv2.imwrite(str(file_path), image)
        
        if not success:
            raise StorageError(f"Failed to write image to {file_path}")
        
        return str(file_path)
        
    except Exception as e:
        raise StorageError(f"Failed to save image: {e}")


def save_result(job_id: str, result_image: np.ndarray) -> str:
    """
    Save final result image.
    
    Args:
        job_id: Job identifier
        result_image: Result image (BGR)
        
    Returns:
        URL/path to result image
        
    Raises:
        StorageError: If save fails
    """
    file_path = settings.results_path / f"{job_id}.png"
    save_image(result_image, file_path)
    
    # Return URL (in real deployment, this would be a public URL)
    # For now, return relative path
    return f"/results/{job_id}.png"


def save_debug_artifacts(
    job_id: str,
    person_mask: Optional[np.ndarray] = None,
    torso_mask: Optional[np.ndarray] = None,
    garment_mask: Optional[np.ndarray] = None,
    draft_composite: Optional[np.ndarray] = None,
    keypoints: Optional[Dict] = None
) -> Dict[str, str]:
    """
    Save debug artifacts for analysis.
    
    Args:
        job_id: Job identifier
        person_mask: Person segmentation mask
        torso_mask: Torso mask
        garment_mask: Garment mask
        draft_composite: Draft composite image
        keypoints: Detected keypoints
        
    Returns:
        Dictionary of artifact names to URLs
        
    Raises:
        StorageError: If save fails
    """
    if not settings.save_debug_artifacts:
        return {}
    
    artifacts = {}
    artifact_dir = settings.artifacts_path / job_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Save masks
        if person_mask is not None:
            path = artifact_dir / "person_mask.png"
            save_image(person_mask, path)
            artifacts['person_mask'] = f"/artifacts/{job_id}/person_mask.png"
        
        if torso_mask is not None:
            path = artifact_dir / "torso_mask.png"
            save_image(torso_mask, path)
            artifacts['torso_mask'] = f"/artifacts/{job_id}/torso_mask.png"
        
        if garment_mask is not None:
            path = artifact_dir / "garment_mask.png"
            save_image(garment_mask, path)
            artifacts['garment_mask'] = f"/artifacts/{job_id}/garment_mask.png"
        
        # Save draft composite
        if draft_composite is not None:
            path = artifact_dir / "draft_composite.png"
            save_image(draft_composite, path)
            artifacts['draft_composite'] = f"/artifacts/{job_id}/draft_composite.png"
        
        # Save keypoints as JSON
        if keypoints is not None:
            path = artifact_dir / "keypoints.json"
            # Convert tuples to lists for JSON serialization
            serializable_kp = {k: list(v) for k, v in keypoints.items()}
            path.write_text(json.dumps(serializable_kp, indent=2))
            artifacts['keypoints'] = f"/artifacts/{job_id}/keypoints.json"
        
        return artifacts
        
    except Exception as e:
        # Don't fail the job if debug artifacts fail
        print(f"Warning: Failed to save debug artifacts: {e}")
        return {}


def get_result_path(job_id: str) -> Optional[Path]:
    """
    Get path to result image if it exists.
    
    Args:
        job_id: Job identifier
        
    Returns:
        Path to result or None
    """
    result_path = settings.results_path / f"{job_id}.png"
    
    if result_path.exists():
        return result_path
    
    return None
