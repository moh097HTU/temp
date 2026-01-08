"""
Control mapper - maps tracking errors to aircraft setpoints.

Intent-level fixed-wing control:
- yaw_error → roll (fixed-wing turns by banking)
- pitch_error → pitch
- range_error → thrust (only in flight mode)
"""

import math
from dataclasses import dataclass
from typing import Optional

from ..common.types import Errors, Setpoint
from ..common.math3d import rad_to_deg
from ..common.filters import clamp


@dataclass
class ControlGains:
    """Control loop gains."""
    # Yaw error to roll setpoint gain (rad -> deg)
    yaw_to_roll: float = 30.0  # deg/rad
    # Pitch error to pitch setpoint gain (rad -> deg)
    pitch_to_pitch: float = 20.0  # deg/rad
    # Range error to thrust gain (m -> normalized thrust)
    range_to_thrust: float = 0.05  # 1/m


@dataclass
class ControlLimits:
    """Control output limits."""
    roll_min_deg: float = -20.0
    roll_max_deg: float = 20.0
    pitch_min_deg: float = -10.0
    pitch_max_deg: float = 10.0
    thrust_min: float = 0.0
    thrust_max: float = 1.0


@dataclass
class ControlConfig:
    """Complete control configuration."""
    gains: ControlGains
    limits: ControlLimits
    thrust_enabled: bool = False  # Always False in bench mode
    # Deadband: ignore small errors
    yaw_deadband_rad: float = 0.02
    pitch_deadband_rad: float = 0.02
    range_deadband_m: float = 0.5


class ControlMapper:
    """
    Maps tracking errors to control setpoints.
    
    For fixed-wing aircraft:
    - To turn right (target on right): command positive roll (bank right)
    - To pitch up (target above): command positive pitch
    - To close distance: increase thrust (flight mode only)
    """

    def __init__(self, config: ControlConfig):
        """
        Initialize control mapper.
        
        Args:
            config: Control configuration
        """
        self.config = config

    def map(self, errors: Errors) -> Setpoint:
        """
        Map errors to setpoint.
        
        Args:
            errors: Tracking errors
            
        Returns:
            Control setpoint
        """
        # If errors are not all valid, return neutral
        if not errors.lock_valid or not errors.track_valid:
            return Setpoint.neutral()

        # Extract errors with deadband
        yaw_error = self._apply_deadband(
            errors.yaw_error, self.config.yaw_deadband_rad
        )
        pitch_error = self._apply_deadband(
            errors.pitch_error, self.config.pitch_deadband_rad
        )
        range_error = self._apply_deadband(
            errors.range_error, self.config.range_deadband_m
        ) if errors.depth_valid else 0.0

        # Compute setpoints
        # Yaw error -> Roll: target right of center -> bank right
        roll_deg = yaw_error * self.config.gains.yaw_to_roll

        # Pitch error -> Pitch: target above center -> pitch up
        pitch_deg = pitch_error * self.config.gains.pitch_to_pitch

        # Range error -> Thrust: target too far -> increase thrust
        thrust = 0.0
        if self.config.thrust_enabled and errors.depth_valid:
            # Positive range_error = target is farther than desired
            thrust = range_error * self.config.gains.range_to_thrust

        # Apply limits
        roll_deg = clamp(roll_deg, 
                        self.config.limits.roll_min_deg,
                        self.config.limits.roll_max_deg)
        pitch_deg = clamp(pitch_deg,
                         self.config.limits.pitch_min_deg,
                         self.config.limits.pitch_max_deg)
        thrust = clamp(thrust,
                      self.config.limits.thrust_min,
                      self.config.limits.thrust_max)

        return Setpoint(
            roll_deg=roll_deg,
            pitch_deg=pitch_deg,
            thrust=thrust,
            yaw_deg=0.0  # Yaw handled via roll for fixed-wing
        )

    def _apply_deadband(self, value: float, threshold: float) -> float:
        """Apply deadband to a value."""
        if abs(value) < threshold:
            return 0.0
        return value

    def compute_roll_for_yaw(self, yaw_error_rad: float) -> float:
        """
        Compute roll setpoint for a given yaw error.
        
        Args:
            yaw_error_rad: Yaw error in radians
            
        Returns:
            Roll setpoint in degrees
        """
        roll = yaw_error_rad * self.config.gains.yaw_to_roll
        return clamp(roll,
                    self.config.limits.roll_min_deg,
                    self.config.limits.roll_max_deg)

    def compute_pitch_for_pitch(self, pitch_error_rad: float) -> float:
        """
        Compute pitch setpoint for a given pitch error.
        
        Args:
            pitch_error_rad: Pitch error in radians
            
        Returns:
            Pitch setpoint in degrees
        """
        pitch = pitch_error_rad * self.config.gains.pitch_to_pitch
        return clamp(pitch,
                    self.config.limits.pitch_min_deg,
                    self.config.limits.pitch_max_deg)
