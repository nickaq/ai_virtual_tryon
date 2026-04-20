"""IDM-VTON inference service — specialized virtual try-on model.

Wraps the IDM-VTON pipeline (ECCV 2024) for single-image virtual try-on.
Model is loaded lazily on first call and cached for subsequent requests.
All blocking inference runs in a thread executor to keep the event loop free.
"""
import os
import sys
import asyncio
import functools
from typing import Optional

import torch
import numpy as np
from PIL import Image
from torchvision import transforms
from transformers import CLIPImageProcessor

from backend.models.job import ErrorCode

# Path to cloned IDM-VTON repository (set in Dockerfile)
IDM_VTON_PATH = os.environ.get("IDM_VTON_PATH", "/app/IDM-VTON")


class VTONInferenceError(Exception):
    """Error during VTON inference."""
    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.DIFFUSION_ERROR):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


# ── Pipeline singleton ────────────────────────────────────────────────
_pipeline = None
_clip_processor = None

NEGATIVE_PROMPT = "monochrome, lowres, bad anatomy, worst quality, low quality"


def _ensure_idm_vton_on_path():
    """Add IDM-VTON source to Python path so we can import its modules."""
    if IDM_VTON_PATH not in sys.path:
        sys.path.insert(0, IDM_VTON_PATH)


def _load_pipeline():
    """Load the full IDM-VTON pipeline (lazy, called once)."""
    global _pipeline, _clip_processor

    if _pipeline is not None:
        return _pipeline

    _ensure_idm_vton_on_path()

    print("Loading IDM-VTON pipeline...")

    from src.tryon_pipeline import StableDiffusionXLInpaintPipeline as TryonPipeline
    from src.unet_hacked_tryon import UNet2DConditionModel
    from src.unet_hacked_garmnet import UNet2DConditionModel as UNet2DConditionModel_ref
    from transformers import (
        CLIPVisionModelWithProjection,
        CLIPTextModel,
        CLIPTextModelWithProjection,
        AutoTokenizer,
    )
    from diffusers import AutoencoderKL, DDPMScheduler

    model_id = "yisol/IDM-VTON"
    dtype = torch.float16
    device = "cuda" if torch.cuda.is_available() else "cpu"

    print(f"  Loading model components from {model_id} on {device}...")

    noise_scheduler = DDPMScheduler.from_pretrained(model_id, subfolder="scheduler")
    vae = AutoencoderKL.from_pretrained(model_id, subfolder="vae", torch_dtype=dtype)
    unet = UNet2DConditionModel.from_pretrained(model_id, subfolder="unet", torch_dtype=dtype)
    image_encoder = CLIPVisionModelWithProjection.from_pretrained(
        model_id, subfolder="image_encoder", torch_dtype=dtype
    )
    unet_encoder = UNet2DConditionModel_ref.from_pretrained(
        model_id, subfolder="unet_encoder", torch_dtype=dtype, use_safetensors=True
    )
    text_encoder_one = CLIPTextModel.from_pretrained(
        model_id, subfolder="text_encoder", torch_dtype=dtype
    )
    text_encoder_two = CLIPTextModelWithProjection.from_pretrained(
        model_id, subfolder="text_encoder_2", torch_dtype=dtype
    )
    tokenizer_one = AutoTokenizer.from_pretrained(
        model_id, subfolder="tokenizer", revision=None, use_fast=False
    )
    tokenizer_two = AutoTokenizer.from_pretrained(
        model_id, subfolder="tokenizer_2", revision=None, use_fast=False
    )

    # Freeze all parameters
    for m in [unet, vae, image_encoder, unet_encoder, text_encoder_one, text_encoder_two]:
        m.requires_grad_(False)
    unet_encoder.to(device, dtype)
    unet.eval()
    unet_encoder.eval()

    pipe = TryonPipeline.from_pretrained(
        model_id,
        unet=unet,
        vae=vae,
        feature_extractor=CLIPImageProcessor(),
        text_encoder=text_encoder_one,
        text_encoder_2=text_encoder_two,
        tokenizer=tokenizer_one,
        tokenizer_2=tokenizer_two,
        scheduler=noise_scheduler,
        image_encoder=image_encoder,
        unet_encoder=unet_encoder,
        torch_dtype=dtype,
    ).to(device)

    _pipeline = pipe
    _clip_processor = CLIPImageProcessor()

    print("  IDM-VTON pipeline loaded successfully.")
    return pipe


# ── Public API ────────────────────────────────────────────────────────

# Standard IDM-VTON resolution
VTON_WIDTH = 768
VTON_HEIGHT = 1024

_transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize([0.5], [0.5]),
])


