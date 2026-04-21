"""Garment preservation score.

Measures how well the generated image preserves the reference garment's
color distribution and edge/texture structure. Used as a reranking signal
for multi-sample VTON inference.

Implementation intentionally uses only OpenCV + NumPy (no extra model
weights) so it stays cheap and dependency-free. If a CLIP image encoder is
already in memory (e.g. from IDM-VTON), `clip_cosine` can be plugged in
later; see `ai/eval/metrics.py` for the hook.

Score is in [0, 1], higher = stronger preservation.
"""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image
from typing import Optional

from .preprocessing import ALL_CLOTHING_LABELS, UPPER_CLOTHING_LABELS, LOWER_CLOTHING_LABELS


def _to_bgr(img) -> np.ndarray:
    if isinstance(img, Image.Image):
        arr = np.array(img.convert("RGB"))
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    arr = np.asarray(img)
    if arr.ndim == 2:
        arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
    return arr


def _garment_labels(category: str) -> set[int]:
    if category == "lower_body":
        return LOWER_CLOTHING_LABELS
    if category == "dresses":
        return ALL_CLOTHING_LABELS
    return UPPER_CLOTHING_LABELS


def _extract_garment_region(
    img_bgr: np.ndarray,
    mask: np.ndarray,
) -> Optional[np.ndarray]:
    """Return the tight-cropped garment region, or None if empty."""
    ys, xs = np.where(mask > 0)
    if ys.size < 50:
        return None
    y0, y1 = ys.min(), ys.max() + 1
    x0, x1 = xs.min(), xs.max() + 1
    crop = img_bgr[y0:y1, x0:x1]
    cmask = mask[y0:y1, x0:x1]
    out = crop.copy()
    out[cmask == 0] = 0
    return out


def _hsv_hist(img_bgr_masked: np.ndarray, mask: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(img_bgr_masked, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], mask, [32, 32], [0, 180, 0, 256])
    cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
    return hist


def _edge_density(img_bgr_masked: np.ndarray, mask: np.ndarray) -> float:
    gray = cv2.cvtColor(img_bgr_masked, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    area = max(int(mask.sum() // 255), 1) if mask.dtype == np.uint8 else max(int(mask.sum()), 1)
    return float(edges.sum()) / (255.0 * area)


def garment_preservation_score(
    reference_garment: Image.Image | np.ndarray,
    generated_image: np.ndarray,
    parsing_map: Optional[np.ndarray] = None,
    agnostic_mask: Optional[np.ndarray] = None,
    category: str = "upper_body",
) -> dict:
    """Compute garment preservation score between the reference garment and
    the garment region of the generated result.

    Args:
        reference_garment: Reference garment product photo (PIL or BGR ndarray).
        generated_image: Generated try-on output (BGR uint8).
        parsing_map: Human parsing map of the generated image (preferred). If
            absent, falls back to `agnostic_mask`.
        agnostic_mask: Binary mask over the garment region (uint8 0/255).
        category: Clothing category for label selection.

    Returns:
        dict with keys: `score` (0..1), `color`, `edges`, `reason`.
    """
    gen_bgr = _to_bgr(generated_image)
    ref_bgr = _to_bgr(reference_garment)

    h, w = gen_bgr.shape[:2]

    if parsing_map is not None and parsing_map.shape[:2] == (h, w):
        labels = _garment_labels(category)
        gen_mask = np.isin(parsing_map, list(labels)).astype(np.uint8) * 255
    elif agnostic_mask is not None:
        gen_mask = agnostic_mask
        if gen_mask.shape[:2] != (h, w):
            gen_mask = cv2.resize(gen_mask, (w, h), interpolation=cv2.INTER_NEAREST)
    else:
        return {"score": 0.5, "color": 0.0, "edges": 0.0, "reason": "no_mask"}

    if gen_mask.sum() < 100 * 255:
        return {"score": 0.5, "color": 0.0, "edges": 0.0, "reason": "tiny_mask"}

    # For the reference, assume the garment occupies the full image; tighten
    # with a simple saturation-based foreground mask to drop neutral backgrounds.
    ref_hsv = cv2.cvtColor(ref_bgr, cv2.COLOR_BGR2HSV)
    ref_mask = (ref_hsv[..., 1] > 20).astype(np.uint8) * 255
    if ref_mask.sum() < ref_mask.size * 0.05 * 255:
        ref_mask = np.full(ref_bgr.shape[:2], 255, dtype=np.uint8)

    gen_region = _extract_garment_region(gen_bgr, gen_mask)
    ref_region = _extract_garment_region(ref_bgr, ref_mask)
    if gen_region is None or ref_region is None:
        return {"score": 0.5, "color": 0.0, "edges": 0.0, "reason": "empty_region"}

    # Resize ref to match gen region scale for fair edge comparison
    gh, gw = gen_region.shape[:2]
    ref_resized = cv2.resize(ref_region, (gw, gh), interpolation=cv2.INTER_AREA)

    # Recompute in-crop masks for metric computation
    gen_region_mask = (gen_region.sum(axis=2) > 0).astype(np.uint8) * 255
    ref_region_mask = (ref_resized.sum(axis=2) > 0).astype(np.uint8) * 255

    # Color: HSV histogram correlation (robust to shape/pose)
    h_gen = _hsv_hist(gen_region, gen_region_mask)
    h_ref = _hsv_hist(ref_resized, ref_region_mask)
    color_sim = float(cv2.compareHist(h_gen, h_ref, cv2.HISTCMP_CORREL))
    color_sim = max(0.0, min(1.0, (color_sim + 1.0) / 2.0))

    # Edges: ratio of edge densities (proxy for print/texture richness)
    ed_gen = _edge_density(gen_region, gen_region_mask)
    ed_ref = _edge_density(ref_resized, ref_region_mask)
    if max(ed_gen, ed_ref) < 1e-6:
        edge_sim = 1.0
    else:
        edge_sim = 1.0 - abs(ed_gen - ed_ref) / max(ed_gen, ed_ref)
    edge_sim = max(0.0, min(1.0, edge_sim))

    score = 0.7 * color_sim + 0.3 * edge_sim
    return {
        "score": float(score),
        "color": color_sim,
        "edges": edge_sim,
        "reason": "ok",
    }
