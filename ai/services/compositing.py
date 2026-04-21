"""Seam blending / compositing utilities for VTON results.

Goal: replace ONLY the garment region of the original person image with the
generated output, using a feathered mask. This guarantees that face, hair,
background and non-garment body parts stay byte-identical to the original,
which eliminates the most common "face drift" / "background changed"
artifacts produced by diffusion-based try-on models.

All inputs/outputs are numpy uint8 arrays in BGR unless stated otherwise.
"""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image
from typing import Optional


def _to_numpy_mask(mask) -> np.ndarray:
    """Accept PIL 'L' image or numpy array, return uint8 HxW in [0,255]."""
    if isinstance(mask, Image.Image):
        mask = np.array(mask.convert("L"))
    mask = np.asarray(mask)
    if mask.ndim == 3:
        mask = mask[..., 0]
    if mask.dtype != np.uint8:
        mask = mask.astype(np.uint8)
    return mask


def feather_mask(
    mask: np.ndarray,
    feather_px: int = 11,
    erode_px: int = 0,
) -> np.ndarray:
    """Return float32 mask in [0,1] with feathered edges.

    Args:
        mask: uint8 HxW, 0 or 255.
        feather_px: Gaussian blur radius for feathering. Higher = softer seam.
        erode_px: Optional pre-erosion in pixels to pull the seam inward
            (useful when the agnostic mask overshoots the actual garment).
    """
    m = (mask > 127).astype(np.uint8) * 255
    if erode_px > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (erode_px * 2 + 1,) * 2)
        m = cv2.erode(m, k, iterations=1)
    if feather_px > 0:
        ksize = feather_px * 2 + 1
        m_f = cv2.GaussianBlur(m.astype(np.float32), (ksize, ksize), 0) / 255.0
    else:
        m_f = m.astype(np.float32) / 255.0
    return np.clip(m_f, 0.0, 1.0)


def seam_blend(
    original_bgr: np.ndarray,
    generated_bgr: np.ndarray,
    agnostic_mask,
    feather_px: int = 11,
    erode_px: int = 2,
    match_colors: bool = True,
) -> np.ndarray:
    """Composite `generated_bgr` into `original_bgr` over the garment region.

    Args:
        original_bgr: Original person image (BGR uint8, HxWx3).
        generated_bgr: VTON output (BGR uint8). Resized to match original if needed.
        agnostic_mask: PIL 'L' or numpy HxW mask. 255 = region to replace.
        feather_px: Seam feathering radius in pixels.
        erode_px: Erode the mask slightly to avoid edge bleeding from the
            diffusion output into the untouched area.
        match_colors: If True, match global garment-region mean/std of the
            generated image to a narrow band around the seam, reducing
            obvious hue/brightness mismatches.

    Returns:
        Blended BGR uint8 image, same HxW as the original.
    """
    h, w = original_bgr.shape[:2]
    if generated_bgr.shape[:2] != (h, w):
        generated_bgr = cv2.resize(
            generated_bgr, (w, h), interpolation=cv2.INTER_LANCZOS4
        )

    m = _to_numpy_mask(agnostic_mask)
    if m.shape != (h, w):
        m = cv2.resize(m, (w, h), interpolation=cv2.INTER_NEAREST)

    soft = feather_mask(m, feather_px=feather_px, erode_px=erode_px)[..., None]

    gen = generated_bgr.astype(np.float32)
    orig = original_bgr.astype(np.float32)

    if match_colors:
        gen = _match_colors_near_seam(orig, gen, m)

    blended = gen * soft + orig * (1.0 - soft)
    return np.clip(blended, 0, 255).astype(np.uint8)


def _match_colors_near_seam(
    orig: np.ndarray,
    gen: np.ndarray,
    mask: np.ndarray,
    band_px: int = 15,
) -> np.ndarray:
    """Lightly shift generated colors so the seam band matches the original.

    Computes per-channel mean in a thin band JUST outside the garment mask
    (from the original) and JUST inside (from the generated), then applies
    an additive offset to the whole generated image. Intentionally mild to
    avoid destroying the garment's own color.
    """
    if mask.max() == 0:
        return gen

    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (band_px * 2 + 1,) * 2)
    dil = cv2.dilate(mask, k, iterations=1)
    ero = cv2.erode(mask, k, iterations=1)
    band_outside = ((dil > 0) & (mask == 0)).astype(bool)
    band_inside = ((mask > 0) & (ero == 0)).astype(bool)

    if band_outside.sum() < 50 or band_inside.sum() < 50:
        return gen

    mean_out = orig[band_outside].mean(axis=0)
    mean_in = gen[band_inside].mean(axis=0)
    shift = (mean_out - mean_in) * 0.3  # conservative
    return gen + shift[None, None, :]
