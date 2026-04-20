"""Stage 3: Garment preparation and anchor point detection."""
import cv2
import numpy as np
from typing import Dict, Tuple, Optional

try:
    from rembg import remove as rembg_remove
    REMBG_AVAILABLE = True
except ImportError:
    REMBG_AVAILABLE = False

from backend.models.job import ErrorCode
from backend.utils.image_utils import smooth_mask, remove_small_components, get_bounding_box


class GarmentPrepError(Exception):
    """Error during garment preparation."""
    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.WARP_FAILED):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


def remove_background(image: np.ndarray, threshold: int = 240) -> Tuple[np.ndarray, np.ndarray]:
    """
    Remove background from garment image using rembg (AI-based) with
    fallback to brightness threshold for white backgrounds.
    
    Args:
        image: Input garment image (BGR)
        threshold: Brightness threshold for fallback background detection
        
    Returns:
        Tuple of (image with transparent background as RGBA, garment mask)
    """
    if REMBG_AVAILABLE:
        # Use rembg for robust background removal on any background
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        result = rembg_remove(rgb_image)  # Returns RGBA numpy array
        
        # Extract alpha channel as garment mask
        if result.shape[2] == 4:
            garment_mask = result[:, :, 3]
        else:
            # Unexpected output, fall through to threshold method
            garment_mask = None
        
        if garment_mask is not None:
            # Threshold to binary
            _, garment_mask = cv2.threshold(garment_mask, 127, 255, cv2.THRESH_BINARY)
            
            # Clean up mask
            garment_mask = smooth_mask(garment_mask, kernel_size=3)
            garment_mask = remove_small_components(garment_mask, min_size=500)
            
            # Create RGBA in BGR order (OpenCV convention)
            b, g, r = cv2.split(image)
            rgba = cv2.merge([b, g, r, garment_mask])
            
            return rgba, garment_mask
    
    # Fallback: simple brightness threshold (works only for white backgrounds)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, bg_mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    garment_mask = cv2.bitwise_not(bg_mask)
    
    # Clean up mask
    garment_mask = smooth_mask(garment_mask, kernel_size=3)
    garment_mask = remove_small_components(garment_mask, min_size=500)
    
    # Create RGBA image
    b, g, r = cv2.split(image)
    rgba = cv2.merge([b, g, r, garment_mask])
    
    return rgba, garment_mask


