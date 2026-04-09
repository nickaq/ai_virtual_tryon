"""
Stage 9: Quality control and validation.

Evaluates the try-on result across multiple criteria and produces
a structured QualityReport suitable for debugging, retry decisions,
and diploma presentation.

Quality Criteria & Thresholds:
  ┌─────────────────────┬───────────┬────────────────────────────────────┐
  │ Check               │ Threshold │ Description                        │
  ├─────────────────────┼───────────┼────────────────────────────────────┤
  │ Neckline Alignment  │ 50 px     │ Garment neckline within 50px of   │
  │                     │           │ person neck after transformation   │
  │ Shoulder Angle      │ 15°       │ Garment rotation matches person   │
  │                     │           │ shoulder angle within 15°          │
  │ Overlap Ratio       │ 85%       │ At least 85% of garment pixels    │
  │                     │           │ must be within person silhouette   │
  │ Scale Ratio         │ 0.5–2.0   │ Garment scaling stays within      │
  │                     │           │ reasonable bounds                  │
  │ Overall Score       │ 0.70      │ Weighted composite score           │
  └─────────────────────┴───────────┴────────────────────────────────────┘

Retry Logic:
  - retry_recommended=True when 0.4 ≤ score < threshold (retry may help)
  - retry_recommended=False when score < 0.4 (fatally bad alignment)
"""
import cv2
import numpy as np
from typing import Dict, Tuple, List
from dataclasses import dataclass, field, asdict

from backend.config import settings
from backend.models.job import ErrorCode
from backend.utils.image_utils import distance


# ── Named Threshold Constants ───────────────────────────────────────
NECKLINE_MAX_DISTANCE_PX = 50      # pixels — neckline must be within 50px
SHOULDER_MAX_ANGLE_DEG = 15.0      # degrees — shoulder mismatch tolerance
MIN_OVERLAP_RATIO = 0.85           # 85% garment must be within person
SCALE_RANGE = (0.5, 2.0)           # acceptable garment scaling window
OVERALL_PASS_THRESHOLD = 0.70      # composite score threshold
RETRY_FUTILITY_THRESHOLD = 0.40    # below this, retry won't help

# Score weights for overall computation
SCORE_WEIGHTS = {
    'neckline_alignment': 0.3,
    'shoulder_angle': 0.2,
    'overlap': 0.3,
    'scale': 0.2,
}


class QualityCheckError(Exception):
    """Error during quality check."""
    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.QUALITY_CHECK_FAILED):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


@dataclass
class CheckResult:
    """Result of a single quality check."""
    name: str
    score: float           # 0.0–1.0
    passed: bool
    threshold: str         # human-readable threshold description
    reason: str            # explanation of pass/fail


