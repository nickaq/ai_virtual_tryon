"""Input quality gates — run BEFORE heavy preprocessing.

Goal: fail fast on garbage-in so we don't spend GPU time on hopeless jobs,
and return a structured reason so the failure-logger can bucket cases for
future retraining / hard-negative mining.

Checks (all dependency-free, OpenCV + NumPy only):
  1. Minimum resolution
  2. Blur / motion blur (Laplacian variance)
  3. Face presence (Haar cascade)
  4. Body framing (person mask area + head/feet cut-off heuristic)

Each check returns a `PreflightFinding`; `run_preflight` aggregates them.
"""
from __future__ import annotations

import os
import cv2
import numpy as np
from PIL import Image
from dataclasses import dataclass, field
from typing import List, Optional

from backend.models.job import ErrorCode


# ── Thresholds (overridable via env) ──────────────────────────────────
MIN_DIMENSION = int(os.environ.get("PREFLIGHT_MIN_DIM", "384"))
BLUR_MIN_LAPLACIAN_VAR = float(os.environ.get("PREFLIGHT_BLUR_MIN", "40.0"))
MIN_FACE_REL_AREA = float(os.environ.get("PREFLIGHT_MIN_FACE_AREA", "0.003"))
# Minimum fraction of the image covered by a "person-like" foreground
MIN_PERSON_REL_AREA = float(os.environ.get("PREFLIGHT_MIN_PERSON_AREA", "0.10"))
# Fraction of top/bottom rows where the person mask should NOT be touching the border
BORDER_CUTOFF_FRAC = float(os.environ.get("PREFLIGHT_BORDER_CUTOFF_FRAC", "0.35"))


@dataclass
class PreflightFinding:
    name: str
    passed: bool
    score: float  # 0..1
    reason: str
    details: dict = field(default_factory=dict)


@dataclass
class PreflightReport:
    passed: bool
    findings: List[PreflightFinding] = field(default_factory=list)
    error_code: Optional[ErrorCode] = None
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "error_code": self.error_code.value if self.error_code else None,
            "summary": self.summary,
            "findings": [
                {
                    "name": f.name,
                    "passed": f.passed,
                    "score": round(f.score, 3),
                    "reason": f.reason,
                    "details": f.details,
                }
                for f in self.findings
            ],
        }


# ── Individual gates ──────────────────────────────────────────────────

def check_resolution(img_bgr: np.ndarray) -> PreflightFinding:
    h, w = img_bgr.shape[:2]
    short = min(h, w)
    passed = short >= MIN_DIMENSION
    return PreflightFinding(
        name="resolution",
        passed=passed,
        score=min(1.0, short / max(MIN_DIMENSION * 2, 1)),
        reason=f"short_side={short}px (min={MIN_DIMENSION})",
        details={"height": h, "width": w},
    )


def check_blur(img_bgr: np.ndarray) -> PreflightFinding:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    # Downscale to a canonical size so the threshold is resolution-independent.
    short = min(gray.shape)
    if short > 512:
        scale = 512.0 / short
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    passed = var >= BLUR_MIN_LAPLACIAN_VAR
    return PreflightFinding(
        name="blur",
        passed=passed,
        score=min(1.0, var / (BLUR_MIN_LAPLACIAN_VAR * 4)),
        reason=f"laplacian_var={var:.1f} (min={BLUR_MIN_LAPLACIAN_VAR:.1f})",
        details={"laplacian_var": var},
    )


_face_cascade = None


def _load_face_cascade():
    global _face_cascade
    if _face_cascade is not None:
        return _face_cascade
    path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
    _face_cascade = cv2.CascadeClassifier(path)
    return _face_cascade


def check_face(img_bgr: np.ndarray) -> PreflightFinding:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    cascade = _load_face_cascade()
    if cascade.empty():
        # Environment doesn't ship haar data — treat as soft-pass, don't block.
        return PreflightFinding(
            name="face",
            passed=True,
            score=0.5,
            reason="face detector unavailable, skipping",
        )

    h, w = gray.shape[:2]
    min_size = max(24, int(min(h, w) * 0.05))
    faces = cascade.detectMultiScale(
        gray, scaleFactor=1.15, minNeighbors=5, minSize=(min_size, min_size)
    )
    if len(faces) == 0:
        return PreflightFinding(
            name="face",
            passed=False,
            score=0.0,
            reason="no face detected",
            details={"count": 0},
        )
    # Pick the largest face and measure its relative area.
    (_, _, fw, fh) = max(faces, key=lambda r: r[2] * r[3])
    rel = (fw * fh) / float(h * w)
    passed = rel >= MIN_FACE_REL_AREA
    return PreflightFinding(
        name="face",
        passed=passed,
        score=min(1.0, rel / (MIN_FACE_REL_AREA * 4)),
        reason=f"face_rel_area={rel:.4f} (min={MIN_FACE_REL_AREA:.4f})",
        details={"count": int(len(faces)), "largest_rel_area": rel},
    )


