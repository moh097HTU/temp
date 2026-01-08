"""
Safety manager - enforces safe control outputs.

Implements:
- EMA filtering for smooth outputs
- Slew rate limiting
- Clamping to safe limits
- Gating on validity
- Timeout failsafe
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

from ..common.types import Setpoint
from ..common.filters import EMAFilter, SlewRateLimiter, clamp

logger = logging.getLogger(__name__)


@dataclass
class SafetyConfig:
    """Safety manager configuration."""
    # Filtering
    roll_ema_alpha: float = 0.3
    pitch_ema_alpha: float = 0.3
    
    # Slew rate limits (degrees per second)
    roll_slew_rate_deg_s: float = 30.0
    pitch_slew_rate_deg_s: float = 20.0
    
    # Output limits
    roll_limit_deg: float = 20.0
    pitch_limit_deg: float = 10.0
    
    # Timeouts (milliseconds)
    track_timeout_ms: float = 500.0
    telemetry_timeout_ms: float = 1000.0
    
    # Bench mode
    bench_mode: bool = True  # Thrust always 0 in bench mode


class SafetyManager:
    """
    Enforces safe control outputs.
    
    All setpoints pass through:
    1. Validity gating (returns neutral if invalid)
    2. EMA filtering (smooth response)
    3. Slew rate limiting (prevent sudden jumps)
    4. Clamping (enforce hard limits)
    5. Bench mode thrust override (thrust = 0)
    """

    def __init__(self, config: SafetyConfig):
        """
        Initialize safety manager.
        
        Args:
            config: Safety configuration
        """
        self.config = config
        
        # EMA filters
        self._roll_ema = EMAFilter(alpha=config.roll_ema_alpha)
        self._pitch_ema = EMAFilter(alpha=config.pitch_ema_alpha)
        
        # Slew rate limiters
        self._roll_slew = SlewRateLimiter(max_rate=config.roll_slew_rate_deg_s)
        self._pitch_slew = SlewRateLimiter(max_rate=config.pitch_slew_rate_deg_s)
        
        # Last valid setpoint time
        self._last_valid_time: Optional[float] = None
        self._last_telemetry_time: Optional[float] = None
        
        # Failsafe state
        self._failsafe_active = False
        
        logger.info(f"SafetyManager initialized (bench_mode={config.bench_mode})")

    def apply(
        self,
        setpoint: Setpoint,
        lock_valid: bool,
        track_fresh: bool,
        telemetry_fresh: bool = True
    ) -> Setpoint:
        """
        Apply safety constraints to setpoint.
        
        Args:
            setpoint: Raw setpoint from control mapper
            lock_valid: Whether target lock is valid
            track_fresh: Whether tracking data is fresh
            telemetry_fresh: Whether FC telemetry is fresh
            
        Returns:
            Safe setpoint with all constraints applied
        """
        current_time = time.time()
        
        # Update telemetry timestamp
        if telemetry_fresh:
            self._last_telemetry_time = current_time
        
        # Check validity gates
        if not self._check_gates(lock_valid, track_fresh, telemetry_fresh, current_time):
            return self._get_failsafe_setpoint()
        
        # Record valid time
        self._last_valid_time = current_time
        self._failsafe_active = False
        
        # Apply EMA filtering
        roll_filtered = self._roll_ema.update(setpoint.roll_deg)
        pitch_filtered = self._pitch_ema.update(setpoint.pitch_deg)
        
        # Apply slew rate limiting
        roll_slewed = self._roll_slew.update(roll_filtered)
        pitch_slewed = self._pitch_slew.update(pitch_filtered)
        
        # Apply hard clamps
        roll_clamped = clamp(roll_slewed, 
                           -self.config.roll_limit_deg,
                           self.config.roll_limit_deg)
        pitch_clamped = clamp(pitch_slewed,
                            -self.config.pitch_limit_deg,
                            self.config.pitch_limit_deg)
        
        # Force thrust to 0 in bench mode
        thrust = 0.0 if self.config.bench_mode else setpoint.thrust
        
        return Setpoint(
            roll_deg=roll_clamped,
            pitch_deg=pitch_clamped,
            thrust=thrust,
            yaw_deg=setpoint.yaw_deg
        )

    def _check_gates(
        self,
        lock_valid: bool,
        track_fresh: bool,
        telemetry_fresh: bool,
        current_time: float
    ) -> bool:
        """Check all validity gates."""
        # Lock must be valid
        if not lock_valid:
            if not self._failsafe_active:
                logger.warning("Lock invalid - entering failsafe")
            return False
        
        # Track must be fresh
        if not track_fresh:
            if not self._failsafe_active:
                logger.warning("Track stale - entering failsafe")
            return False
        
        # Check track timeout
        if self._last_valid_time is not None:
            time_since_valid = (current_time - self._last_valid_time) * 1000
            if time_since_valid > self.config.track_timeout_ms:
                if not self._failsafe_active:
                    logger.warning(f"Track timeout ({time_since_valid:.0f}ms) - failsafe")
                return False
        
        # Check telemetry timeout
        if not telemetry_fresh and self._last_telemetry_time is not None:
            time_since_telemetry = (current_time - self._last_telemetry_time) * 1000
            if time_since_telemetry > self.config.telemetry_timeout_ms:
                if not self._failsafe_active:
                    logger.warning(f"Telemetry timeout ({time_since_telemetry:.0f}ms) - failsafe")
                return False
        
        return True

    def _get_failsafe_setpoint(self) -> Setpoint:
        """Get failsafe (neutral) setpoint."""
        self._failsafe_active = True
        
        # Gradually ramp to neutral using slew limiters
        roll_safe = self._roll_slew.update(0.0)
        pitch_safe = self._pitch_slew.update(0.0)
        
        return Setpoint(
            roll_deg=roll_safe,
            pitch_deg=pitch_safe,
            thrust=0.0,  # Always 0 in failsafe
            yaw_deg=0.0
        )

    def reset(self) -> None:
        """Reset safety manager state."""
        self._roll_ema.reset()
        self._pitch_ema.reset()
        self._roll_slew.reset()
        self._pitch_slew.reset()
        self._last_valid_time = None
        self._last_telemetry_time = None
        self._failsafe_active = False
        logger.info("SafetyManager reset")

    def force_neutral(self) -> Setpoint:
        """Force immediate neutral setpoint (bypass slew)."""
        self._roll_ema.reset(0.0)
        self._pitch_ema.reset(0.0)
        self._roll_slew.reset(0.0)
        self._pitch_slew.reset(0.0)
        return Setpoint.neutral()

    @property
    def is_failsafe_active(self) -> bool:
        """Check if failsafe is currently active."""
        return self._failsafe_active

    @property
    def bench_mode(self) -> bool:
        """Check if in bench mode."""
        return self.config.bench_mode

    def set_bench_mode(self, enabled: bool) -> None:
        """Set bench mode."""
        self.config.bench_mode = enabled
        logger.info(f"Bench mode: {enabled}")
