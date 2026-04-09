"""Stage 4: Garment alignment and warping onto person."""
import cv2
import numpy as np
from typing import Dict, Tuple

from backend.models.job import ErrorCode
from backend.utils.image_utils import calculate_angle, distance


class AlignmentError(Exception):
    """Error during alignment and warping."""
    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.WARP_FAILED):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


def calculate_transform_params(
    garment_anchors: Dict[str, Tuple[int, int]],
    person_keypoints: Dict[str, Tuple[int, int]]
) -> Dict[str, float]:
    """
    Calculate transformation parameters to align garment with person.
    
    Args:
        garment_anchors: Garment anchor points
        person_keypoints: Person keypoints
        
    Returns:
        Dictionary with scale, angle, translation
    """
    # Calculate shoulder width
    garment_shoulder_width = distance(
        garment_anchors['left_shoulder'],
        garment_anchors['right_shoulder']
    )
    
    person_shoulder_width = distance(
        person_keypoints['left_shoulder'],
        person_keypoints['right_shoulder']
    )
    
    # Scale factor
    scale = person_shoulder_width / garment_shoulder_width if garment_shoulder_width > 0 else 1.0
    
    # Calculate rotation angle (based on shoulder line)
    garment_angle = calculate_angle(
        garment_anchors['left_shoulder'],
        garment_anchors['right_shoulder']
    )
    
    person_angle = calculate_angle(
        person_keypoints['left_shoulder'],
        person_keypoints['right_shoulder']
    )
    
    rotation_angle = person_angle - garment_angle
    
    # Translation (align necklines)
    garment_neck = garment_anchors.get('neckline', garment_anchors['left_shoulder'])
    person_neck = person_keypoints.get('neck', person_keypoints['left_shoulder'])
    
    tx = person_neck[0] - garment_neck[0]
    ty = person_neck[1] - garment_neck[1]
    
    return {
        'scale': scale,
        'angle': rotation_angle,
        'tx': tx,
        'ty': ty,
        'center': garment_neck
    }


def apply_affine_transform(
    garment_image: np.ndarray,
    garment_mask: np.ndarray,
    transform_params: Dict[str, float],
    output_shape: Tuple[int, int]
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Apply affine transformation to garment.
    
    Args:
        garment_image: Garment image (RGBA or BGR)
        garment_mask: Garment binary mask
        transform_params: Transformation parameters
        output_shape: Output image shape (h, w)
        
    Returns:
        Tuple of (transformed image, transformed mask)
    """
    h, w = output_shape
    center = transform_params['center']
    
    # Build transformation matrix
    # 1. Rotate and scale around center
    M = cv2.getRotationMatrix2D(
        center,
        transform_params['angle'],
        transform_params['scale']
    )
    
    # 2. Add translation
    M[0, 2] += transform_params['tx']
    M[1, 2] += transform_params['ty']
    
    # Apply to image
    if garment_image.shape[2] == 4:
        # Handle RGBA separately
        transformed = cv2.warpAffine(
            garment_image,
            M,
            (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0, 0)
        )
    else:
        transformed = cv2.warpAffine(
            garment_image,
            M,
            (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0)
        )
    
    # Apply to mask
    transformed_mask = cv2.warpAffine(
        garment_mask,
        M,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0
    )
    
    # Threshold mask to binary
    _, transformed_mask = cv2.threshold(transformed_mask, 127, 255, cv2.THRESH_BINARY)
    
    return transformed, transformed_mask


def composite_garment_on_person(
    person_image: np.ndarray,
    garment_image: np.ndarray,
    garment_mask: np.ndarray,
    torso_mask: np.ndarray,
    arms_mask: np.ndarray
) -> np.ndarray:
    """
    Composite garment onto person, handling occlusions.
    
    Args:
        person_image: Original person image (BGR)
        garment_image: Transformed garment (BGR or RGBA)
        garment_mask: Transformed garment mask
        torso_mask: Person torso mask
        arms_mask: Person arms mask
        
    Returns:
        Composited image
    """
    result = person_image.copy()
    
    # Convert garment to BGR if RGBA
    if garment_image.shape[2] == 4:
        garment_bgr = garment_image[:, :, :3]
        garment_alpha = garment_image[:, :, 3]
    else:
        garment_bgr = garment_image
        garment_alpha = garment_mask
    
    # Create composite mask
    # Garment should be visible on torso, but occluded by arms
    composite_mask = cv2.bitwise_and(garment_mask, torso_mask)
    composite_mask = cv2.bitwise_and(composite_mask, cv2.bitwise_not(arms_mask))
    
    # Blend garment using mask
    # Normalize mask to 0-1 range
    alpha = composite_mask.astype(float) / 255.0
    alpha = np.expand_dims(alpha, axis=2)
    
    # Also use garment alpha if available
    if garment_image.shape[2] == 4:
        garment_alpha_norm = garment_alpha.astype(float) / 255.0
        garment_alpha_norm = np.expand_dims(garment_alpha_norm, axis=2)
        alpha = alpha * garment_alpha_norm
    
    # Blend
    result = (garment_bgr * alpha + result * (1 - alpha)).astype(np.uint8)
    
    return result


def align_and_composite(
    person_image: np.ndarray,
    person_keypoints: Dict[str, Tuple[int, int]],
    garment_image: np.ndarray,
    garment_mask: np.ndarray,
    garment_anchors: Dict[str, Tuple[int, int]],
    torso_mask: np.ndarray,
    arms_mask: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, Dict[str, float]]:
    """
    Complete alignment and compositing pipeline.
    
    Args:
        person_image: Person image (BGR)
        person_keypoints: Person keypoints
        garment_image: Garment image (RGBA or BGR)
        garment_mask: Garment mask
        garment_anchors: Garment anchor points
        torso_mask: Person torso mask
        arms_mask: Person arms mask
        
    Returns:
        Tuple of (draft composite, transformed garment mask, transform params)
        
    Raises:
        AlignmentError: If alignment fails
    """
    try:
        h, w = person_image.shape[:2]
        
        # Calculate transformation
        transform_params = calculate_transform_params(garment_anchors, person_keypoints)
        
        # Apply transformation
        transformed_garment, transformed_mask = apply_affine_transform(
            garment_image,
            garment_mask,
            transform_params,
            (h, w)
        )
        
        # Composite
        draft_composite = composite_garment_on_person(
            person_image,
            transformed_garment,
            transformed_mask,
            torso_mask,
            arms_mask
        )
        
        return draft_composite, transformed_mask, transform_params
        
    except Exception as e:
        raise AlignmentError(f"Alignment failed: {e}")
