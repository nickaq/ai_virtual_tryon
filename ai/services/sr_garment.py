"""Super-resolution restricted to the garment region.

Strategy:
  1. Crop the garment bbox from the blended result (plus a small margin).
  2. Run a SR upscaler on that crop (Real-ESRGAN if installed, otherwise a
     high-quality sharpening fallback that never downgrades quality).
  3. Resize the SR crop back to the original crop size with Lanczos.
  4. Paste back over the garment region only, using the garment mask with
     a small feather so the seam stays invisible.

Why restrict to the garment? Because SR models love hallucinating face
details and that is exactly what we just protected via seam blending.
Keeping SR inside the garment polygon preserves face/hair pixel-perfectly
while sharpening print, seams and fabric texture — the stuff users
actually judge a try-on on.

The heavy Real-ESRGAN path is optional; enable it with
``VTON_GARMENT_SR=1`` and have ``realesrgan`` + ``basicsr`` installed.
"""
from __future__ import annotations

import os
import cv2
import numpy as np
from typing import Optional

from .preprocessing import (
    ALL_CLOTHING_LABELS,
    UPPER_CLOTHING_LABELS,
    LOWER_CLOTHING_LABELS,
)


# ── Config ────────────────────────────────────────────────────────────
VTON_GARMENT_SR = os.environ.get("VTON_GARMENT_SR", "0") == "1"
VTON_GARMENT_SR_SCALE = int(os.environ.get("VTON_GARMENT_SR_SCALE", "2"))
VTON_GARMENT_SR_PAD = int(os.environ.get("VTON_GARMENT_SR_PAD", "16"))
VTON_GARMENT_SR_FEATHER = int(os.environ.get("VTON_GARMENT_SR_FEATHER", "5"))


# ── Model loading (lazy, optional) ───────────────────────────────────
_sr_model = None
_sr_backend: Optional[str] = None


def _load_realesrgan():
    """Return a Real-ESRGAN upscaler or None if deps/weights unavailable."""
    global _sr_model, _sr_backend
    if _sr_model is not None or _sr_backend == "unavailable":
        return _sr_model
    try:
        from realesrgan import RealESRGANer
        from basicsr.archs.rrdbnet_arch import RRDBNet
    except ImportError:
        _sr_backend = "unavailable"
        print("  [sr_garment] realesrgan not installed — using sharpening fallback")
        return None

    weight_path = os.environ.get("REALESRGAN_WEIGHTS", "")
    if not weight_path or not os.path.exists(weight_path):
        _sr_backend = "unavailable"
        print(
            "  [sr_garment] REALESRGAN_WEIGHTS not set or missing, "
            "using sharpening fallback"
        )
        return None

    import torch

    model = RRDBNet(
        num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32,
        scale=VTON_GARMENT_SR_SCALE,
    )
    _sr_model = RealESRGANer(
        scale=VTON_GARMENT_SR_SCALE,
        model_path=weight_path,
        model=model,
        tile=400,
        tile_pad=10,
        pre_pad=0,
        half=torch.cuda.is_available(),
        device="cuda" if torch.cuda.is_available() else "cpu",
    )
    _sr_backend = "realesrgan"
    print(f"  [sr_garment] Real-ESRGAN loaded (scale={VTON_GARMENT_SR_SCALE})")
    return _sr_model


def _upscale(crop_bgr: np.ndarray) -> np.ndarray:
    """Upscale a BGR crop by ``VTON_GARMENT_SR_SCALE`` using the best
    available backend; always returns a crop of the SAME size as the input
    (downscaled back after SR) for drop-in compositing."""
    h, w = crop_bgr.shape[:2]
    model = _load_realesrgan()
    if model is not None:
        try:
            sr, _ = model.enhance(crop_bgr, outscale=VTON_GARMENT_SR_SCALE)
            sharp = cv2.resize(sr, (w, h), interpolation=cv2.INTER_LANCZOS4)
            return sharp
        except Exception as e:
            print(f"  [sr_garment] Real-ESRGAN enhance failed: {e}; fallback")

    # Fallback: Lanczos upsample + unsharp mask + Lanczos downsample.
    up = cv2.resize(
        crop_bgr, (w * VTON_GARMENT_SR_SCALE, h * VTON_GARMENT_SR_SCALE),
        interpolation=cv2.INTER_LANCZOS4,
    )
    blurred = cv2.GaussianBlur(up, (0, 0), sigmaX=1.2)
    unsharp = cv2.addWeighted(up, 1.35, blurred, -0.35, 0)
    return cv2.resize(unsharp, (w, h), interpolation=cv2.INTER_LANCZOS4)


# ── Mask helpers ──────────────────────────────────────────────────────

def _garment_labels(category: str) -> set[int]:
    if category == "lower_body":
        return LOWER_CLOTHING_LABELS
    if category == "dresses":
        return ALL_CLOTHING_LABELS
    return UPPER_CLOTHING_LABELS


def _garment_mask_from_parsing(
    parsing_map: np.ndarray, category: str, shape: tuple[int, int]
) -> np.ndarray:
    h, w = shape
    labels = _garment_labels(category)
    mask = np.isin(parsing_map, list(labels)).astype(np.uint8) * 255
    if mask.shape != (h, w):
        mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
    return mask


# ── Public API ────────────────────────────────────────────────────────

def enhance_garment_region(
    image_bgr: np.ndarray,
    parsing_map: Optional[np.ndarray] = None,
    agnostic_mask: Optional[np.ndarray] = None,
    category: str = "upper_body",
) -> np.ndarray:
    """Sharpen/upscale only the garment region; return a new BGR image.

    If ``VTON_GARMENT_SR`` is off, the input is returned unchanged.
    """
    if not VTON_GARMENT_SR:
        return image_bgr

    h, w = image_bgr.shape[:2]
    if parsing_map is not None and parsing_map.shape[:2] == (h, w):
        mask = _garment_mask_from_parsing(parsing_map, category, (h, w))
    elif agnostic_mask is not None:
        mask = agnostic_mask
        if mask.shape[:2] != (h, w):
            mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
    else:
        return image_bgr

    ys, xs = np.where(mask > 0)
    if ys.size < 100:
        return image_bgr

    pad = VTON_GARMENT_SR_PAD
    y0 = max(0, ys.min() - pad)
    y1 = min(h, ys.max() + 1 + pad)
    x0 = max(0, xs.min() - pad)
    x1 = min(w, xs.max() + 1 + pad)

    crop = image_bgr[y0:y1, x0:x1].copy()
    enhanced = _upscale(crop)

    # Feathered crop mask restricted to the garment region within the crop.
    crop_mask = mask[y0:y1, x0:x1].astype(np.uint8)
    if VTON_GARMENT_SR_FEATHER > 0:
        k = VTON_GARMENT_SR_FEATHER * 2 + 1
        soft = cv2.GaussianBlur(crop_mask.astype(np.float32), (k, k), 0) / 255.0
    else:
        soft = (crop_mask > 0).astype(np.float32)
    soft = np.clip(soft, 0.0, 1.0)[..., None]

    blended_crop = enhanced.astype(np.float32) * soft + crop.astype(np.float32) * (1.0 - soft)
    out = image_bgr.copy()
    out[y0:y1, x0:x1] = np.clip(blended_crop, 0, 255).astype(np.uint8)
    return out
