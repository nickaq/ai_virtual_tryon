"""
Stage 5: Thin-Plate Spline (TPS) Warping.

Own implementation of TPS warping for non-linear garment deformation.
TPS computes a smooth interpolating function that maps source control points
to target control points, allowing the garment to deform according to body pose —
unlike affine transforms which only handle scale, rotation, and translation.

Mathematical basis:
  Given N control point pairs (source → target), TPS finds coefficients
  for the radial basis function U(r) = r² · ln(r) such that the mapping
  f(x, y) = a₀ + a₁x + a₂y + Σᵢ wᵢ · U(||(x,y) - pᵢ||)
  minimizes bending energy while exactly interpolating control points.

References:
  Bookstein, F.L. (1989). "Principal Warps: Thin-Plate Splines and the
  Decomposition of Deformations." IEEE TPAMI, 11(6), 567-585.
"""
import cv2
import numpy as np
from typing import Dict, Tuple, Optional, List

from backend.models.job import ErrorCode


class TPSWarpError(Exception):
    """Error during TPS warping."""
    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.WARP_FAILED):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


def _tps_kernel(r: np.ndarray) -> np.ndarray:
    """
    TPS radial basis function: U(r) = r² · ln(r).

    Handles r=0 case (U(0) = 0 by convention/limit).

    Args:
        r: Distance matrix or vector (non-negative values)

    Returns:
        Kernel values with same shape as input
    """
    result = np.zeros_like(r, dtype=np.float64)
    mask = r > 0
    result[mask] = (r[mask] ** 2) * np.log(r[mask])
    return result


def _pairwise_distances(points: np.ndarray) -> np.ndarray:
    """
    Compute pairwise Euclidean distance matrix between N points.

    Args:
        points: (N, 2) array of 2D points

    Returns:
        (N, N) distance matrix
    """
    diff = points[:, np.newaxis, :] - points[np.newaxis, :, :]
    return np.sqrt(np.sum(diff ** 2, axis=2))


