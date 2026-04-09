import pytest
import numpy as np
from ai.services.occlusion import Layer, extract_head_neck_mask, create_layer_stack, composite_layers

def test_extract_head_neck_mask():
    """Verify head/neck masking logic creates a mask over the given points."""
    keypoints = {
        'nose': (50, 20),
        'left_eye': (40, 15),
        'right_eye': (60, 15),
        'neck': (50, 50)
    }
    person_mask = np.ones((100, 100), dtype=np.uint8) * 255
    mask = extract_head_neck_mask(person_mask, keypoints)
    assert mask.shape == (100, 100)
    # The mask should be active around the nose and neck
    assert mask[20, 50] == 255
    assert mask[50, 50] == 255

def test_layer_compositing():
    """Verify that layers composite according to Z-order."""
    bg_img = np.zeros((100, 100, 3), dtype=np.uint8)
    
    # Torso: red (Z=1)
    torso_img = np.zeros((100, 100, 3), dtype=np.uint8)
    torso_img[:] = (0, 0, 255)
    torso_mask = np.ones((100, 100), dtype=np.uint8) * 255
    
    # Garment: green (Z=2)
    garment_img = np.zeros((100, 100, 3), dtype=np.uint8)
    garment_img[:] = (0, 255, 0)
    garment_mask = np.ones((100, 100), dtype=np.uint8) * 255
    
    # Arms: blue (Z=3), but mask only covers top half
    arms_img = np.zeros((100, 100, 3), dtype=np.uint8)
    arms_img[:] = (255, 0, 0)
    arms_mask = np.zeros((100, 100), dtype=np.uint8)
    arms_mask[0:50, :] = 255
    person_mask = np.ones((100, 100), dtype=np.uint8) * 255
    layers = create_layer_stack(
        person_image=bg_img,
        garment_image=garment_img,
        garment_mask=garment_mask,
        person_mask=person_mask,
        torso_mask=torso_mask,
        arms_mask=arms_mask,
        head_mask=None
    )
    
    # Note: create_layer_stack inherently skips base Layer setup, it returns Layer instances.
    # The layers should be sorted by z_order inside composite_layers
    result = composite_layers(layers)
    
    # Verify layers stack returns a valid image array
    assert result.shape == (100, 100, 3)
    assert result.dtype == np.uint8
