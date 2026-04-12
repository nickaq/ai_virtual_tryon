"""
Stage 8: Refinement through Local Stable Diffusion.

This module is a POST-GEOMETRIC refinement step. Input MUST be a coarse
composite image produced by the alignment stage (TPS warp + occlusion composite).
Diffusion does NOT replace geometric alignment — it refines the output by
smoothing seams, improving fabric texture, and enhancing photorealism.

Two refinement modes are supported:
  - IMG2IMG: Stable Diffusion img2img pipeline — refines the entire composite
  - INPAINTING: Stable Diffusion inpainting pipeline — refines only the garment
    region while preserving the person and background exactly

Hyperparameters:
  - strength: 0.25–0.40 (controls how much the diffusion changes the image)
  - guidance_scale: 7.5 (classifier-free guidance for prompt adherence)
  - num_inference_steps: 20 (denoising steps — balance of speed and quality)
"""
import os
import cv2
import numpy as np
from enum import Enum
from typing import Optional, Dict, Any
from PIL import Image

import torch
if not hasattr(torch, "xpu"):
    from unittest.mock import MagicMock
    mock_xpu = MagicMock()
    mock_xpu.is_available.return_value = False
    torch.xpu = mock_xpu

# Import configurations
from backend.config import settings
from backend.models.job import ErrorCode


class RefinementMode(str, Enum):
    """Diffusion refinement mode."""
    IMG2IMG = "img2img"
    INPAINTING = "inpainting"


class DiffusionAPIError(Exception):
    """Error during Diffusion generation."""
    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.DIFFUSION_ERROR):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


# ── Documented Hyperparameters ──────────────────────────────────────
REFINEMENT_HYPERPARAMS = {
    "img2img": {
        "base_strength": 0.25,          # Minimum denoising strength
        "max_strength": 0.40,           # Maximum denoising strength
        "strength_increment": 0.03,     # Increment per retry level
        "guidance_scale": 7.5,          # CFG scale
        "num_inference_steps": 20,      # Denoising steps
    },
    "inpainting": {
        "base_strength": 0.50,          # Higher for inpainting (masked region only)
        "max_strength": 0.75,           # More aggressive for masked refinement
        "strength_increment": 0.05,     # Increment per retry level
        "guidance_scale": 7.5,          # CFG scale
        "num_inference_steps": 25,      # Slightly more steps for masked detail
    },
}


# ── Pipeline Caching ────────────────────────────────────────────────
_img2img_pipeline = None
_inpainting_pipeline = None


def _get_img2img_pipeline():
    """Lazily load the img2img diffusion pipeline."""
    global _img2img_pipeline
    if _img2img_pipeline is not None:
        return _img2img_pipeline
        
    try:
        import torch
        from diffusers import StableDiffusionImg2ImgPipeline
        
        model_id = settings.diffusion_model_id
        device = settings.diffusion_device
        
        print(f"Loading img2img diffusion model: {model_id} on {device}...")
        _img2img_pipeline = StableDiffusionImg2ImgPipeline.from_pretrained(
            model_id,
            torch_dtype=torch.float16 if device in ["cuda", "mps"] else torch.float32,
            safety_checker=None
        ).to(device)
        
        return _img2img_pipeline
    except ImportError:
        raise DiffusionAPIError(
            "diffusers or torch is not installed. Please install diffusers and pytorch to use local diffusion.",
            ErrorCode.DIFFUSION_ERROR
        )
    except Exception as e:
        raise DiffusionAPIError(f"Failed to load img2img pipeline: {e}")


def _get_inpainting_pipeline():
    """Lazily load the inpainting diffusion pipeline."""
    global _inpainting_pipeline
    if _inpainting_pipeline is not None:
        return _inpainting_pipeline
        
    try:
        import torch
        from diffusers import StableDiffusionInpaintPipeline
        
        model_id = settings.diffusion_inpaint_model_id
        device = settings.diffusion_device
        
        print(f"Loading inpainting diffusion model: {model_id} on {device}...")
        _inpainting_pipeline = StableDiffusionInpaintPipeline.from_pretrained(
            model_id,
            torch_dtype=torch.float16 if device in ["cuda", "mps"] else torch.float32,
            safety_checker=None
        ).to(device)
        
        return _inpainting_pipeline
    except ImportError:
        raise DiffusionAPIError(
            "diffusers or torch is not installed. Please install diffusers and pytorch.",
            ErrorCode.DIFFUSION_ERROR
        )
    except Exception as e:
        raise DiffusionAPIError(f"Failed to load inpainting pipeline: {e}")


def create_prompt(
    garment_type: Optional[str] = None,
    preserve_face: bool = True,
    preserve_background: bool = True
) -> str:
    """Create prompt for Stable Diffusion."""
    garment_desc = "wearing "
    if garment_type:
        garment_desc += f"{garment_type.replace('_', ' ')}"
    else:
        garment_desc += "clothing"
        
    prompt = f"high quality photorealistic image of a person {garment_desc}, perfect fit, detailed fabric texture, high resolution"
    
    if preserve_face:
        prompt += ", precise facial features"
    
    if preserve_background:
        prompt += ", natural background"
        
    return prompt


