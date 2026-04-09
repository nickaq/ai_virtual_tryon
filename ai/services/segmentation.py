"""Stage 1: Person segmentation and silhouette extraction."""
import cv2
import numpy as np
from typing import Dict, Tuple

# Try to import rembg, but provide fallback if not available (Python 3.8 compatibility)
try:
    from rembg import remove
    REMBG_AVAILABLE = True
except ImportError:
    REMBG_AVAILABLE = False
    def remove(image, **kwargs):
        """Fallback: simple background removal using GrabCut."""
        mask = np.zeros(image.shape[:2], np.uint8)
        bgdModel = np.zeros((1, 65), np.float64)
        fgdModel = np.zeros((1, 65), np.float64)
        h, w = image.shape[:2]
        rect = (10, 10, w - 20, h - 20)
        cv2.grabCut(image, mask, rect, bgdModel, fgdModel, 5, cv2.GC_INIT_WITH_RECT)
        mask2 = np.where((mask == 2) | (mask == 0), 0, 255).astype('uint8')
        # Return RGBA with alpha from mask
        result = np.dstack([image, mask2])
        return result

from backend.models.job import ErrorCode
from backend.utils.image_utils import smooth_mask, remove_small_components


class SegmentationError(Exception):
    """Error during segmentation."""
    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.SEGMENTATION_FAILED):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


def extract_person_mask(image: np.ndarray) -> np.ndarray:
    """
    Extract person segmentation mask using rembg.
    
    Args:
        image: Input image (BGR format)
        
    Returns:
        Binary mask (0 or 255)
        
    Raises:
        SegmentationError: If segmentation fails
    """
    try:
        # Convert to RGB for rembg
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Remove background - returns RGBA
        result = remove(rgb_image, alpha_matting=True, alpha_matting_erode_size=10)
        
        # Extract alpha channel as mask
        if result.shape[2] == 4:
            mask = result[:, :, 3]
        else:
            raise SegmentationError("Failed to extract alpha channel")
        
        # Threshold to binary
        _, binary_mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
        
        # Clean up mask
        binary_mask = smooth_mask(binary_mask, kernel_size=5)
        binary_mask = remove_small_components(binary_mask, min_size=1000)
        
        if cv2.countNonZero(binary_mask) == 0:
            raise SegmentationError("Empty person mask - no person detected")
        
        return binary_mask
        
    except SegmentationError:
        raise
    except Exception as e:
        raise SegmentationError(f"Person segmentation failed: {e}")


def extract_torso_mask(person_mask: np.ndarray, keypoints: Dict) -> np.ndarray:
    """
    Extract torso region from person mask using keypoints.
    
    Args:
        person_mask: Full person mask
        keypoints: Dictionary of detected keypoints
        
    Returns:
        Torso mask
    """
    h, w = person_mask.shape
    torso_mask = np.zeros((h, w), dtype=np.uint8)
    
    try:
        # Get torso keypoints
        neck = keypoints.get('neck')
        left_shoulder = keypoints.get('left_shoulder')
        right_shoulder = keypoints.get('right_shoulder')
        left_hip = keypoints.get('left_hip')
        right_hip = keypoints.get('right_hip')
        
        # If we have all required points, create polygon
        if all([neck, left_shoulder, right_shoulder, left_hip, right_hip]):
            points = np.array([
                left_shoulder,
                right_shoulder,
                right_hip,
                left_hip
            ], dtype=np.int32)
            
            cv2.fillPoly(torso_mask, [points], 255)
            
            # Intersect with person mask
            torso_mask = cv2.bitwise_and(torso_mask, person_mask)
        else:
            # Fallback: use upper 70% of person mask
            # Find bounding box of person
            contours, _ = cv2.findContours(person_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                x, y, box_w, box_h = cv2.boundingRect(max(contours, key=cv2.contourArea))
                
                # Take upper 70%
                torso_h = int(box_h * 0.7)
                torso_mask[y:y+torso_h, x:x+box_w] = person_mask[y:y+torso_h, x:x+box_w]
    
    except Exception:
        # Ultimate fallback: return full person mask
        return person_mask
    
    return torso_mask


def extract_arms_mask(
    person_mask: np.ndarray,
    torso_mask: np.ndarray,
    keypoints: Dict
) -> np.ndarray:
    """
    Extract arms region from person mask.
    
    Args:
        person_mask: Full person mask
        torso_mask: Torso mask
        keypoints: Dictionary of detected keypoints
        
    Returns:
        Arms mask
    """
    try:
        # Simple approach: arms = person - torso (in upper body region)
        arms_mask = cv2.bitwise_and(
            person_mask,
            cv2.bitwise_not(torso_mask)
        )
        
        # Only keep upper half (arms, not legs)
        h = person_mask.shape[0]
        arms_mask[h//2:, :] = 0
        
        return arms_mask
        
    except Exception:
        # If fails, return empty mask
        return np.zeros_like(person_mask)


def segment_person(
    image: np.ndarray,
    keypoints: Dict
) -> Dict[str, np.ndarray]:
    """
    Complete person segmentation pipeline.
    
    Args:
        image: Input image (BGR)
        keypoints: Detected keypoints
        
    Returns:
        Dictionary with 'person', 'torso', 'arms' masks
        
    Raises:
        SegmentationError: If segmentation fails
    """
    # Extract person mask
    person_mask = extract_person_mask(image)
    
    # Extract torso and arms
    torso_mask = extract_torso_mask(person_mask, keypoints)
    arms_mask = extract_arms_mask(person_mask, torso_mask, keypoints)
    
    return {
        'person': person_mask,
        'torso': torso_mask,
        'arms': arms_mask
    }
