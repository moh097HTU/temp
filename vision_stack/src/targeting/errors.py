"""
Error computation for targeting.

Computes yaw, pitch, and range errors from target position
relative to camera optical axis.
"""

import math
from dataclasses import dataclass
from typing import Optional, Tuple

from ..common.types import Track, Errors, CameraIntrinsics, BoundingBox
from ..common.math3d import pixel_to_angles


@dataclass
class ErrorConfig:
    """Error computation configuration."""
    desired_range_m: float = 10.0  # Desired distance to target
    min_range_m: float = 3.0  # Minimum valid range
    max_range_m: float = 50.0  # Maximum valid range
    depth_percentile: float = 50.0  # Which percentile to use for depth ROI


class ErrorComputer:
    """
    Computes tracking errors from target position.
    
    Errors:
    - yaw_error: Horizontal angular offset from optical axis (positive = target right)
    - pitch_error: Vertical angular offset from optical axis (positive = target above)
    - range_error: Distance error from desired range (positive = target too far)
    """

    def __init__(self, intrinsics: CameraIntrinsics, config: ErrorConfig):
        """
        Initialize error computer.
        
        Args:
            intrinsics: Camera intrinsic parameters
            config: Error computation configuration
        """
        self.intrinsics = intrinsics
        self.config = config

    def compute(
        self,
        track: Optional[Track],
        depth_m: Optional[float],
        lock_valid: bool
    ) -> Errors:
        """
        Compute tracking errors.
        
        Args:
            track: Locked target track (may be None)
            depth_m: Depth to target in meters (may be None)
            lock_valid: Whether lock is currently valid
            
        Returns:
            Errors object with computed errors and validity flags
        """
        # Initialize with zero errors
        errors = Errors(
            yaw_error=0.0,
            pitch_error=0.0,
            range_error=0.0,
            track_valid=False,
            depth_valid=False,
            lock_valid=lock_valid
        )

        if not lock_valid or track is None:
            return errors

        # Track is valid
        errors.track_valid = True

        # Compute target center in pixels
        cx, cy = track.bbox.center

        # Compute angular errors using camera intrinsics
        yaw_error, pitch_error = pixel_to_angles(
            u=cx,
            v=cy,
            fx=self.intrinsics.fx,
            fy=self.intrinsics.fy,
            cx=self.intrinsics.cx,
            cy=self.intrinsics.cy
        )

        errors.yaw_error = yaw_error
        errors.pitch_error = pitch_error

        # Compute range error if depth is valid
        if depth_m is not None:
            if self.config.min_range_m <= depth_m <= self.config.max_range_m:
                errors.depth_valid = True
                errors.range_error = depth_m - self.config.desired_range_m
            else:
                # Depth out of valid range
                errors.depth_valid = False
                # Still provide error estimate for out-of-range cases
                if depth_m < self.config.min_range_m:
                    errors.range_error = depth_m - self.config.desired_range_m
                else:
                    errors.range_error = depth_m - self.config.desired_range_m

        return errors

    def compute_from_pixel(
        self,
        pixel: Tuple[float, float],
        depth_m: Optional[float]
    ) -> Tuple[float, float, float]:
        """
        Compute raw errors from a pixel position.
        
        Args:
            pixel: (u, v) pixel coordinates
            depth_m: Depth in meters
            
        Returns:
            Tuple of (yaw_error, pitch_error, range_error) in radians and meters
        """
        u, v = pixel

        yaw_error, pitch_error = pixel_to_angles(
            u=u,
            v=v,
            fx=self.intrinsics.fx,
            fy=self.intrinsics.fy,
            cx=self.intrinsics.cx,
            cy=self.intrinsics.cy
        )

        range_error = 0.0
        if depth_m is not None:
            range_error = depth_m - self.config.desired_range_m

        return yaw_error, pitch_error, range_error

    def is_centered(
        self,
        errors: Errors,
        yaw_threshold_rad: float = 0.05,
        pitch_threshold_rad: float = 0.05
    ) -> bool:
        """
        Check if target is approximately centered.
        
        Args:
            errors: Computed errors
            yaw_threshold_rad: Max yaw error to be considered centered
            pitch_threshold_rad: Max pitch error to be considered centered
            
        Returns:
            True if target is within thresholds
        """
        if not errors.all_valid:
            return False
        
        return (abs(errors.yaw_error) < yaw_threshold_rad and
                abs(errors.pitch_error) < pitch_threshold_rad)

    def is_in_range(self, errors: Errors, threshold_m: float = 2.0) -> bool:
        """
        Check if target is approximately at desired range.
        
        Args:
            errors: Computed errors
            threshold_m: Max range error to be considered in range
            
        Returns:
            True if target is within range threshold
        """
        if not errors.depth_valid:
            return False
        
        return abs(errors.range_error) < threshold_m
