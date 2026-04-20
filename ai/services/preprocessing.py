"""Preprocessing pipeline for IDM-VTON.

Generates the three inputs the VTON model needs from a raw person image:
  1. DensePose visualization (body part + UV map)
  2. Human parsing segmentation map
  3. Agnostic mask (regions where clothing should be generated)
"""
import os
import sys
import cv2
import numpy as np
from PIL import Image
from typing import Tuple, Optional

from backend.models.job import ErrorCode

IDM_VTON_PATH = os.environ.get("IDM_VTON_PATH", "/app/IDM-VTON")
CKPT_DIR = os.path.join(IDM_VTON_PATH, "ckpt")


class PreprocessingError(Exception):
    """Error during preprocessing."""
    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.SEGMENTATION_FAILED):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


# ── DensePose ─────────────────────────────────────────────────────────

_densepose_predictor = None


def _load_densepose():
    """Load DensePose predictor (lazy, once)."""
    global _densepose_predictor
    if _densepose_predictor is not None:
        return _densepose_predictor

    try:
        from detectron2.config import get_cfg
        from detectron2.engine import DefaultPredictor
        from detectron2 import model_zoo
    except ImportError:
        raise PreprocessingError(
            "detectron2 is not installed. Cannot generate DensePose. "
            "Install with: pip install 'git+https://github.com/facebookresearch/detectron2.git'"
        )

    print("Loading DensePose model...")

    cfg = get_cfg()

    # Add DensePose config
    from densepose import add_densepose_config
    add_densepose_config(cfg)

    densepose_cfg = os.path.join(
        IDM_VTON_PATH, "preprocess", "detectron2", "projects", "DensePose",
        "configs", "densepose_rcnn_R_50_FPN_s1x.yaml"
    )

    # If the config file from IDM-VTON repo is available, use it
    if os.path.exists(densepose_cfg):
        cfg.merge_from_file(densepose_cfg)
    else:
        # Fallback: use detectron2 model zoo config
        cfg.merge_from_file(
            model_zoo.get_config_file("COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x.yaml")
        )

    model_path = os.path.join(CKPT_DIR, "densepose", "model_final_162be9.pkl")
    if not os.path.exists(model_path):
        raise PreprocessingError(
            f"DensePose model not found at {model_path}. "
            "Run scripts/setup_idm_vton.sh to download checkpoints."
        )

    cfg.MODEL.WEIGHTS = model_path
    cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.5
    cfg.MODEL.DEVICE = "cuda" if __import__("torch").cuda.is_available() else "cpu"

    _densepose_predictor = DefaultPredictor(cfg)
    print("  DensePose model loaded.")
    return _densepose_predictor


def generate_densepose(person_image: Image.Image) -> Image.Image:
    """
    Generate DensePose visualization from person image.

    Args:
        person_image: Person photo (PIL RGB)

    Returns:
        DensePose visualization image (PIL RGB, same size as input)

    Raises:
        PreprocessingError: If DensePose generation fails
    """
    try:
        # Try to use IDM-VTON's built-in DensePose preprocessing
        if IDM_VTON_PATH not in sys.path:
            sys.path.insert(0, IDM_VTON_PATH)

        try:
            from preprocess.detectron2.projects.DensePose.densepose.vis.extractor import (
                DensePoseResultExtractor,
            )
            from preprocess.detectron2.projects.DensePose.densepose.vis.densepose_results import (
                DensePoseResultsFineSegmentationVisualizer as Visualizer,
            )
        except ImportError:
            from densepose.vis.extractor import DensePoseResultExtractor
            from densepose.vis.densepose_results import (
                DensePoseResultsFineSegmentationVisualizer as Visualizer,
            )

        predictor = _load_densepose()

        # Convert to numpy BGR for detectron2
        img_np = np.array(person_image)
        if img_np.shape[2] == 4:
            img_np = img_np[:, :, :3]
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        # Run DensePose
        with __import__("torch").no_grad():
            outputs = predictor(img_bgr)["instances"]

        # Extract and visualize results
        extractor = DensePoseResultExtractor()
        results = extractor(outputs)

        # Create visualization
        vis = Visualizer()
        densepose_img = np.zeros_like(img_bgr)
        vis.visualize(densepose_img, results)

        # Convert back to RGB PIL
        densepose_rgb = cv2.cvtColor(densepose_img, cv2.COLOR_BGR2RGB)
        return Image.fromarray(densepose_rgb)

    except PreprocessingError:
        raise
    except Exception as e:
        raise PreprocessingError(f"DensePose generation failed: {e}")


# ── Human Parsing ─────────────────────────────────────────────────────

_parsing_session = None


def _load_parsing_model():
    """Load human parsing ONNX model (lazy, once)."""
    global _parsing_session
    if _parsing_session is not None:
        return _parsing_session

    import onnxruntime as ort

    model_path = os.path.join(CKPT_DIR, "humanparsing", "parsing_lip.onnx")
    if not os.path.exists(model_path):
        # Fallback to ATR model
        model_path = os.path.join(CKPT_DIR, "humanparsing", "parsing_atr.onnx")

    if not os.path.exists(model_path):
        raise PreprocessingError(
            f"Human parsing model not found. Run scripts/setup_idm_vton.sh to download."
        )

    print(f"Loading human parsing model from {model_path}...")
    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    _parsing_session = ort.InferenceSession(model_path, providers=providers)
    print("  Human parsing model loaded.")
    return _parsing_session