def detect_garment_anchor_points(
    garment_mask: np.ndarray,
    garment_type: Optional[str] = None
) -> Dict[str, Tuple[int, int]]:
    """
    Detect anchor points on garment (neckline, shoulders, hem).
    
    Args:
        garment_mask: Binary garment mask
        garment_type: Type of garment (for type-specific detection)
        
    Returns:
        Dictionary of anchor point names to coordinates
        
    Raises:
        GarmentPrepError: If anchor detection fails
    """
    bbox = get_bounding_box(garment_mask)
    
    if bbox is None:
        raise GarmentPrepError("Empty garment mask - cannot detect anchors")
    
    x, y, w, h = bbox
    
    # Find contours
    contours, _ = cv2.findContours(garment_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        raise GarmentPrepError("No garment contour found")
    
    # Get largest contour
    contour = max(contours, key=cv2.contourArea)
    
    # Detect key points based on garment geometry
    anchors = {}
    
    # Set region boundaries based on garment type
    gtype = (garment_type or "upper_body").lower()
    
    # Defaults (t-shirt, shirt, upper_body)
    shoulder_y_max_pct = 0.3
    waist_y_min_pct = 0.4
    waist_y_max_pct = 0.65
    hem_y_min_pct = 0.75
    hem_bottom_min_pct = 0.8
    neckline_y_max_pct = 0.2
    
    if gtype == "dress":
        # Dress implies a longer silhouette
        waist_y_min_pct = 0.3
        waist_y_max_pct = 0.45
        hem_y_min_pct = 0.85
        hem_bottom_min_pct = 0.9
    elif gtype in ["jacket", "coat", "outerwear"]:
        # Jackets might feature deeper neckline, lower waist/hem
        neckline_y_max_pct = 0.25
        waist_y_min_pct = 0.5
        waist_y_max_pct = 0.7
        hem_y_min_pct = 0.8
        hem_bottom_min_pct = 0.85
    
    # Top center (neckline) - highest point near center
    top_points = contour[contour[:, 0, 1] < (y + h * neckline_y_max_pct)]
    if len(top_points) > 0:
        # Find point closest to horizontal center
        center_x = x + w // 2
        top_center_idx = np.argmin(np.abs(top_points[:, 0, 0] - center_x))
        anchors['neckline'] = tuple(top_points[top_center_idx, 0])
    else:
        # Fallback
        anchors['neckline'] = (x + w // 2, y)
    
    # Left shoulder - top left corner area
    left_region = contour[
        (contour[:, 0, 0] < (x + w * 0.4)) &
        (contour[:, 0, 1] < (y + h * shoulder_y_max_pct))
    ]
    if len(left_region) > 0:
        # Leftmost point in top-left region
        left_idx = np.argmin(left_region[:, 0, 0])
        anchors['left_shoulder'] = tuple(left_region[left_idx, 0])
    else:
        anchors['left_shoulder'] = (x, y + int(h * 0.15))
    
    # Right shoulder - top right corner area
    right_region = contour[
        (contour[:, 0, 0] > (x + w * 0.6)) &
        (contour[:, 0, 1] < (y + h * shoulder_y_max_pct))
    ]
    if len(right_region) > 0:
        # Rightmost point in top-right region
        right_idx = np.argmax(right_region[:, 0, 0])
        anchors['right_shoulder'] = tuple(right_region[right_idx, 0])
    else:
        anchors['right_shoulder'] = (x + w, y + int(h * 0.15))
    
    # Bottom hem — lowest center point
    bottom_points = contour[contour[:, 0, 1] > (y + h * hem_bottom_min_pct)]
    if len(bottom_points) > 0:
        center_x = x + w // 2
        bottom_center_idx = np.argmin(np.abs(bottom_points[:, 0, 0] - center_x))
        anchors['hem_bottom'] = tuple(bottom_points[bottom_center_idx, 0])
    else:
        anchors['hem_bottom'] = (x + w // 2, y + h)
    
    # Extended anchors for TPS warping (waist and hem corners)
    
    # Left waist
    waist_region_left = contour[
        (contour[:, 0, 0] < (x + w * 0.4)) &
        (contour[:, 0, 1] > (y + h * waist_y_min_pct)) &
        (contour[:, 0, 1] < (y + h * waist_y_max_pct))
    ]
    if len(waist_region_left) > 0:
        left_idx = np.argmin(waist_region_left[:, 0, 0])
        anchors['left_waist'] = tuple(waist_region_left[left_idx, 0])
    
    # Right waist
    waist_region_right = contour[
        (contour[:, 0, 0] > (x + w * 0.6)) &
        (contour[:, 0, 1] > (y + h * waist_y_min_pct)) &
        (contour[:, 0, 1] < (y + h * waist_y_max_pct))
    ]
    if len(waist_region_right) > 0:
        right_idx = np.argmax(waist_region_right[:, 0, 0])
        anchors['right_waist'] = tuple(waist_region_right[right_idx, 0])
    
    # Left hem — bottom-left corner
    hem_region_left = contour[
        (contour[:, 0, 0] < (x + w * 0.4)) &
        (contour[:, 0, 1] > (y + h * hem_y_min_pct))
    ]
    if len(hem_region_left) > 0:
        left_idx = np.argmin(hem_region_left[:, 0, 0])
        anchors['left_hem'] = tuple(hem_region_left[left_idx, 0])
    
    # Right hem — bottom-right corner
    hem_region_right = contour[
        (contour[:, 0, 0] > (x + w * 0.6)) &
        (contour[:, 0, 1] > (y + h * hem_y_min_pct))
    ]
    if len(hem_region_right) > 0:
        right_idx = np.argmax(hem_region_right[:, 0, 0])
        anchors['right_hem'] = tuple(hem_region_right[right_idx, 0])
    
    return anchors


def prepare_garment(
    image: np.ndarray,
    garment_type: Optional[str] = None
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Tuple[int, int]]]:
    """
    Complete garment preparation pipeline.
    
    Args:
        image: Input garment image (BGR)
        garment_type: Optional garment type
        
    Returns:
        Tuple of (garment RGBA, garment mask, anchor points)
        
    Raises:
        GarmentPrepError: If preparation fails
    """
    try:
        # Remove background
        garment_rgba, garment_mask = remove_background(image)
        
        # Detect anchor points
        anchors = detect_garment_anchor_points(garment_mask, garment_type)
        
        return garment_rgba, garment_mask, anchors
        
    except GarmentPrepError:
        raise
    except Exception as e:
        raise GarmentPrepError(f"Garment preparation failed: {e}")
