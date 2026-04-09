"""Stage 5: Quality control and validation."""
import cv2
import numpy as np
from typing import Dict, Tuple

from backend.config import settings
from backend.models.job import ErrorCode
from backend.utils.image_utils import distance


class QualityCheckError(Exception):
    """Error during quality check."""
    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.QUALITY_CHECK_FAILED):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


def check_neckline_alignment(
    garment_anchors: Dict[str, Tuple[int, int]],
    person_keypoints: Dict[str, Tuple[int, int]],
    transform_params: Dict[str, float],
    max_distance: int = 50
) -> Tuple[bool, float]:
    """
    Check if garment neckline is properly aligned with person's neck.
    
    Args:
        garment_anchors: Garment anchor points
        person_keypoints: Person keypoints
        transform_params: Applied transformation parameters
        max_distance: Maximum acceptable distance in pixels
        
    Returns:
        Tuple of (passed, distance_score)
    """
    # Get neckline positions
    garment_neck = garment_anchors.get('neckline')
    person_neck = person_keypoints.get('neck')
    
    if not garment_neck or not person_neck:
        # Can't check without both points
        return True, 1.0
    
    # Calculate transformed garment neck position
    # Apply scale, rotation, translation
    # For simplicity, use the translation params directly
    transformed_neck = (
        garment_neck[0] + transform_params['tx'],
        garment_neck[1] + transform_params['ty']
    )
    
    # Calculate distance
    dist = distance(transformed_neck, person_neck)
    
    # Score: 1.0 if perfect, 0.0 if at max_distance
    score = max(0.0, 1.0 - (dist / max_distance))
    
    passed = dist < max_distance
    
    return passed, score


def check_shoulder_angle(
    person_keypoints: Dict[str, Tuple[int, int]],
    transform_params: Dict[str, float],
    max_angle_diff: float = 15.0
) -> Tuple[bool, float]:
    """
    Check if garment rotation matches person's shoulder angle.
    
    Args:
        person_keypoints: Person keypoints
        transform_params: Applied transformation
        max_angle_diff: Maximum acceptable angle difference in degrees
        
    Returns:
        Tuple of (passed, angle_score)
    """
    # The transform already accounts for the angle difference
    # If transform_params['angle'] is large, it means there was a mismatch
    angle_diff = abs(transform_params['angle'])
    
    # Score
    score = max(0.0, 1.0 - (angle_diff / max_angle_diff))
    
    passed = angle_diff < max_angle_diff
    
    return passed, score


def check_garment_within_person(
    garment_mask: np.ndarray,
    person_mask: np.ndarray,
    max_overflow: float = 0.15
) -> Tuple[bool, float]:
    """
    Check that garment stays mostly within person silhouette.
    
    Args:
        garment_mask: Transformed garment mask
        person_mask: Person mask
        max_overflow: Maximum fraction of garment pixels outside person
        
    Returns:
        Tuple of (passed, overlap_score)
    """
    # Count garment pixels
    garment_pixels = cv2.countNonZero(garment_mask)
    
    if garment_pixels == 0:
        return False, 0.0
    
    # Count garment pixels inside person
    overlap = cv2.bitwise_and(garment_mask, person_mask)
    overlap_pixels = cv2.countNonZero(overlap)
    
    # Calculate overlap ratio
    overlap_ratio = overlap_pixels / garment_pixels
    
    # Calculate overflow ratio
    overflow_ratio = 1.0 - overlap_ratio
    
    # Score
    score = overlap_ratio
    
    passed = overflow_ratio < max_overflow
    
    return passed, score


def check_scale_reasonable(
    transform_params: Dict[str, float],
    min_scale: float = 0.5,
    max_scale: float = 2.0
) -> Tuple[bool, float]:
    """
    Check that garment scaling is reasonable.
    
    Args:
        transform_params: Applied transformation
        min_scale: Minimum acceptable scale
        max_scale: Maximum acceptable scale
        
    Returns:
        Tuple of (passed, scale_score)
    """
    scale = transform_params['scale']
    
    # Check bounds
    passed = min_scale <= scale <= max_scale
    
    # Score: 1.0 at scale=1.0, lower as it deviates
    if scale < 1.0:
        score = (scale - min_scale) / (1.0 - min_scale) if min_scale < 1.0 else scale
    else:
        score = (max_scale - scale) / (max_scale - 1.0) if max_scale > 1.0 else 1.0 / scale
    
    score = max(0.0, min(1.0, score))
    
    return passed, score


