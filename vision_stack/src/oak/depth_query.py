"""
Depth query utilities for targeting.
"""

from typing import Optional, Tuple
import numpy as np


def query_depth_point(
    depth_frame: np.ndarray,
    u: int,
    v: int,
    rgb_size: Tuple[int, int],
    depth_size: Tuple[int, int]
) -> Optional[float]:
    """
    Query depth at a single point.
    
    Args:
        depth_frame: Depth image (uint16, mm)
        u, v: Pixel coordinates in RGB frame
        rgb_size: (width, height) of RGB frame
        depth_size: (width, height) of depth frame
        
    Returns:
        Depth in meters, or None if invalid
    """
    if depth_frame is None:
        return None

    # Scale coordinates
    scale_x = depth_size[0] / rgb_size[0]
    scale_y = depth_size[1] / rgb_size[1]
    
    depth_u = int(u * scale_x)
    depth_v = int(v * scale_y)

    # Bounds check
    if not (0 <= depth_u < depth_size[0] and 0 <= depth_v < depth_size[1]):
        return None

    depth_mm = depth_frame[depth_v, depth_u]
    if depth_mm == 0:
        return None

    return depth_mm / 1000.0


def query_depth_roi_median(
    depth_frame: np.ndarray,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    rgb_size: Tuple[int, int],
    depth_size: Tuple[int, int]
) -> Optional[float]:
    """
    Query median depth over a region of interest.
    
    Args:
        depth_frame: Depth image (uint16, mm)
        x1, y1, x2, y2: ROI in RGB coordinates
        rgb_size: (width, height) of RGB frame
        depth_size: (width, height) of depth frame
        
    Returns:
        Median depth in meters, or None if invalid
    """
    if depth_frame is None:
        return None

    # Scale to depth coordinates
    scale_x = depth_size[0] / rgb_size[0]
    scale_y = depth_size[1] / rgb_size[1]

    d_x1 = max(0, int(x1 * scale_x))
    d_y1 = max(0, int(y1 * scale_y))
    d_x2 = min(depth_size[0], int(x2 * scale_x))
    d_y2 = min(depth_size[1], int(y2 * scale_y))

    if d_x2 <= d_x1 or d_y2 <= d_y1:
        return None

    roi = depth_frame[d_y1:d_y2, d_x1:d_x2]
    valid_depths = roi[roi > 0]
    
    if len(valid_depths) == 0:
        return None

    return float(np.median(valid_depths)) / 1000.0


def is_depth_in_range(
    depth_m: Optional[float],
    min_range: float,
    max_range: float
) -> bool:
    """Check if depth value is within valid range."""
    if depth_m is None:
        return False
    return min_range <= depth_m <= max_range
