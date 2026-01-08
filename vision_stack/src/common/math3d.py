"""
3D math utilities for quaternion operations and coordinate transforms.
"""

import math
from dataclasses import dataclass
from typing import Tuple

import numpy as np


@dataclass
class Quaternion:
    """Quaternion representation (w, x, y, z) with Hamilton convention."""
    w: float
    x: float
    y: float
    z: float

    def to_array(self) -> np.ndarray:
        """Convert to numpy array [w, x, y, z]."""
        return np.array([self.w, self.x, self.y, self.z])

    def normalize(self) -> "Quaternion":
        """Return normalized quaternion."""
        norm = math.sqrt(self.w**2 + self.x**2 + self.y**2 + self.z**2)
        if norm < 1e-10:
            return Quaternion(1.0, 0.0, 0.0, 0.0)
        return Quaternion(self.w / norm, self.x / norm, self.y / norm, self.z / norm)

    @staticmethod
    def identity() -> "Quaternion":
        """Return identity quaternion (no rotation)."""
        return Quaternion(1.0, 0.0, 0.0, 0.0)


def euler_to_quaternion(roll_rad: float, pitch_rad: float, yaw_rad: float) -> Quaternion:
    """
    Convert Euler angles (ZYX order) to quaternion.
    
    Args:
        roll_rad: Roll angle in radians (rotation about X)
        pitch_rad: Pitch angle in radians (rotation about Y)
        yaw_rad: Yaw angle in radians (rotation about Z)
        
    Returns:
        Quaternion representing the rotation
    """
    cr = math.cos(roll_rad / 2)
    sr = math.sin(roll_rad / 2)
    cp = math.cos(pitch_rad / 2)
    sp = math.sin(pitch_rad / 2)
    cy = math.cos(yaw_rad / 2)
    sy = math.sin(yaw_rad / 2)

    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy

    return Quaternion(w, x, y, z).normalize()


def quaternion_to_euler(q: Quaternion) -> Tuple[float, float, float]:
    """
    Convert quaternion to Euler angles (ZYX order).
    
    Returns:
        Tuple of (roll, pitch, yaw) in radians
    """
    # Roll (x-axis rotation)
    sinr_cosp = 2 * (q.w * q.x + q.y * q.z)
    cosr_cosp = 1 - 2 * (q.x * q.x + q.y * q.y)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    # Pitch (y-axis rotation)
    sinp = 2 * (q.w * q.y - q.z * q.x)
    if abs(sinp) >= 1:
        pitch = math.copysign(math.pi / 2, sinp)
    else:
        pitch = math.asin(sinp)

    # Yaw (z-axis rotation)
    siny_cosp = 2 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return roll, pitch, yaw


def quaternion_multiply(q1: Quaternion, q2: Quaternion) -> Quaternion:
    """Multiply two quaternions (q1 * q2)."""
    w = q1.w * q2.w - q1.x * q2.x - q1.y * q2.y - q1.z * q2.z
    x = q1.w * q2.x + q1.x * q2.w + q1.y * q2.z - q1.z * q2.y
    y = q1.w * q2.y - q1.x * q2.z + q1.y * q2.w + q1.z * q2.x
    z = q1.w * q2.z + q1.x * q2.y - q1.y * q2.x + q1.z * q2.w
    return Quaternion(w, x, y, z)


def pixel_to_angles(
    u: float,
    v: float,
    fx: float,
    fy: float,
    cx: float,
    cy: float
) -> Tuple[float, float]:
    """
    Convert pixel coordinates to angular offsets from optical axis.
    
    Args:
        u, v: Pixel coordinates
        fx, fy: Focal lengths in pixels
        cx, cy: Principal point (image center)
        
    Returns:
        Tuple of (yaw_error, pitch_error) in radians
        - yaw_error: positive = target right of center
        - pitch_error: positive = target above center
    """
    # Pixel offset from center
    dx = u - cx
    dy = v - cy
    
    # Convert to angles using pinhole camera model
    yaw_error = math.atan2(dx, fx)
    pitch_error = -math.atan2(dy, fy)  # Negative because image y increases downward
    
    return yaw_error, pitch_error


def deg_to_rad(degrees: float) -> float:
    """Convert degrees to radians."""
    return degrees * math.pi / 180.0


def rad_to_deg(radians: float) -> float:
    """Convert radians to degrees."""
    return radians * 180.0 / math.pi


def normalize_angle(angle_rad: float) -> float:
    """Normalize angle to [-pi, pi]."""
    while angle_rad > math.pi:
        angle_rad -= 2 * math.pi
    while angle_rad < -math.pi:
        angle_rad += 2 * math.pi
    return angle_rad


def rotation_matrix_from_euler(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """
    Create 3x3 rotation matrix from Euler angles (ZYX order).
    
    Args:
        roll, pitch, yaw: Angles in radians
        
    Returns:
        3x3 rotation matrix
    """
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    
    return np.array([
        [cp*cy, sr*sp*cy - cr*sy, cr*sp*cy + sr*sy],
        [cp*sy, sr*sp*sy + cr*cy, cr*sp*sy - sr*cy],
        [-sp, sr*cp, cr*cp]
    ])
