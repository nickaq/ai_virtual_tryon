"""Input validation utilities."""
from pathlib import Path
from typing import Optional
from PIL import Image


ALLOWED_FORMATS = {'.jpg', '.jpeg', '.png'}
ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png'}


def validate_image_format(file_path: Path) -> bool:
    """
    Validate that file is a supported image format.
    
    Args:
        file_path: Path to image file
        
    Returns:
        True if format is valid
    """
    suffix = file_path.suffix.lower()
    return suffix in ALLOWED_FORMATS


def validate_image_size(file_path: Path, max_size_mb: int) -> bool:
    """
    Validate that image file size is within limits.
    
    Args:
        file_path: Path to image file
        max_size_mb: Maximum size in megabytes
        
    Returns:
        True if size is valid
    """
    size_mb = file_path.stat().st_size / (1024 * 1024)
    return size_mb <= max_size_mb


def validate_image_dimensions(image: Image.Image, max_dimension: int) -> bool:
    """
    Validate that image dimensions are within limits.
    
    Args:
        image: PIL Image
        max_dimension: Maximum width or height
        
    Returns:
        True if dimensions are valid
    """
    w, h = image.size
    return max(w, h) <= max_dimension


def validate_url(url: Optional[str]) -> bool:
    """
    Validate URL format.
    
    Args:
        url: URL string
        
    Returns:
        True if URL is valid
    """
    if not url:
        return False
    
    return url.startswith(('http://', 'https://'))
