"""Common image processing utilities."""
import cv2
import numpy as np
from PIL import Image, ExifTags
from typing import Tuple, Optional
from pathlib import Path


def auto_rotate_image(image: Image.Image) -> Image.Image:
    """
    Auto-rotate image based on EXIF orientation.
    
    Args:
        image: PIL Image
        
    Returns:
        Rotated PIL Image
    """
    try:
        exif = image._getexif()
        if exif is not None:
            for tag, value in exif.items():
                if tag in ExifTags.TAGS and ExifTags.TAGS[tag] == 'Orientation':
                    if value == 3:
                        image = image.rotate(180, expand=True)
                    elif value == 6:
                        image = image.rotate(270, expand=True)
                    elif value == 8:
                        image = image.rotate(90, expand=True)
                    break
    except (AttributeError, KeyError, IndexError):
        # No EXIF data or no orientation tag
        pass
    
    return image


def resize_maintain_aspect(
    image: np.ndarray,
    max_size: int
) -> np.ndarray:
    """
    Resize image to fit within max_size while maintaining aspect ratio.
    
    Args:
        image: Input image as numpy array
        max_size: Maximum dimension (width or height)
        
    Returns:
        Resized image
    """
    h, w = image.shape[:2]
    
    # Calculate scaling factor
    if max(h, w) <= max_size:
        return image
    
    scale = max_size / max(h, w)
    new_w = int(w * scale)
    new_h = int(h * scale)
    
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)


def smooth_mask(mask: np.ndarray, kernel_size: int = 5) -> np.ndarray:
    """
    Smooth binary mask using morphological operations.
    
    Args:
        mask: Binary mask (0 or 255)
        kernel_size: Size of morphological kernel
        
    Returns:
        Smoothed mask
    """
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    
    # Close small holes
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    
    # Open to remove small noise
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    
    # Slight blur for smooth edges
    mask = cv2.GaussianBlur(mask, (5, 5), 0)
    
    return mask


def remove_small_components(mask: np.ndarray, min_size: int = 1000) -> np.ndarray:
    """
    Remove small connected components from binary mask.
    
    Args:
        mask: Binary mask
        min_size: Minimum component size in pixels
        
    Returns:
        Cleaned mask
    """
    # Find connected components
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    
    # Create output mask
    output = np.zeros_like(mask)
    
    # Keep only large components (skip label 0 which is background)
    for i in range(1, num_labels):
        if stats[i, cv2.CC_STAT_AREA] >= min_size:
            output[labels == i] = 255
    
    return output


def pil_to_cv2(pil_image: Image.Image) -> np.ndarray:
    """Convert PIL Image to OpenCV format (BGR)."""
    # Convert to RGB if needed
    if pil_image.mode != 'RGB':
        pil_image = pil_image.convert('RGB')
    
    # Convert to numpy array and change RGB to BGR
    cv2_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    
    return cv2_image


def cv2_to_pil(cv2_image: np.ndarray) -> Image.Image:
    """Convert OpenCV image (BGR) to PIL Image."""
    # Convert BGR to RGB
    rgb_image = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB)
    
    return Image.fromarray(rgb_image)


def get_bounding_box(mask: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Get bounding box of mask.
    
    Args:
        mask: Binary mask
        
    Returns:
        (x, y, w, h) or None if mask is empty
    """
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return None
    
    # Get largest contour
    largest_contour = max(contours, key=cv2.contourArea)
    
    return cv2.boundingRect(largest_contour)


def calculate_angle(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """
    Calculate angle between two points in degrees.
    
    Args:
        p1: First point (x, y)
        p2: Second point (x, y)
        
    Returns:
        Angle in degrees
    """
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    
    return np.degrees(np.arctan2(dy, dx))


def distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Calculate Euclidean distance between two points."""
    return np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
