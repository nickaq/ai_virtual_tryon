"""Stage 6: Refinement through Local Stable Diffusion API."""
import os
import cv2
import numpy as np
from typing import Optional, Dict, Any
from PIL import Image

# Import configurations
from backend.config import settings
from backend.models.job import ErrorCode

class DiffusionAPIError(Exception):
    """Error during Diffusion generation."""
    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)

# Global variables for caching model locally
_pipeline = None

def _get_pipeline():
    """Lazily load the diffusion pipeline."""
    global _pipeline
    if _pipeline is not None:
        return _pipeline
        
    try:
        import torch
        from diffusers import StableDiffusionImg2ImgPipeline
        
        # Load the stable diffusion pipeline (img2img mode for refinement)
        model_id = settings.diffusion_model_id
        device = settings.diffusion_device
        
        print(f"Loading local diffusion model: {model_id} on {device}...")
        _pipeline = StableDiffusionImg2ImgPipeline.from_pretrained(
            model_id,
            torch_dtype=torch.float16 if device in ["cuda", "mps"] else torch.float32,
            safety_checker=None
        ).to(device)
        
        return _pipeline
    except ImportError:
        raise DiffusionAPIError(
            "diffusers or torch is not installed. Please install diffusers and pytorch to use local diffusion.",
            ErrorCode.UNKNOWN_ERROR
        )
    except Exception as e:
        raise DiffusionAPIError(f"Failed to load diffusion pipeline: {e}")

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

async def refine_image_with_diffusion(
    person_image: np.ndarray,
    garment_image: np.ndarray,
    draft_composite: np.ndarray,
    preserve_face: bool = True,
    preserve_background: bool = True,
    realism_level: int = 3,
    garment_type: Optional[str] = None
) -> np.ndarray:
    """
    Refine the draft composite using local Stable Diffusion Img2Img.
    
    Args:
        person_image: Original person (RGB HWC uint8)
        garment_image: Original garment (RGB HWC uint8)
        draft_composite: Coarse TryOn from geometric alignment (RGB HWC uint8)
        preserve_face: Whether to prioritize face
        preserve_background: Whether to prioritize background
        realism_level: Adjusts strength roughly. 1-5 where 5 is higher strength.
        garment_type: Optional category hint for prompt
        
    Returns:
        Refined image (RGB HWC uint8)
    """
    try:
        pipeline = _get_pipeline()
        
        # Determine exact runtime hyperparameters from realism_level
        # The user's specification states: strength: 0.25-0.4, steps: 20, guidance: 7-8
        base_strength = 0.25
        strength_increment = 0.03 * (realism_level - 1)  # scale up the denoise strength with retry
        strength = min(0.4, base_strength + strength_increment)
        
        guidance_scale = 7.5
        num_inference_steps = 20
        
        prompt = create_prompt(garment_type, preserve_face, preserve_background)
        negative_prompt = "blurry, mutated, deformed, cartoon, illustration, badly drawn face, ugly, multiple limbs, watermark"
        
        # Convert numpy array to PIL Image
        init_image = Image.fromarray(draft_composite)
        
        print(f"Running Local Diffusion on {settings.diffusion_device}...")
        print(f" -> Strength: {strength:.2f}, Guidance: {guidance_scale}, Prompt: {prompt}")
        
        result_imgs = pipeline(
            prompt=prompt,
            negative_prompt=negative_prompt,
            image=init_image,
            strength=strength,
            guidance_scale=guidance_scale,
            num_inference_steps=num_inference_steps
        ).images
        
        final_image = np.array(result_imgs[0])
        return final_image
        
    except DiffusionAPIError as e:
        # Pass through expected API exceptions
        raise e
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise DiffusionAPIError(f"Unexpected error during Diffusion run: {e}")
