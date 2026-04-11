"""Stage 2: Pose detection and keypoint extraction."""
import cv2
import numpy as np
from typing import Dict, Tuple, Optional

# Try to import mediapipe, but provide fallback if not available (Python 3.8 compatibility)
try:
    import ssl
    try:
        _create_unverified_https_context = ssl._create_unverified_context
    except AttributeError:
        pass
    else:
        ssl._create_default_https_context = _create_unverified_https_context

    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
    mp_pose = mp.solutions.pose
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    mp_pose = None

from backend.models.job import ErrorCode
from backend.utils.image_utils import get_bounding_box


class PoseDetectionError(Exception):
    """Error during pose detection."""
    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.POSE_FAILED):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


def detect_keypoints(image: np.ndarray, confidence_threshold: float = 0.5) -> Dict[str, Tuple[int, int]]:
    """
    Detect body keypoints using MediaPipe Pose.
    
    Args:
        image: Input image (BGR)
        confidence_threshold: Minimum confidence for keypoint detection
        
    Returns:
        Dictionary of keypoint names to (x, y) coordinates
        
    Raises:
        PoseDetectionError: If pose detection fails
    """
    try:
        h, w = image.shape[:2]
        
        # Convert to RGB for MediaPipe
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        if not MEDIAPIPE_AVAILABLE:
            raise PoseDetectionError("MediaPipe is not installed or failed to import. Please install mediapipe.")
            
        # Run pose detection
        with mp_pose.Pose(
            static_image_mode=True,
            model_complexity=2,
            min_detection_confidence=confidence_threshold
        ) as pose:
            results = pose.process(rgb_image)
        
        if not results.pose_landmarks:
            raise PoseDetectionError("No pose detected in image")
        
        landmarks = results.pose_landmarks.landmark
        
        # Extract key points we need
        keypoints = {}
        
        # MediaPipe landmark indices
        landmark_map = {
            'nose': mp_pose.PoseLandmark.NOSE,
            'left_shoulder': mp_pose.PoseLandmark.LEFT_SHOULDER,
            'right_shoulder': mp_pose.PoseLandmark.RIGHT_SHOULDER,
            'left_elbow': mp_pose.PoseLandmark.LEFT_ELBOW,
            'right_elbow': mp_pose.PoseLandmark.RIGHT_ELBOW,
            'left_wrist': mp_pose.PoseLandmark.LEFT_WRIST,
            'right_wrist': mp_pose.PoseLandmark.RIGHT_WRIST,
            'left_hip': mp_pose.PoseLandmark.LEFT_HIP,
            'right_hip': mp_pose.PoseLandmark.RIGHT_HIP,
        }
        
        for name, landmark_id in landmark_map.items():
            landmark = landmarks[landmark_id.value]
            
            # Check confidence (visibility)
            if landmark.visibility < confidence_threshold:
                continue
            
            # Convert normalized coordinates to pixel coordinates
            x = int(landmark.x * w)
            y = int(landmark.y * h)
            
            # Ensure within bounds
            x = max(0, min(w - 1, x))
            y = max(0, min(h - 1, y))
            
            keypoints[name] = (x, y)
        
        # Calculate neck point (midpoint between shoulders)
        if 'left_shoulder' in keypoints and 'right_shoulder' in keypoints:
            ls = keypoints['left_shoulder']
            rs = keypoints['right_shoulder']
            keypoints['neck'] = (
                (ls[0] + rs[0]) // 2,
                (ls[1] + rs[1]) // 2
            )
        
        # Validate we have minimum required keypoints
        required = ['left_shoulder', 'right_shoulder']
        if not all(k in keypoints for k in required):
            raise PoseDetectionError("Missing critical keypoints (shoulders)")
        
        return keypoints
        
    except PoseDetectionError:
        raise
    except Exception as e:
        raise PoseDetectionError(f"Pose detection failed: {e}")


def get_fallback_keypoints(person_mask: np.ndarray) -> Dict[str, Tuple[int, int]]:
    """
    Generate fallback keypoints from person mask bounding box.
    
    Args:
        person_mask: Binary person mask
        
    Returns:
        Dictionary of estimated keypoints
    """
    bbox = get_bounding_box(person_mask)
    
    if bbox is None:
        raise PoseDetectionError("Cannot generate fallback keypoints - empty mask")
    
    x, y, w, h = bbox
    
    # Estimate keypoints based on typical body proportions
    keypoints = {
        'neck': (x + w // 2, y + int(h * 0.15)),
        'left_shoulder': (x + int(w * 0.3), y + int(h * 0.18)),
        'right_shoulder': (x + int(w * 0.7), y + int(h * 0.18)),
        'left_hip': (x + int(w * 0.35), y + int(h * 0.55)),
        'right_hip': (x + int(w * 0.65), y + int(h * 0.55)),
    }
    
    return keypoints


def detect_pose(image: np.ndarray, person_mask: Optional[np.ndarray] = None) -> Dict[str, Tuple[int, int]]:
    """
    Detect pose keypoints with fallback to bounding box estimation.
    
    Args:
        image: Input image (BGR)
        person_mask: Optional person mask for fallback
        
    Returns:
        Dictionary of keypoints
        
    Raises:
        PoseDetectionError: If pose detection completely fails
    """
    try:
        # Try MediaPipe detection
        keypoints = detect_keypoints(image, confidence_threshold=0.5)
        return keypoints
        
    except PoseDetectionError as e:
        # Fall back to bounding box estimation if we have a mask
        if person_mask is not None:
            print(f"Warning: {e.message}. Using fallback keypoints.")
            return get_fallback_keypoints(person_mask)
        else:
            raise
