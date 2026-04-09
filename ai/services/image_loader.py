"""Stage 0: Image loading and normalization."""
import httpx
import cv2
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Tuple, Optional

from backend.config import settings
from backend.models.job import ErrorCode
from backend.utils.image_utils import auto_rotate_image, resize_maintain_aspect, pil_to_cv2
from backend.utils.validation import validate_image_format, validate_image_size


class ImageLoadError(Exception):
    """Error during image loading."""
    def __init__(self, message: str, error_code: ErrorCode):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


async def download_image(url: str, timeout: int = 30) -> bytes:
    """
    Download image from URL.
    
    Args:
        url: Image URL
        timeout: Request timeout in seconds
        
    Returns:
        Image bytes
        
    Raises:
        ImageLoadError: If download fails
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=timeout)
            response.raise_for_status()
            return response.content
    except httpx.TimeoutException:
        raise ImageLoadError("Image download timed out", ErrorCode.TIMEOUT)
    except httpx.HTTPError as e:
        raise ImageLoadError(f"Failed to download image: {e}", ErrorCode.STORAGE_ERROR)


def load_image_from_path(image_path: str) -> Image.Image:
    """
    Load image from file path.
    
    Args:
        image_path: Path to image file
        
    Returns:
        PIL Image
        
    Raises:
        ImageLoadError: If loading fails
    """
    path = Path(image_path)
    
    if not path.exists():
        raise ImageLoadError(f"Image not found: {image_path}", ErrorCode.STORAGE_ERROR)
    
    if not validate_image_format(path):
        raise ImageLoadError(
            f"Invalid image format. Allowed: {', '.join(['.jpg', '.png'])}",
            ErrorCode.INVALID_IMAGE_FORMAT
        )
    
    if not validate_image_size(path, settings.max_image_size_mb):
        raise ImageLoadError(
            f"Image too large. Maximum: {settings.max_image_size_mb}MB",
            ErrorCode.IMAGE_TOO_LARGE
        )
    
    try:
        image = Image.open(path)
        return image
    except Exception as e:
        raise ImageLoadError(f"Failed to load image: {e}", ErrorCode.INVALID_IMAGE_FORMAT)


async def load_image_from_url(url: str) -> Image.Image:
    """
    Load image from URL.
    
    Args:
        url: Image URL
        
    Returns:
        PIL Image
        
    Raises:
        ImageLoadError: If loading fails
    """
    try:
        image_bytes = await download_image(url)
        
        # Check size
        size_mb = len(image_bytes) / (1024 * 1024)
        if size_mb > settings.max_image_size_mb:
            raise ImageLoadError(
                f"Image too large. Maximum: {settings.max_image_size_mb}MB",
                ErrorCode.IMAGE_TOO_LARGE
            )
        
        # Load image
        from io import BytesIO
        image = Image.open(BytesIO(image_bytes))
        
        return image
        
    except ImageLoadError:
        raise
    except Exception as e:
        raise ImageLoadError(f"Failed to load image: {e}", ErrorCode.INVALID_IMAGE_FORMAT)


def normalize_image(image: Image.Image) -> np.ndarray:
    """
    Normalize image: auto-rotate, resize, convert to RGB, return as OpenCV array.
    
    Args:
        image: PIL Image
        
    Returns:
        Normalized image as numpy array (BGR format)
    """
    # Auto-rotate based on EXIF
    image = auto_rotate_image(image)
    
    # Convert to RGB
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Convert to OpenCV format
    cv2_image = pil_to_cv2(image)
    
    # Resize to working size
    cv2_image = resize_maintain_aspect(cv2_image, settings.work_image_size)
    
    return cv2_image


async def load_and_normalize(
    image_url: Optional[str] = None,
    image_path: Optional[str] = None
) -> Tuple[np.ndarray, Image.Image]:
    """
    Load and normalize image from URL or path.
    
    Args:
        image_url: Optional image URL
        image_path: Optional image path
        
    Returns:
        Tuple of (normalized OpenCV image, original PIL image)
        
    Raises:
        ImageLoadError: If loading or normalization fails
    """
    # Load image
    if image_url:
        pil_image = await load_image_from_url(image_url)
    elif image_path:
        pil_image = load_image_from_path(image_path)
    else:
        raise ImageLoadError("No image URL or path provided", ErrorCode.STORAGE_ERROR)
    
    # Normalize
    normalized = normalize_image(pil_image)
    
    return normalized, pil_image
