import pytest
import numpy as np
from ai.services.quality_control import (
    check_garment_within_person, 
    check_neckline_alignment,
    check_shoulder_angle,
    check_scale_reasonable
)

def test_overlap_perfect():
    garment = np.ones((50, 50), dtype=np.uint8) * 255
    person = np.ones((50, 50), dtype=np.uint8) * 255
    
    val = check_garment_within_person(garment, person)
    assert bool(val.passed) is True
    assert val.score == 1.0

def test_overlap_failing():
    garment = np.zeros((100, 100), dtype=np.uint8)
    garment[0:50, 0:50] = 255 # Top left quadrant
    
    person = np.zeros((100, 100), dtype=np.uint8)
    person[50:100, 50:100] = 255 # Bottom right quadrant
    
    val = check_garment_within_person(garment, person)
    assert bool(val.passed) is False
    assert val.score == 0.0

def test_neckline_alignment():
    anchors = {'neckline': (50, 50)}
    person = {'neck': (55, 55)}
    
    # 5px horizontal and 5px vertical distance < 50px threshold
    val = check_neckline_alignment(anchors, person, transform_params={'tx': 0, 'ty': 0})
    assert bool(val.passed) is True

def test_scale_check():
    # Between 0.5 and 2.0 is passed
    assert bool(check_scale_reasonable({'scale': 1.0}).passed) is True
    assert bool(check_scale_reasonable({'scale': 2.1}).passed) is False
    assert bool(check_scale_reasonable({'scale': 0.4}).passed) is False
