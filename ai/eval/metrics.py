"""Evaluation metrics for VTON.

- `GarmentPreservationScore`: lightweight, dependency-free, used in production
  as a reranking signal (see `ai/services/garment_score.py`).
- `calculate_fid` / `calculate_lpips`: optional hooks for offline/training-time
  evaluation. Require extra deps (`pytorch-fid`, `lpips`) and are intentionally
  left as no-ops when those packages are not installed.
"""
from __future__ import annotations

from typing import Optional
import numpy as np

from ai.services.garment_score import garment_preservation_score


def calculate_fid(real_images, fake_images) -> Optional[float]:
    """Frechet Inception Distance. Lower is better.

    Returns None if `pytorch-fid` is not installed.
    """
    try:
        from pytorch_fid.fid_score import calculate_fid_given_paths  # noqa: F401
    except ImportError:
        return None
    raise NotImplementedError(
        "Wire up pytorch-fid with paths to folders of real/fake images."
    )


def calculate_lpips(real_images, fake_images) -> Optional[float]:
    """LPIPS perceptual distance. Lower = more similar.

    Returns None if `lpips` is not installed.
    """
    try:
        import lpips  # noqa: F401
        import torch  # noqa: F401
    except ImportError:
        return None
    raise NotImplementedError("Wire up lpips.LPIPS() on batched tensors.")


class GarmentPreservationScore:
    """Measures how well the generated image preserves the reference garment.

    Delegates to `ai.services.garment_score.garment_preservation_score`,
    which uses HSV histogram correlation + edge-density similarity over the
    garment region. Returns a score in [0, 1], higher is better.
    """

    def __init__(self):
        pass

    def __call__(
        self,
        generated_img: np.ndarray,
        original_garment_img,
        generated_garment_mask: Optional[np.ndarray] = None,
        parsing_map: Optional[np.ndarray] = None,
        category: str = "upper_body",
    ) -> float:
        result = garment_preservation_score(
            reference_garment=original_garment_img,
            generated_image=generated_img,
            parsing_map=parsing_map,
            agnostic_mask=generated_garment_mask,
            category=category,
        )
        return float(result["score"])
