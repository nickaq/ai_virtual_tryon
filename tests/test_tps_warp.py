import pytest
import numpy as np
from ai.services.tps_warp import TPSTransform, compute_tps_coefficients, TPSWarpError

def test_tps_interpolation_exact_match():
    """Verify that source control points map exactly to destination points."""
    src = np.array([[0,0], [100,0], [0,100], [100,100]], dtype=np.float64)
    dst = np.array([[10,10], [90,5], [5,95], [105,105]], dtype=np.float64)
    
    tps = TPSTransform(src, dst)
    mapped = tps.transform_points(src)
    
    # TPS should perfectly interpolate control points
    error = np.mean(np.abs(mapped - dst))
    assert error < 1e-5, f"Interpolation error too large: {error}"

def test_tps_image_warping_shape():
    """Verify warp_image returns identical dimensions as output_shape."""
    src = np.array([[0,0], [100,0], [0,100], [100,100]], dtype=np.float64)
    dst = np.array([[10,10], [90,5], [5,95], [105,105]], dtype=np.float64)
    tps = TPSTransform(src, dst)
    
    img = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
    mask = np.ones((200, 200), dtype=np.uint8) * 255
    
    warped_img, warped_mask = tps.warp_image(img, mask, (250, 250))
    
    assert warped_img.shape == (250, 250, 3)
    assert warped_mask.shape == (250, 250)

def test_tps_fewer_than_3_points():
    """Verify that TPS construction fails gracefully if given 1 or 2 points."""
    src = np.array([[0,0], [100,0]], dtype=np.float64)
    dst = np.array([[10,10], [90,5]], dtype=np.float64)
    
    with pytest.raises(TPSWarpError, match="at least 3 control points"):
        TPSTransform(src, dst)