def calculate_quality_score(
    garment_anchors: Dict[str, Tuple[int, int]],
    person_keypoints: Dict[str, Tuple[int, int]],
    garment_mask: np.ndarray,
    person_mask: np.ndarray,
    transform_params: Dict[str, float]
) -> Tuple[float, Dict[str, float], bool]:
    """
    Calculate overall quality score for try-on result.
    
    Args:
        garment_anchors: Garment anchor points
        person_keypoints: Person keypoints
        garment_mask: Transformed garment mask
        person_mask: Person mask
        transform_params: Applied transformation
        
    Returns:
        Tuple of (overall_score, individual_scores, passed)
    """
    scores = {}
    checks = {}
    
    # Neckline alignment
    passed, score = check_neckline_alignment(garment_anchors, person_keypoints, transform_params)
    scores['neckline_alignment'] = score
    checks['neckline_alignment'] = passed
    
    # Shoulder angle
    passed, score = check_shoulder_angle(person_keypoints, transform_params)
    scores['shoulder_angle'] = score
    checks['shoulder_angle'] = passed
    
    # Garment within person
    passed, score = check_garment_within_person(garment_mask, person_mask)
    scores['overlap'] = score
    checks['overlap'] = passed
    
    # Scale reasonableness
    passed, score = check_scale_reasonable(transform_params)
    scores['scale'] = score
    checks['scale'] = passed
    
    # Overall score (weighted average)
    weights = {
        'neckline_alignment': 0.3,
        'shoulder_angle': 0.2,
        'overlap': 0.3,
        'scale': 0.2
    }
    
    overall_score = sum(scores[k] * weights[k] for k in weights.keys())
    
    # Overall pass/fail
    all_passed = all(checks.values())
    quality_passed = overall_score >= settings.quality_threshold and all_passed
    
    return overall_score, scores, quality_passed


def quality_control(
    garment_anchors: Dict[str, Tuple[int, int]],
    person_keypoints: Dict[str, Tuple[int, int]],
    garment_mask: np.ndarray,
    person_mask: np.ndarray,
    transform_params: Dict[str, float]
) -> Tuple[float, bool]:
    """
    Run quality control checks.
    
    Args:
        garment_anchors: Garment anchor points
        person_keypoints: Person keypoints
        garment_mask: Transformed garment mask
        person_mask: Person mask
        transform_params: Applied transformation
        
    Returns:
        Tuple of (quality_score, passed)
        
    Raises:
        QualityCheckError: If quality check fails critically
    """
    try:
        overall_score, individual_scores, passed = calculate_quality_score(
            garment_anchors,
            person_keypoints,
            garment_mask,
            person_mask,
            transform_params
        )
        
        return overall_score, passed
        
    except Exception as e:
        raise QualityCheckError(f"Quality control failed: {e}")

def evaluate_final_result(
    original_image: np.ndarray,
    final_image: np.ndarray,
    person_mask: np.ndarray,
    geometric_score: float
) -> Tuple[float, bool]:
    """
    Evaluate final generated result against original image and metrics.
    
    Args:
        original_image: The original user image
        final_image: The generated diffusion result
        person_mask: Mask of the person (to check background preservation)
        geometric_score: Score from geometric alignment phase
        
    Returns:
        Tuple of (quality_score, passed)
    """
    # 1. Correct clothing placement / geometric structure (from Stage 5)
    score = geometric_score * 0.5
    
    # 2. Visual consistency & preservation of body/background
    # Calculate difference in background (where person_mask is 0)
    bg_mask = cv2.bitwise_not(person_mask)
    
    if original_image.shape == final_image.shape:
        orig_bg = cv2.bitwise_and(original_image, original_image, mask=bg_mask)
        final_bg = cv2.bitwise_and(final_image, final_image, mask=bg_mask)
        
        # Mean absolute difference in background
        diff = cv2.absdiff(orig_bg, final_bg)
        mean_diff = np.mean(diff[bg_mask > 0]) if np.any(bg_mask > 0) else 0
        
        # Max difference of ~255. We want diff to be low.
        # Score from 0 to 1 where 0 is high diff, 1 is no diff
        bg_preservation = max(0.0, 1.0 - (mean_diff / 50.0)) 
    else:
        bg_preservation = 0.5 # fallback shape mismatch
        
    score += bg_preservation * 0.5
    
    # 3. Absence of artifacts (basic placeholder for noise detection)
    # Could measure extreme high-frequency changes, but we'll threshold overall score
    
    passed = score >= settings.quality_threshold
    return score, passed