def _prepare_inputs(
    person_image: Image.Image,
    garment_image: Image.Image,
    densepose_image: Image.Image,
    agnostic_mask: Image.Image,
):
    """Prepare all tensor inputs for the pipeline."""
    # Resize to model resolution
    person_resized = person_image.resize((VTON_WIDTH, VTON_HEIGHT), Image.LANCZOS)
    garment_resized = garment_image.resize((VTON_WIDTH, VTON_HEIGHT), Image.LANCZOS)
    densepose_resized = densepose_image.resize((VTON_WIDTH, VTON_HEIGHT), Image.LANCZOS)
    mask_resized = agnostic_mask.resize((VTON_WIDTH, VTON_HEIGHT), Image.NEAREST)

    # Person image tensor [-1, 1]
    person_tensor = _transform(person_resized)

    # Garment tensors
    garment_tensor = _transform(garment_resized)
    garment_clip = _clip_processor(images=garment_resized, return_tensors="pt").pixel_values

    # DensePose tensor [-1, 1]
    densepose_tensor = _transform(densepose_resized)

    # Agnostic mask tensor [0, 1] — 1 = area to inpaint (clothing region)
    mask_tensor = transforms.ToTensor()(mask_resized)
    if mask_tensor.shape[0] > 1:
        mask_tensor = mask_tensor[:1]

    return {
        "person_tensor": person_tensor,
        "garment_tensor": garment_tensor,
        "garment_clip": garment_clip,
        "densepose_tensor": densepose_tensor,
        "mask_tensor": mask_tensor,
    }


async def try_on(
    person_image: Image.Image,
    garment_image: Image.Image,
    densepose_image: Image.Image,
    agnostic_mask: Image.Image,
    category: str = "upper_body",
    num_inference_steps: int = 30,
    guidance_scale: float = 2.0,
    seed: int = 42,
) -> Image.Image:
    """
    Run IDM-VTON virtual try-on inference.

    Args:
        person_image: Person photo (PIL RGB)
        garment_image: Garment photo (PIL RGB, ideally on clean background)
        densepose_image: DensePose visualization of person (PIL RGB)
        agnostic_mask: Mask where clothing goes (PIL L, white=clothing area)
        category: Clothing category for prompt (upper_body, lower_body, dresses)
        num_inference_steps: Diffusion steps (default 30)
        guidance_scale: CFG scale (default 2.0 — IDM-VTON uses low guidance)
        seed: Random seed for reproducibility

    Returns:
        Result image (PIL RGB, VTON_WIDTH x VTON_HEIGHT)

    Raises:
        VTONInferenceError: If inference fails
    """
    try:
        pipe = _load_pipeline()
        device = pipe.device

        inputs = _prepare_inputs(person_image, garment_image, densepose_image, agnostic_mask)

        # Build prompts
        category_text = category.replace("_", " ") if category else "upper body clothing"
        caption = f"model is wearing a {category_text}"
        caption_cloth = f"a photo of {category_text}"

        # Encode text prompts
        with torch.inference_mode():
            (
                prompt_embeds,
                negative_prompt_embeds,
                pooled_prompt_embeds,
                negative_pooled_prompt_embeds,
            ) = pipe.encode_prompt(
                [caption],
                num_images_per_prompt=1,
                do_classifier_free_guidance=True,
                negative_prompt=[NEGATIVE_PROMPT],
            )

            (prompt_embeds_c, _, _, _) = pipe.encode_prompt(
                [caption_cloth],
                num_images_per_prompt=1,
                do_classifier_free_guidance=False,
                negative_prompt=[NEGATIVE_PROMPT],
            )

        generator = torch.Generator(device).manual_seed(seed)

        # Run inference in thread executor to avoid blocking event loop
        def _run():
            with torch.no_grad(), torch.cuda.amp.autocast():
                return pipe(
                    prompt_embeds=prompt_embeds,
                    negative_prompt_embeds=negative_prompt_embeds,
                    pooled_prompt_embeds=pooled_prompt_embeds,
                    negative_pooled_prompt_embeds=negative_pooled_prompt_embeds,
                    num_inference_steps=num_inference_steps,
                    generator=generator,
                    strength=1.0,
                    pose_img=inputs["densepose_tensor"].unsqueeze(0).to(device, torch.float16),
                    text_embeds_cloth=prompt_embeds_c,
                    cloth=inputs["garment_tensor"].unsqueeze(0).to(device, torch.float16),
                    mask_image=inputs["mask_tensor"].unsqueeze(0),
                    image=(inputs["person_tensor"].unsqueeze(0) + 1.0) / 2.0,
                    height=VTON_HEIGHT,
                    width=VTON_WIDTH,
                    guidance_scale=guidance_scale,
                    ip_adapter_image=inputs["garment_clip"].to(device, torch.float16),
                )[0]

        loop = asyncio.get_running_loop()
        images = await loop.run_in_executor(None, _run)
        return images[0]

    except VTONInferenceError:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise VTONInferenceError(f"IDM-VTON inference failed: {e}")