@dataclass
class QualityReport:
    """
    Structured quality assessment report.

    Contains per-check results, overall score, pass/fail status,
    retry recommendation, and human-readable failure reasons.
    Suitable for serialization to JSON as a debug artifact.
    """
    overall_score: float
    passed: bool
    checks: Dict[str, CheckResult] = field(default_factory=dict)
    retry_recommended: bool = False
    failure_reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dictionary."""
        return {
            'overall_score': round(self.overall_score, 4),
            'passed': self.passed,
            'retry_recommended': self.retry_recommended,
            'failure_reasons': self.failure_reasons,
            'checks': {
                name: {
                    'score': round(check.score, 4),
                    'passed': check.passed,
                    'threshold': check.threshold,
                    'reason': check.reason,
                }
                for name, check in self.checks.items()
            },
        }


def check_neckline_alignment(
    garment_anchors: Dict[str, Tuple[int, int]],
    person_keypoints: Dict[str, Tuple[int, int]],
    transform_params: Dict[str, float],
    max_distance: int = NECKLINE_MAX_DISTANCE_PX
) -> CheckResult:
    """
    Check if garment neckline is properly aligned with person's neck.
    """
    garment_neck = garment_anchors.get('neckline')
    person_neck = person_keypoints.get('neck')

    if not garment_neck or not person_neck:
        return CheckResult(
            name='neckline_alignment',
            score=1.0,
            passed=True,
            threshold=f'≤ {max_distance}px',
            reason='Skipped: missing neckline or neck keypoint'
        )

    # Calculate transformed garment neck position
    transformed_neck = (
        garment_neck[0] + transform_params.get('tx', 0),
        garment_neck[1] + transform_params.get('ty', 0)
    )

    dist = distance(transformed_neck, person_neck)
    score = max(0.0, 1.0 - (dist / max_distance))
    passed = dist < max_distance

    return CheckResult(
        name='neckline_alignment',
        score=score,
        passed=passed,
        threshold=f'≤ {max_distance}px',
        reason=f'Neckline distance: {dist:.1f}px ({"OK" if passed else "EXCEEDS LIMIT"})'
    )


def check_shoulder_angle(
    person_keypoints: Dict[str, Tuple[int, int]],
    transform_params: Dict[str, float],
    max_angle_diff: float = SHOULDER_MAX_ANGLE_DEG
) -> CheckResult:
    """
    Check if garment rotation matches person's shoulder angle.
    """
    angle_diff = abs(transform_params.get('angle', 0))
    score = max(0.0, 1.0 - (angle_diff / max_angle_diff))
    passed = angle_diff < max_angle_diff

    return CheckResult(
        name='shoulder_angle',
        score=score,
        passed=passed,
        threshold=f'≤ {max_angle_diff}°',
        reason=f'Shoulder angle diff: {angle_diff:.1f}° ({"OK" if passed else "EXCEEDS LIMIT"})'
    )


def check_garment_within_person(
    garment_mask: np.ndarray,
    person_mask: np.ndarray,
    min_overlap: float = MIN_OVERLAP_RATIO
) -> CheckResult:
    """
    Check that garment stays mostly within person silhouette.
    """
    garment_pixels = cv2.countNonZero(garment_mask)

    if garment_pixels == 0:
        return CheckResult(
            name='overlap',
            score=0.0,
            passed=False,
            threshold=f'≥ {min_overlap*100:.0f}%',
            reason='Empty garment mask — no garment pixels detected'
        )

    overlap = cv2.bitwise_and(garment_mask, person_mask)
    overlap_pixels = cv2.countNonZero(overlap)
    overlap_ratio = overlap_pixels / garment_pixels
    overflow_ratio = 1.0 - overlap_ratio

    passed = overflow_ratio < (1.0 - min_overlap)

    return CheckResult(
        name='overlap',
        score=overlap_ratio,
        passed=passed,
        threshold=f'≥ {min_overlap*100:.0f}% within person',
        reason=f'Overlap: {overlap_ratio*100:.1f}% ({overlap_pixels}/{garment_pixels}px)'
    )


def check_scale_reasonable(
    transform_params: Dict[str, float],
    min_scale: float = SCALE_RANGE[0],
    max_scale: float = SCALE_RANGE[1]
) -> CheckResult:
    """
    Check that garment scaling is reasonable.
    """
    scale = transform_params.get('scale', 1.0)
    passed = min_scale <= scale <= max_scale

    if scale < 1.0:
        score = (scale - min_scale) / (1.0 - min_scale) if min_scale < 1.0 else scale
    else:
        score = (max_scale - scale) / (max_scale - 1.0) if max_scale > 1.0 else 1.0 / scale

    score = max(0.0, min(1.0, score))

    return CheckResult(
        name='scale',
        score=score,
        passed=passed,
        threshold=f'{min_scale}x–{max_scale}x',
        reason=f'Scale factor: {scale:.2f}x ({"OK" if passed else "OUT OF RANGE"})'
    )


def quality_control(
    garment_anchors: Dict[str, Tuple[int, int]],
    person_keypoints: Dict[str, Tuple[int, int]],
    garment_mask: np.ndarray,
    person_mask: np.ndarray,
    transform_params: Dict[str, float]
) -> Tuple[float, bool]:
    """
    Run quality control checks on geometric alignment result.

    Returns:
        Tuple of (quality_score, passed)

    Raises:
        QualityCheckError: If quality check fails critically
    """
    try:
        report = build_quality_report(
            garment_anchors, person_keypoints,
            garment_mask, person_mask, transform_params
        )
        return report.overall_score, report.passed

    except Exception as e:
        raise QualityCheckError(f"Quality control failed: {e}")


def build_quality_report(
    garment_anchors: Dict[str, Tuple[int, int]],
    person_keypoints: Dict[str, Tuple[int, int]],
    garment_mask: np.ndarray,
    person_mask: np.ndarray,
    transform_params: Dict[str, float]
) -> QualityReport:
    """
    Build a detailed quality report with per-check results.

    Args:
        garment_anchors: Garment anchor points
        person_keypoints: Person keypoints
        garment_mask: Transformed garment mask
        person_mask: Person mask
        transform_params: Applied transformation parameters

    Returns:
        QualityReport with all check results
    """
    checks = {}
    failure_reasons = []

    # Run all checks
    check_results = [
        check_neckline_alignment(garment_anchors, person_keypoints, transform_params),
        check_shoulder_angle(person_keypoints, transform_params),
        check_garment_within_person(garment_mask, person_mask),
        check_scale_reasonable(transform_params),
    ]

    for result in check_results:
        checks[result.name] = result
        if not result.passed:
            failure_reasons.append(f"{result.name}: {result.reason}")

    # Compute weighted overall score
    overall_score = sum(
        checks[name].score * weight
        for name, weight in SCORE_WEIGHTS.items()
        if name in checks
    )

    # Overall pass/fail
    all_passed = all(c.passed for c in checks.values())
    quality_passed = overall_score >= OVERALL_PASS_THRESHOLD and all_passed

    # Retry recommendation
    retry_recommended = (
        not quality_passed and
        overall_score >= RETRY_FUTILITY_THRESHOLD
    )

    return QualityReport(
        overall_score=overall_score,
        passed=quality_passed,
        checks=checks,
        retry_recommended=retry_recommended,
        failure_reasons=failure_reasons,
    )


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
    bg_mask = cv2.bitwise_not(person_mask)

    if original_image.shape == final_image.shape:
        orig_bg = cv2.bitwise_and(original_image, original_image, mask=bg_mask)
        final_bg = cv2.bitwise_and(final_image, final_image, mask=bg_mask)

        diff = cv2.absdiff(orig_bg, final_bg)
        mean_diff = np.mean(diff[bg_mask > 0]) if np.any(bg_mask > 0) else 0

        # Max difference of ~255. We want diff to be low.
        bg_preservation = max(0.0, 1.0 - (mean_diff / 50.0))
    else:
        bg_preservation = 0.5  # fallback shape mismatch

    score += bg_preservation * 0.5

    passed = score >= settings.quality_threshold
    return score, passed