NEGATIVE_PROMPT = (
    "blurry, mutated, deformed, cartoon, illustration, "
    "badly drawn face, ugly, multiple limbs, watermark"
)


async def _refine_with_img2img(
    draft_composite: np.ndarray,
    prompt: str,
    realism_level: int = 3
) -> np.ndarray:
    """
    Refine using img2img pipeline.
    Processes the ENTIRE image through the diffusion model.
    """
    pipeline = _get_img2img_pipeline()
    params = REFINEMENT_HYPERPARAMS["img2img"]
    
    strength = min(
        params["max_strength"],
        params["base_strength"] + params["strength_increment"] * (realism_level - 1)
    )
    
    init_image = Image.fromarray(cv2.cvtColor(draft_composite, cv2.COLOR_BGR2RGB))
    
    print(f"  [img2img] Strength: {strength:.2f}, Guidance: {params['guidance_scale']}")
    
    result_imgs = pipeline(
        prompt=prompt,
        negative_prompt=NEGATIVE_PROMPT,
        image=init_image,
        strength=strength,
        guidance_scale=params["guidance_scale"],
        num_inference_steps=params["num_inference_steps"]
    ).images
    
    return cv2.cvtColor(np.array(result_imgs[0]), cv2.COLOR_RGB2BGR)


async def _refine_with_inpainting(
    draft_composite: np.ndarray,
    garment_mask: np.ndarray,
    prompt: str,
    realism_level: int = 3
) -> np.ndarray:
    """
    Refine using inpainting pipeline.
    Only the garment region (defined by garment_mask) is regenerated;
    the person's face, body, and background are preserved exactly.
    """
    pipeline = _get_inpainting_pipeline()
    params = REFINEMENT_HYPERPARAMS["inpainting"]
    
    strength = min(
        params["max_strength"],
        params["base_strength"] + params["strength_increment"] * (realism_level - 1)
    )
    
    # Prepare PIL images
    init_image = Image.fromarray(cv2.cvtColor(draft_composite, cv2.COLOR_BGR2RGB))
    
    # Inpainting mask: white = region to regenerate (garment area)
    mask_image = Image.fromarray(garment_mask).convert("L")
    
    print(f"  [inpainting] Strength: {strength:.2f}, Guidance: {params['guidance_scale']}")
    
    result_imgs = pipeline(
        prompt=prompt,
        negative_prompt=NEGATIVE_PROMPT,
        image=init_image,
        mask_image=mask_image,
        strength=strength,
        guidance_scale=params["guidance_scale"],
        num_inference_steps=params["num_inference_steps"]
    ).images
    
    return cv2.cvtColor(np.array(result_imgs[0]), cv2.COLOR_RGB2BGR)


async def refine_image_with_diffusion(
    person_image: np.ndarray,
    garment_image: np.ndarray,
    draft_composite: np.ndarray,
    preserve_face: bool = True,
    preserve_background: bool = True,
    realism_level: int = 3,
    garment_type: Optional[str] = None,
    mode: RefinementMode = RefinementMode.IMG2IMG,
    garment_mask: Optional[np.ndarray] = None
) -> np.ndarray:
    """
    Refine the draft composite using local Stable Diffusion.

    IMPORTANT: This function operates on the OUTPUT of geometric alignment.
    The draft_composite must already contain the warped garment composited
    onto the person image. Diffusion refines — it does not replace geometry.
    
    Args:
        person_image: Original person (RGB HWC uint8)
        garment_image: Original garment (RGB HWC uint8)
        draft_composite: Coarse TryOn from geometric alignment (RGB HWC uint8)
        preserve_face: Whether to prioritize face
        preserve_background: Whether to prioritize background
        realism_level: Adjusts strength roughly. 1-5 where 5 is higher strength.
        garment_type: Optional category hint for prompt
        mode: Refinement mode — IMG2IMG or INPAINTING
        garment_mask: Required for INPAINTING mode — mask of garment region
        
    Returns:
        Refined image (RGB HWC uint8)
    """
    assert draft_composite is not None, (
        "Diffusion requires geometric alignment output. "
        "draft_composite cannot be None."
    )

    try:
        prompt = create_prompt(garment_type, preserve_face, preserve_background)
        
        print(f"Running Local Diffusion ({mode.value}) on {settings.diffusion_device}...")
        
        if mode == RefinementMode.INPAINTING:
            if garment_mask is None:
                print("  Warning: No garment_mask provided for inpainting, falling back to img2img")
                return await _refine_with_img2img(draft_composite, prompt, realism_level)
            return await _refine_with_inpainting(
                draft_composite, garment_mask, prompt, realism_level
            )
        else:
            return await _refine_with_img2img(draft_composite, prompt, realism_level)
        
    except DiffusionAPIError as e:
        # Pass through expected API exceptions
        raise e
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise DiffusionAPIError(f"Unexpected error during Diffusion run: {e}")