def compute_tps_coefficients(
    source_points: np.ndarray,
    target_points: np.ndarray,
    regularization: float = 0.0
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute TPS transformation coefficients.

    Solves the linear system to find weights w and affine parameters [a₀, a₁, a₂]
    for both x and y target coordinates.

    The system is:
        ┌          ┐ ┌   ┐   ┌   ┐
        │ K + λI  P │ │ w │ = │ v │
        │ Pᵀ     0 │ │ a │   │ 0 │
        └          ┘ └   ┘   └   ┘

    Where:
        K[i,j] = U(||pᵢ - pⱼ||)  — kernel matrix
        P = [1, x₁, y₁; 1, x₂, y₂; ...]  — affine part
        v = target coordinates
        λ = regularization (0 = exact interpolation)

    Args:
        source_points: (N, 2) source control points
        target_points: (N, 2) target control points
        regularization: Regularization parameter (λ). 0 for exact interpolation.

    Returns:
        Tuple of (weights, affine_params):
            weights: (N, 2) — TPS kernel weights for x and y
            affine_params: (3, 2) — affine parameters [a₀, a₁, a₂] for x and y

    Raises:
        TPSWarpError: If the system is singular or underdetermined
    """
    n = source_points.shape[0]

    if n < 3:
        raise TPSWarpError(
            f"TPS requires at least 3 control points, got {n}. "
            "Use affine mode for fewer points."
        )

    # Compute kernel matrix K
    distances = _pairwise_distances(source_points)
    K = _tps_kernel(distances)

    # Add regularization to diagonal
    if regularization > 0:
        K += regularization * np.eye(n)

    # Build affine matrix P: [1, x, y] for each source point
    P = np.ones((n, 3), dtype=np.float64)
    P[:, 1:] = source_points

    # Build the full system matrix L
    # L = [ K  P ]
    #     [ Pᵀ 0 ]
    L = np.zeros((n + 3, n + 3), dtype=np.float64)
    L[:n, :n] = K
    L[:n, n:] = P
    L[n:, :n] = P.T

    # Right-hand side: target coordinates with zero padding for constraints
    rhs = np.zeros((n + 3, 2), dtype=np.float64)
    rhs[:n, :] = target_points

    # Solve the linear system
    try:
        coefficients = np.linalg.solve(L, rhs)
    except np.linalg.LinAlgError:
        # Fallback to least-squares if singular
        try:
            coefficients, _, _, _ = np.linalg.lstsq(L, rhs, rcond=None)
        except Exception as e:
            raise TPSWarpError(f"Failed to solve TPS system: {e}")

    weights = coefficients[:n]       # (N, 2) — kernel weights
    affine_params = coefficients[n:]  # (3, 2) — [a₀, a₁, a₂]

    return weights, affine_params


def tps_transform_points(
    points: np.ndarray,
    source_ctrl: np.ndarray,
    weights: np.ndarray,
    affine_params: np.ndarray
) -> np.ndarray:
    """
    Apply TPS transformation to a set of points.

    f(x, y) = a₀ + a₁x + a₂y + Σᵢ wᵢ · U(||(x,y) - pᵢ||)

    Args:
        points: (M, 2) points to transform
        source_ctrl: (N, 2) source control points
        weights: (N, 2) TPS kernel weights
        affine_params: (3, 2) affine parameters

    Returns:
        (M, 2) transformed points
    """
    m = points.shape[0]
    n = source_ctrl.shape[0]

    # Compute distances from each query point to each control point
    # points: (M, 2), source_ctrl: (N, 2) → distances: (M, N)
    diff = points[:, np.newaxis, :] - source_ctrl[np.newaxis, :, :]
    distances = np.sqrt(np.sum(diff ** 2, axis=2))

    # Apply TPS kernel
    K = _tps_kernel(distances)  # (M, N)

    # Affine part: [1, x, y] · [a₀, a₁, a₂]ᵀ
    P = np.ones((m, 3), dtype=np.float64)
    P[:, 1:] = points

    # f(x, y) = P · affine + K · weights
    result = P @ affine_params + K @ weights

    return result


class TPSTransform:
    """
    Thin-Plate Spline transformation.

    Encapsulates the computation and application of TPS warping
    between two sets of corresponding control points.

    Usage:
        tps = TPSTransform(source_points, target_points)
        warped_image, warped_mask = tps.warp_image(image, mask, output_shape)
    """

    def __init__(
        self,
        source_points: np.ndarray,
        target_points: np.ndarray,
        regularization: float = 0.0
    ):
        """
        Initialize TPS transform from control point correspondences.

        Args:
            source_points: (N, 2) control points on the source (garment)
            target_points: (N, 2) corresponding points on the target (person)
            regularization: Smoothing parameter (0 = exact interpolation)
        """
        self.source_points = np.array(source_points, dtype=np.float64)
        self.target_points = np.array(target_points, dtype=np.float64)
        self.regularization = regularization

        # Compute coefficients
        self.weights, self.affine_params = compute_tps_coefficients(
            self.source_points,
            self.target_points,
            regularization
        )
        self.coefficients = np.vstack([self.weights, self.affine_params])

    def transform_points(self, points: np.ndarray) -> np.ndarray:
        """
        Transform a set of 2D points using the computed TPS mapping.

        Args:
            points: (M, 2) points in source space

        Returns:
            (M, 2) points in target space
        """
        return tps_transform_points(
            points, self.source_points, self.weights, self.affine_params
        )

    def warp_image(
        self,
        image: np.ndarray,
        mask: np.ndarray,
        output_shape: Tuple[int, int]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Warp an image and its mask using the inverse TPS mapping.

        For each pixel in the output, we find its corresponding location
        in the source image using the inverse TPS transform, then sample.

        Args:
            image: Source image (H, W, C) — BGR or RGBA
            mask: Source binary mask (H, W)
            output_shape: (height, width) of output

        Returns:
            Tuple of (warped_image, warped_mask)
        """
        out_h, out_w = output_shape

        # Create inverse transform: target → source
        # We compute the inverse by fitting TPS from target → source
        try:
            inv_weights, inv_affine = compute_tps_coefficients(
                self.target_points,
                self.source_points,
                self.regularization
            )
        except TPSWarpError:
            # If inverse fails, fall back to cv2.remap with forward mapping
            return self._warp_with_forward_mapping(image, mask, output_shape)

        # Generate grid of output pixel coordinates
        grid_x, grid_y = np.meshgrid(
            np.arange(out_w, dtype=np.float64),
            np.arange(out_h, dtype=np.float64)
        )
        grid_points = np.stack([grid_x.ravel(), grid_y.ravel()], axis=1)

        # Transform output grid → source coordinates
        source_coords = tps_transform_points(
            grid_points, self.target_points, inv_weights, inv_affine
        )

        # Reshape to maps for cv2.remap
        map_x = source_coords[:, 0].reshape(out_h, out_w).astype(np.float32)
        map_y = source_coords[:, 1].reshape(out_h, out_w).astype(np.float32)

        # Warp image using remap
        if image.shape[2] == 4:
            warped_image = cv2.remap(
                image, map_x, map_y,
                interpolation=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(0, 0, 0, 0)
            )
        else:
            warped_image = cv2.remap(
                image, map_x, map_y,
                interpolation=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(0, 0, 0)
            )

        # Warp mask
        warped_mask = cv2.remap(
            mask, map_x, map_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0
        )

        # Threshold mask to binary
        _, warped_mask = cv2.threshold(warped_mask, 127, 255, cv2.THRESH_BINARY)

        return warped_image, warped_mask

    def _warp_with_forward_mapping(
        self,
        image: np.ndarray,
        mask: np.ndarray,
        output_shape: Tuple[int, int]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Fallback warping using forward mapping with scatter.

        Less accurate than inverse mapping but more robust when
        the inverse TPS system is ill-conditioned.
        """
        src_h, src_w = image.shape[:2]
        out_h, out_w = output_shape

        # Generate source grid
        grid_x, grid_y = np.meshgrid(
            np.arange(src_w, dtype=np.float64),
            np.arange(src_h, dtype=np.float64)
        )
        src_points = np.stack([grid_x.ravel(), grid_y.ravel()], axis=1)

        # Forward transform
        dst_points = tps_transform_points(
            src_points, self.source_points, self.weights, self.affine_params
        )

        # Round to integer coordinates
        dst_x = np.clip(np.round(dst_points[:, 0]).astype(int), 0, out_w - 1)
        dst_y = np.clip(np.round(dst_points[:, 1]).astype(int), 0, out_h - 1)

        # Scatter pixels
        channels = image.shape[2]
        warped_image = np.zeros((out_h, out_w, channels), dtype=image.dtype)
        warped_mask = np.zeros((out_h, out_w), dtype=mask.dtype)

        src_x = grid_x.ravel().astype(int)
        src_y = grid_y.ravel().astype(int)

        warped_image[dst_y, dst_x] = image[src_y, src_x]
        warped_mask[dst_y, dst_x] = mask[src_y, src_x]

        return warped_image, warped_mask


def build_control_point_pairs(
    garment_anchors: Dict[str, Tuple[int, int]],
    person_keypoints: Dict[str, Tuple[int, int]]
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Build corresponding control point pairs from garment anchors and person keypoints.

    Maps garment anchor names to person keypoint names based on anatomical correspondence.

    Args:
        garment_anchors: Detected anchor points on the garment
        person_keypoints: Detected keypoints on the person

    Returns:
        Tuple of (source_points, target_points) as (N, 2) arrays

    Raises:
        TPSWarpError: If fewer than 3 corresponding pairs found
    """
    # Correspondence mapping: garment anchor → person keypoint
    correspondence = {
        'left_shoulder': 'left_shoulder',
        'right_shoulder': 'right_shoulder',
        'neckline': 'neck',
        'hem_bottom': 'waist_center',   # approximate
        'left_waist': 'left_hip',
        'right_waist': 'right_hip',
        'left_hem': 'left_hip',         # fallback if no separate hem
        'right_hem': 'right_hip',       # fallback
    }

    source_pts = []
    target_pts = []

    for garment_name, person_name in correspondence.items():
        if garment_name in garment_anchors and person_name in person_keypoints:
            source_pts.append(garment_anchors[garment_name])
            target_pts.append(person_keypoints[person_name])

    # Extra: compute waist_center from hips if not in keypoints but hips available
    if 'hem_bottom' in garment_anchors and 'waist_center' not in person_keypoints:
        if 'left_hip' in person_keypoints and 'right_hip' in person_keypoints:
            lh = person_keypoints['left_hip']
            rh = person_keypoints['right_hip']
            waist_center = ((lh[0] + rh[0]) // 2, (lh[1] + rh[1]) // 2)
            source_pts.append(garment_anchors['hem_bottom'])
            target_pts.append(waist_center)

    if len(source_pts) < 3:
        raise TPSWarpError(
            f"Insufficient control point pairs ({len(source_pts)}). "
            f"TPS requires at least 3. Available garment anchors: {list(garment_anchors.keys())}, "
            f"person keypoints: {list(person_keypoints.keys())}"
        )

    return np.array(source_pts, dtype=np.float64), np.array(target_pts, dtype=np.float64)


def apply_tps_warp(
    garment_image: np.ndarray,
    garment_mask: np.ndarray,
    garment_anchors: Dict[str, Tuple[int, int]],
    person_keypoints: Dict[str, Tuple[int, int]],
    output_shape: Tuple[int, int],
    regularization: float = 0.0
) -> Tuple[np.ndarray, np.ndarray, Dict]:
    """
    Complete TPS warp pipeline: build correspondences, compute TPS, warp image.

    Args:
        garment_image: Garment image (RGBA or BGR)
        garment_mask: Garment binary mask
        garment_anchors: Garment anchor points
        person_keypoints: Person keypoints
        output_shape: (height, width) of output
        regularization: TPS smoothing (0 = exact interpolation)

    Returns:
        Tuple of (warped_image, warped_mask, transform_params)
        where transform_params contains TPS metadata for quality evaluation
    """
    # Build control point pairs
    source_pts, target_pts = build_control_point_pairs(garment_anchors, person_keypoints)

    # Compute and apply TPS
    tps = TPSTransform(source_pts, target_pts, regularization)
    warped_image, warped_mask = tps.warp_image(garment_image, garment_mask, output_shape)

    # Build transform_params compatible with quality_control expectations
    transform_params = {
        'warp_mode': 'tps',
        'num_control_points': len(source_pts),
        'regularization': regularization,
        # Approximate affine parameters for backward compatibility with quality checks
        'scale': _estimate_scale(source_pts, target_pts),
        'angle': _estimate_angle(source_pts, target_pts),
        'tx': float(tps.affine_params[0, 0]),
        'ty': float(tps.affine_params[0, 1]),
        'center': tuple(np.mean(source_pts, axis=0).astype(int)),
    }

    return warped_image, warped_mask, transform_params


def _estimate_scale(source: np.ndarray, target: np.ndarray) -> float:
    """Estimate scale factor from control point pairs (mean distance ratio)."""
    src_dists = _pairwise_distances(source)
    tgt_dists = _pairwise_distances(target)

    # Use upper triangle (non-zero, non-diagonal)
    mask = np.triu(np.ones_like(src_dists, dtype=bool), k=1)
    src_mean = np.mean(src_dists[mask]) if np.any(mask & (src_dists > 0)) else 1.0
    tgt_mean = np.mean(tgt_dists[mask]) if np.any(mask & (tgt_dists > 0)) else 1.0

    return tgt_mean / src_mean if src_mean > 0 else 1.0


def _estimate_angle(source: np.ndarray, target: np.ndarray) -> float:
    """Estimate rotation angle from first two control points."""
    if len(source) < 2 or len(target) < 2:
        return 0.0

    src_vec = source[1] - source[0]
    tgt_vec = target[1] - target[0]

    src_angle = np.degrees(np.arctan2(src_vec[1], src_vec[0]))
    tgt_angle = np.degrees(np.arctan2(tgt_vec[1], tgt_vec[0]))

    return tgt_angle - src_angle