def _person_mask_gb(img_bgr: np.ndarray) -> np.ndarray:
    """Rough person foreground mask via GrabCut on center rect.

    Not a body segmentation — just good enough for "person present and not
    cropped" heuristics. Much cheaper than loading a segmentation model.
    """
    h, w = img_bgr.shape[:2]
    mask = np.zeros((h, w), np.uint8)
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    # Center rect covering ~80% of image.
    rect = (int(w * 0.1), int(h * 0.05), int(w * 0.8), int(h * 0.9))
    try:
        cv2.grabCut(img_bgr, mask, rect, bgd, fgd, 2, cv2.GC_INIT_WITH_RECT)
    except cv2.error:
        return np.zeros((h, w), np.uint8)
    fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    return fg


def check_framing(img_bgr: np.ndarray) -> PreflightFinding:
    h, w = img_bgr.shape[:2]
    # Use a downscaled copy — GrabCut is expensive.
    scale = 256.0 / min(h, w)
    if scale < 1.0:
        small = cv2.resize(img_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    else:
        small = img_bgr
    sh, sw = small.shape[:2]
    fg = _person_mask_gb(small)
    rel_area = float(fg.sum()) / (255.0 * sh * sw)

    if rel_area < MIN_PERSON_REL_AREA:
        return PreflightFinding(
            name="framing",
            passed=False,
            score=rel_area / max(MIN_PERSON_REL_AREA, 1e-6),
            reason=f"person region too small ({rel_area:.2%} < {MIN_PERSON_REL_AREA:.0%})",
            details={"person_rel_area": rel_area},
        )

    # Heuristic crop check: if mask touches the top border heavily, head is
    # likely cut off; similarly for left/right with big area implies hard crop.
    top_touch = float(fg[0, :].sum()) / (255.0 * sw)
    left_touch = float(fg[:, 0].sum()) / (255.0 * sh)
    right_touch = float(fg[:, -1].sum()) / (255.0 * sh)
    cropped_sides = [t for t in (top_touch, left_touch, right_touch) if t > BORDER_CUTOFF_FRAC]

    if cropped_sides:
        return PreflightFinding(
            name="framing",
            passed=False,
            score=0.3,
            reason=(
                f"figure cropped at borders: top={top_touch:.2f} "
                f"L={left_touch:.2f} R={right_touch:.2f}"
            ),
            details={
                "person_rel_area": rel_area,
                "top_touch": top_touch,
                "left_touch": left_touch,
                "right_touch": right_touch,
            },
        )

    return PreflightFinding(
        name="framing",
        passed=True,
        score=min(1.0, rel_area / 0.4),
        reason=f"person_rel_area={rel_area:.2%}, borders ok",
        details={"person_rel_area": rel_area},
    )


# ── Aggregator ────────────────────────────────────────────────────────

# Which checks are hard-fail vs. soft-warn.
HARD_CHECKS = {"resolution", "blur", "face", "framing"}


def run_preflight(person_image) -> PreflightReport:
    """Run all input quality gates on the person image.

    Args:
        person_image: PIL.Image (RGB) or BGR numpy uint8.

    Returns:
        PreflightReport. `passed=False` means the job should be rejected
        without spending GPU time; `error_code` is set to
        `INPUT_QUALITY_FAILED` in that case.
    """
    if isinstance(person_image, Image.Image):
        img_bgr = cv2.cvtColor(np.array(person_image.convert("RGB")), cv2.COLOR_RGB2BGR)
    else:
        img_bgr = np.asarray(person_image)
        if img_bgr.ndim == 2:
            img_bgr = cv2.cvtColor(img_bgr, cv2.COLOR_GRAY2BGR)

    findings = [
        check_resolution(img_bgr),
        check_blur(img_bgr),
        check_face(img_bgr),
        check_framing(img_bgr),
    ]

    failed = [f for f in findings if not f.passed and f.name in HARD_CHECKS]
    passed = len(failed) == 0
    summary = (
        "all input quality gates passed"
        if passed
        else "failed: " + ", ".join(f"{f.name}({f.reason})" for f in failed)
    )
    return PreflightReport(
        passed=passed,
        findings=findings,
        error_code=None if passed else ErrorCode.INPUT_QUALITY_FAILED,
        summary=summary,
    )
