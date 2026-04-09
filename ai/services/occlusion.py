"""
Stage 6: Z-order layered occlusion handling.

Implements proper depth-based compositing with 5 layers:
  Z=0  Background   — original scene behind the person
  Z=1  Body (torso) — torso beneath clothing
  Z=2  Garment      — the warped clothing item
  Z=3  Arms         — arms rendered on top of clothing
  Z=4  Head/Neck    — head and neck always on top (never occluded)

This approach replaces simple mask-based compositing with a physically
correct layer stack, producing more realistic results especially when
arms cross in front of the body or the garment has complex necklines.
"""
import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class Layer:
    """A compositing layer with image data, mask, and Z-order."""
    name: str
    image: np.ndarray       # BGR, same size as output
    mask: np.ndarray         # Single-channel alpha (0-255)
    z_order: int             # Higher = rendered on top
    feather_radius: int = 3  # Gaussian blur radius for edge feathering


def extract_head_neck_mask(
    person_mask: np.ndarray,
    keypoints: Dict[str, Tuple[int, int]],
    margin_ratio: float = 0.08
) -> np.ndarray:
    """
    Extract head and neck mask from person mask using keypoints.

    The head/neck region is defined as everything above the shoulder line
    plus a configurable margin below it (to include the upper chest/collar area).

    Args:
        person_mask: Full person binary mask (H, W)
        keypoints: Detected person keypoints
        margin_ratio: Fraction of image height used as margin below shoulders

    Returns:
        Binary mask of head/neck region (H, W)
    """
    h, w = person_mask.shape
    head_mask = np.zeros((h, w), dtype=np.uint8)

    # Determine the cutoff line (shoulder level)
    left_shoulder = keypoints.get('left_shoulder')
    right_shoulder = keypoints.get('right_shoulder')
    neck = keypoints.get('neck')
    nose = keypoints.get('nose')

    if left_shoulder and right_shoulder:
        # Shoulder line Y + margin
        shoulder_y = max(left_shoulder[1], right_shoulder[1])
        margin = int(h * margin_ratio)
        cutoff_y = shoulder_y + margin
    elif neck:
        cutoff_y = neck[1] + int(h * 0.05)
    elif nose:
        cutoff_y = nose[1] + int(h * 0.15)
    else:
        # Fallback: top 20% of person bounding box
        contours, _ = cv2.findContours(person_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            _, py, _, ph = cv2.boundingRect(max(contours, key=cv2.contourArea))
            cutoff_y = py + int(ph * 0.2)
        else:
            cutoff_y = int(h * 0.2)

    # Everything above cutoff that intersects with person mask
    head_mask[:cutoff_y, :] = person_mask[:cutoff_y, :]

    return head_mask


def feather_mask(mask: np.ndarray, radius: int = 3) -> np.ndarray:
    """
    Apply edge feathering to a binary mask for smooth layer transitions.

    Uses Gaussian blur on the mask edges to create soft alpha transitions
    instead of hard edges.

    Args:
        mask: Binary mask (0 or 255)
        radius: Blur radius (larger = softer edges)

    Returns:
        Feathered mask with smooth edges (0-255)
    """
    if radius <= 0:
        return mask

    # Ensure kernel size is odd
    kernel_size = radius * 2 + 1

    # Blur the mask to create soft edges
    feathered = cv2.GaussianBlur(
        mask.astype(np.float32),
        (kernel_size, kernel_size),
        0
    )

    # Normalize back to 0-255
    feathered = np.clip(feathered, 0, 255).astype(np.uint8)

    return feathered


def create_layer_stack(
    person_image: np.ndarray,
    garment_image: np.ndarray,
    garment_mask: np.ndarray,
    person_mask: np.ndarray,
    torso_mask: np.ndarray,
    arms_mask: np.ndarray,
    head_mask: Optional[np.ndarray] = None
) -> List[Layer]:
    """
    Create the Z-ordered layer stack for compositing.

    Args:
        person_image: Original person image (BGR, H×W×3)
        garment_image: Warped garment image (BGR or RGBA, H×W×3/4)
        garment_mask: Warped garment binary mask (H×W)
        person_mask: Person silhouette mask (not directly used but available)
        torso_mask: Torso region mask
        arms_mask: Arms region mask
        head_mask: Head/neck region mask (optional)

    Returns:
        List of Layer objects sorted by Z-order (bottom to top)
    """
    h, w = person_image.shape[:2]
    layers = []

    # Convert garment to BGR if RGBA
    if garment_image.shape[2] == 4:
        garment_bgr = garment_image[:, :, :3]
        garment_alpha = garment_image[:, :, 3]
        # Combine alpha with mask
        combined_garment_mask = cv2.bitwise_and(garment_mask, garment_alpha)
    else:
        garment_bgr = garment_image
        combined_garment_mask = garment_mask

    # Z=0: Background layer — the full original image as the base
    bg_mask = np.full((h, w), 255, dtype=np.uint8)
    layers.append(Layer(
        name="background",
        image=person_image.copy(),
        mask=bg_mask,
        z_order=0,
        feather_radius=0  # No feathering on background
    ))

    # Z=1: Body/torso — the torso region from original image
    # This is rendered beneath the garment, so only the parts NOT covered
    # by the garment will show through. We include it explicitly so that
    # skin tones at garment edges blend correctly.
    layers.append(Layer(
        name="torso",
        image=person_image.copy(),
        mask=torso_mask.copy(),
        z_order=1,
        feather_radius=2
    ))

    # Z=2: Garment — the warped clothing
    # Restrict garment to torso region (it shouldn't appear outside the body)
    garment_visible_mask = cv2.bitwise_and(combined_garment_mask, torso_mask)
    garment_layer_image = np.zeros_like(person_image)
    garment_layer_image[:, :] = garment_bgr[:, :]
    layers.append(Layer(
        name="garment",
        image=garment_layer_image,
        mask=garment_visible_mask,
        z_order=2,
        feather_radius=3
    ))

    # Z=3: Arms — rendered on top of the garment
    arms_layer_image = person_image.copy()
    layers.append(Layer(
        name="arms",
        image=arms_layer_image,
        mask=arms_mask.copy(),
        z_order=3,
        feather_radius=2
    ))

    # Z=4: Head/Neck — always on top
    if head_mask is not None and cv2.countNonZero(head_mask) > 0:
        head_layer_image = person_image.copy()
        layers.append(Layer(
            name="head_neck",
            image=head_layer_image,
            mask=head_mask.copy(),
            z_order=4,
            feather_radius=2
        ))

    # Sort by Z-order (should already be sorted, but be explicit)
    layers.sort(key=lambda l: l.z_order)

    return layers


def composite_layers(layers: List[Layer]) -> np.ndarray:
    """
    Composite a stack of layers from bottom to top using alpha blending.

    Each layer's mask is feathered for smooth transitions, then
    painted over the accumulator in Z-order.

    Args:
        layers: List of Layer objects sorted by Z-order (bottom to top)

    Returns:
        Final composited image (BGR, H×W×3)
    """
    if not layers:
        raise ValueError("No layers to composite")

    # Start with the bottom layer as the base
    base = layers[0]
    result = base.image.copy()

    # Paint each subsequent layer on top
    for layer in layers[1:]:
        # Feather the mask edges
        alpha_mask = feather_mask(layer.mask, layer.feather_radius)

        # Normalize to 0.0-1.0
        alpha = alpha_mask.astype(np.float32) / 255.0
        alpha = np.expand_dims(alpha, axis=2)  # (H, W) → (H, W, 1)

        # Alpha blend: result = layer * alpha + result * (1 - alpha)
        result = (layer.image.astype(np.float32) * alpha +
                  result.astype(np.float32) * (1.0 - alpha)).astype(np.uint8)

    return result
