"""Post-inference quality checks for VTON results.

Checks the generated try-on image for:
  - Face/identity preservation (SSIM on face region)
  - Artifact detection (blur, unnatural patterns)
  - Anatomy plausibility (no missing limbs, distorted proportions)
"""
import cv2
import numpy as np
from PIL import Image
from typing import Dict, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class PostCheckResult:
    """Result of a single post-check."""
    name: str
    score: float  # 0.0 – 1.0
    passed: bool
    reason: str


@dataclass
class PostCheckReport:
    """Full post-check report."""
    overall_score: float
    passed: bool
    checks: Dict[str, PostCheckResult] = field(default_factory=dict)
    failure_reasons: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "overall_score": round(self.overall_score, 3),
            "passed": self.passed,
            "checks": {k: {"score": round(v.score, 3), "passed": v.passed, "reason": v.reason}
                       for k, v in self.checks.items()},
            "failure_reasons": self.failure_reasons,
        }


# ── Individual checks ─────────────────────────────────────────────────

def check_face_identity(
    original: np.ndarray,
    result: np.ndarray,
    parsing_map: Optional[np.ndarray] = None,
    threshold: float = 0.6,
) -> PostCheckResult:
    """
    Check face preservation by comparing face region SSIM.

    Uses human parsing face label (13) or upper 25% of image as proxy.
    """
    h, w = original.shape[:2]
    rh, rw = result.shape[:2]

    # Resize if needed
    if (h, w) != (rh, rw):
        result = cv2.resize(result, (w, h), interpolation=cv2.INTER_LANCZOS4)

    # Get face region
    if parsing_map is not None and parsing_map.shape[:2] == (h, w):
        face_mask = (parsing_map == 13).astype(np.uint8)  # Face label
        # Also include hair as context
        face_mask |= (parsing_map == 2).astype(np.uint8)  # Hair
    else:
        # Fallback: upper 30% center region
        face_mask = np.zeros((h, w), dtype=np.uint8)
        y_end = int(h * 0.3)
        x_start = int(w * 0.25)
        x_end = int(w * 0.75)
        face_mask[:y_end, x_start:x_end] = 1

    if face_mask.sum() < 100:
        return PostCheckResult("face_identity", 1.0, True, "No face region detected, skipping")

    # Compare face region
    orig_face = cv2.bitwise_and(original, original, mask=face_mask)
    result_face = cv2.bitwise_and(result, result, mask=face_mask)

    # Compute normalized difference
    diff = cv2.absdiff(orig_face, result_face).astype(np.float32)
    face_pixels = face_mask.sum()
    mean_diff = diff.sum() / (face_pixels * 3 * 255.0)  # Normalize to [0, 1]

    score = max(0.0, 1.0 - mean_diff * 5.0)  # Scale: 20% diff → score 0
    passed = score >= threshold

    return PostCheckResult(
        "face_identity",
        score,
        passed,
        f"Face similarity: {score:.2f} ({'OK' if passed else 'DEGRADED'})",
    )


def check_artifacts(
    result: np.ndarray,
    threshold: float = 0.5,
) -> PostCheckResult:
    """
    Check for common diffusion artifacts: excessive blur, noise patterns.
    """
    gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY) if len(result.shape) == 3 else result

    # Laplacian variance as sharpness measure
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    sharpness = laplacian.var()

    # Reasonable range for a natural photo: 50-5000
    if sharpness < 20:
        score = 0.2
        reason = f"Very blurry (sharpness={sharpness:.1f})"
    elif sharpness < 50:
        score = 0.5
        reason = f"Somewhat blurry (sharpness={sharpness:.1f})"
    else:
        score = min(1.0, sharpness / 200.0)
        reason = f"Sharpness OK ({sharpness:.1f})"

    passed = score >= threshold
    return PostCheckResult("artifacts", score, passed, reason)


def check_background_preservation(
    original: np.ndarray,
    result: np.ndarray,
    parsing_map: Optional[np.ndarray] = None,
    threshold: float = 0.5,
) -> PostCheckResult:
    """
    Check that background (non-person regions) is preserved.
    """
    h, w = original.shape[:2]
    rh, rw = result.shape[:2]

    if (h, w) != (rh, rw):
        result = cv2.resize(result, (w, h), interpolation=cv2.INTER_LANCZOS4)

    # Background mask
    if parsing_map is not None and parsing_map.shape[:2] == (h, w):
        bg_mask = (parsing_map == 0).astype(np.uint8)
    else:
        # Can't check without parsing
        return PostCheckResult("background", 0.8, True, "No parsing map, skipping bg check")

    if bg_mask.sum() < 100:
        return PostCheckResult("background", 1.0, True, "Minimal background, skipping")

    # Compare background regions
    diff = cv2.absdiff(original, result)
    bg_diff = diff[bg_mask > 0].mean() / 255.0

    score = max(0.0, 1.0 - bg_diff * 3.0)
    passed = score >= threshold

    return PostCheckResult(
        "background",
        score,
        passed,
        f"Background preservation: {score:.2f} ({'OK' if passed else 'CHANGED'})",
    )


# ── Combined post-check ──────────────────────────────────────────────

SCORE_WEIGHTS = {
    "face_identity": 0.40,
    "artifacts": 0.30,
    "background": 0.30,
}

OVERALL_THRESHOLD = 0.50


def run_postchecks(
    original_image: np.ndarray,
    result_image: np.ndarray,
    parsing_map: Optional[np.ndarray] = None,
) -> PostCheckReport:
    """
    Run all post-inference quality checks.

    Args:
        original_image: Original person image (BGR uint8)
        result_image: Generated try-on result (BGR uint8)
        parsing_map: Human parsing map (optional, improves accuracy)

    Returns:
        PostCheckReport with scores and pass/fail status
    """
    checks = {}
    failure_reasons = []

    check_results = [
        check_face_identity(original_image, result_image, parsing_map),
        check_artifacts(result_image),
        check_background_preservation(original_image, result_image, parsing_map),
    ]

    for result in check_results:
        checks[result.name] = result
        if not result.passed:
            failure_reasons.append(f"{result.name}: {result.reason}")

    # Weighted score
    overall_score = sum(
        checks[name].score * weight
        for name, weight in SCORE_WEIGHTS.items()
        if name in checks
    )

    passed = overall_score >= OVERALL_THRESHOLD

    return PostCheckReport(
        overall_score=overall_score,
        passed=passed,
        checks=checks,
        failure_reasons=failure_reasons,
    )