def generate_human_parsing(person_image: Image.Image) -> np.ndarray:
    """
    Generate human parsing segmentation map.

    LIP labels:
        0: Background, 1: Hat, 2: Hair, 3: Glove, 4: Sunglasses,
        5: Upper-clothes, 6: Dress, 7: Coat, 8: Socks, 9: Pants,
        10: Jumpsuits, 11: Scarf, 12: Skirt, 13: Face, 14: Left-arm,
        15: Right-arm, 16: Left-leg, 17: Right-leg, 18: Left-shoe, 19: Right-shoe

    Args:
        person_image: Person photo (PIL RGB)

    Returns:
        Parsing map as numpy array (H, W) with integer class labels
    """
    try:
        session = _load_parsing_model()

        # Prepare input: resize to model input size
        input_size = (473, 473)  # Standard SCHP input
        img_resized = person_image.resize(input_size, Image.LANCZOS)
        img_np = np.array(img_resized).astype(np.float32)

        # Normalize (ImageNet mean/std)
        mean = np.array([0.485, 0.456, 0.406]).reshape(1, 1, 3)
        std = np.array([0.229, 0.224, 0.225]).reshape(1, 1, 3)
        img_np = (img_np / 255.0 - mean) / std

        # NCHW format
        img_tensor = np.transpose(img_np, (2, 0, 1))[np.newaxis, :].astype(np.float32)

        # Run inference
        input_name = session.get_inputs()[0].name
        output = session.run(None, {input_name: img_tensor})[0]

        # Get class predictions
        parsing = np.argmax(output[0], axis=0)

        # Resize back to original size
        orig_w, orig_h = person_image.size
        parsing_resized = cv2.resize(
            parsing.astype(np.uint8), (orig_w, orig_h), interpolation=cv2.INTER_NEAREST
        )

        return parsing_resized

    except PreprocessingError:
        raise
    except Exception as e:
        raise PreprocessingError(f"Human parsing failed: {e}")


# ── Agnostic Mask ─────────────────────────────────────────────────────

# LIP label IDs for clothing regions
UPPER_CLOTHING_LABELS = {5, 6, 7, 10, 11}   # Upper-clothes, Dress, Coat, Jumpsuits, Scarf
LOWER_CLOTHING_LABELS = {9, 12}              # Pants, Skirt
ALL_CLOTHING_LABELS = UPPER_CLOTHING_LABELS | LOWER_CLOTHING_LABELS


def generate_agnostic_mask(
    parsing_map: np.ndarray,
    category: str = "upper_body",
) -> Image.Image:
    """
    Generate agnostic mask from human parsing.

    The agnostic mask marks regions where the model should generate clothing.
    White (255) = area to inpaint, Black (0) = keep as is.

    Args:
        parsing_map: Human parsing segmentation map (H, W)
        category: Clothing category — 'upper_body', 'lower_body', or 'dresses'

    Returns:
        Agnostic mask (PIL image, mode L)
    """
    h, w = parsing_map.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)

    if category == "lower_body":
        target_labels = LOWER_CLOTHING_LABELS
    elif category == "dresses":
        target_labels = ALL_CLOTHING_LABELS
    else:  # upper_body (default)
        target_labels = UPPER_CLOTHING_LABELS

    # Mark clothing regions
    for label_id in target_labels:
        mask[parsing_map == label_id] = 255

    # Also mask arms for upper body (they overlap with clothing)
    if category in ("upper_body", "dresses"):
        mask[parsing_map == 14] = 255  # Left-arm
        mask[parsing_map == 15] = 255  # Right-arm

    # Dilate mask slightly for smoother boundaries
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.dilate(mask, kernel, iterations=2)

    return Image.fromarray(mask, mode="L")


# ── Combined preprocessing ────────────────────────────────────────────

async def preprocess_person(
    person_image: Image.Image,
    category: str = "upper_body",
) -> Tuple[Image.Image, Image.Image, np.ndarray]:
    """
    Full preprocessing pipeline for a person image.

    Args:
        person_image: Person photo (PIL RGB)
        category: Clothing category

    Returns:
        Tuple of (densepose_image, agnostic_mask, parsing_map)

    Raises:
        PreprocessingError: If any preprocessing step fails
    """
    import asyncio

    loop = asyncio.get_running_loop()

    print("  Generating DensePose...")
    densepose_image = await loop.run_in_executor(None, generate_densepose, person_image)

    print("  Generating human parsing...")
    parsing_map = await loop.run_in_executor(None, generate_human_parsing, person_image)

    print("  Generating agnostic mask...")
    agnostic_mask = generate_agnostic_mask(parsing_map, category)

    return densepose_image, agnostic_mask, parsing_map
