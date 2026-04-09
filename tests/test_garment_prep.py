import pytest
import numpy as np
import cv2
from ai.services.garment_prep import detect_garment_anchor_points

def test_garment_prep_dress_vs_tshirt():
    mask = np.zeros((200, 200), dtype=np.uint8)
    # create an ellipse so contour has points at every Y coordinate
    cv2.ellipse(mask, (100, 100), (50, 80), 0, 0, 360, 255, -1)
    
    # t-shirt: waist goes up to ~65%, hem ~80%
    anchors_tshirt = detect_garment_anchor_points(mask, "t-shirt")
    anchors_dress = detect_garment_anchor_points(mask, "dress")
    
    # Just assert the keys are properly generated and the function doesn't crash
    assert "left_waist" in anchors_tshirt
    assert "left_waist" in anchors_dress
    assert len(anchors_tshirt) == 8
    assert len(anchors_dress) == 8
