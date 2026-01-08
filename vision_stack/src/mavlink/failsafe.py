"""
Failsafe state machine.

Handles failsafe conditions and recovery.
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

logger = logging.getLogger(__name__)


class FailsafeState(Enum):
    """Failsafe state machine states."""
    NOMINAL = auto()  # Normal operation
    WARNING = auto()  # Minor issues, continue with caution
    FAILSAFE = auto()  # Critical issue, commanding neutral
    RECOVERY = auto()  # Recovering from failsafe


class FailsafeAction(Enum):
    """Actions to take on failsafe."""
    NEUTRAL = auto()  # Send neutral setpoints (bench mode)
    LOITER = auto()  # Exit offboard, enter loiter (flight mode)
    RTL = auto()  # Return to launch


@dataclass
class FailsafeConfig:
    """Failsafe configuration."""
    # Timeouts
    track_lost_warning_ms: float = 250.0
    track_lost_failsafe_ms: float = 500.0
    telemetry_lost_warning_ms: float = 500.0
    telemetry_lost_failsafe_ms: float = 1000.0
    
    # Actions
    action: FailsafeAction = FailsafeAction.NEUTRAL
    
    # Recovery
    recovery_confirmation_ms: float = 500.0  # Time good before leaving failsafe


class FailsafeManager:
    """
    Manages failsafe state machine.
    
    Monitors:
    - Track/lock validity
    - Telemetry freshness
    - Data rates
    
    Transitions:
    NOMINAL → WARNING → FAILSAFE → RECOVERY → NOMINAL
    """

    def __init__(self, config: FailsafeConfig):
        """
        Initialize failsafe manager.
        
        Args:
            config: Failsafe configuration
        """
        self.config = config
        
        # State
        self._state = FailsafeState.NOMINAL
        self._failsafe_entry_time: Optional[float] = None
        self._recovery_start_time: Optional[float] = None
        
        # Tracking
        self._last_track_valid_time: Optional[float] = None
        self._last_telemetry_time: Optional[float] = None
        
        logger.info("FailsafeManager initialized")

    def update(
        self,
        track_valid: bool,
        telemetry_valid: bool,
        lock_valid: bool
    ) -> FailsafeState:
        """
        Update failsafe state based on current conditions.
        
        Args:
            track_valid: Whether tracking data is valid
            telemetry_valid: Whether telemetry is fresh
            lock_valid: Whether target lock is valid
            
        Returns:
            Current failsafe state
        """
        current_time = time.time()
        
        # Update timestamps
        if track_valid and lock_valid:
            self._last_track_valid_time = current_time
        if telemetry_valid:
            self._last_telemetry_time = current_time
        
        # Calculate elapsed times
        track_elapsed_ms = self._elapsed_ms(self._last_track_valid_time, current_time)
        telem_elapsed_ms = self._elapsed_ms(self._last_telemetry_time, current_time)
        
        # Determine target state based on conditions
        target_state = self._evaluate_conditions(track_elapsed_ms, telem_elapsed_ms)
        
        # State machine transitions
        new_state = self._transition(target_state, current_time)
        
        if new_state != self._state:
            logger.info(f"Failsafe state: {self._state.name} → {new_state.name}")
            self._state = new_state
        
        return self._state

    def _elapsed_ms(self, last_time: Optional[float], current_time: float) -> float:
        """Calculate elapsed time in ms, or infinity if never set."""
        if last_time is None:
            return float('inf')
        return (current_time - last_time) * 1000

    def _evaluate_conditions(
        self,
        track_elapsed_ms: float,
        telem_elapsed_ms: float
    ) -> FailsafeState:
        """Evaluate conditions and return target state."""
        # Check for failsafe conditions
        track_failsafe = track_elapsed_ms >= self.config.track_lost_failsafe_ms
        telem_failsafe = telem_elapsed_ms >= self.config.telemetry_lost_failsafe_ms
        
        if track_failsafe or telem_failsafe:
            return FailsafeState.FAILSAFE
        
        # Check for warning conditions
        track_warning = track_elapsed_ms >= self.config.track_lost_warning_ms
        telem_warning = telem_elapsed_ms >= self.config.telemetry_lost_warning_ms
        
        if track_warning or telem_warning:
            return FailsafeState.WARNING
        
        return FailsafeState.NOMINAL

    def _transition(self, target: FailsafeState, current_time: float) -> FailsafeState:
        """Handle state machine transitions."""
        if self._state == FailsafeState.NOMINAL:
            if target == FailsafeState.WARNING:
                return FailsafeState.WARNING
            elif target == FailsafeState.FAILSAFE:
                self._failsafe_entry_time = current_time
                return FailsafeState.FAILSAFE
        
        elif self._state == FailsafeState.WARNING:
            if target == FailsafeState.NOMINAL:
                return FailsafeState.NOMINAL
            elif target == FailsafeState.FAILSAFE:
                self._failsafe_entry_time = current_time
                return FailsafeState.FAILSAFE
        
        elif self._state == FailsafeState.FAILSAFE:
            if target == FailsafeState.NOMINAL or target == FailsafeState.WARNING:
                # Start recovery
                self._recovery_start_time = current_time
                return FailsafeState.RECOVERY
        
        elif self._state == FailsafeState.RECOVERY:
            if target == FailsafeState.FAILSAFE:
                # Back to failsafe
                self._recovery_start_time = None
                return FailsafeState.FAILSAFE
            elif target == FailsafeState.NOMINAL:
                # Check recovery duration
                if self._recovery_start_time is not None:
                    recovery_ms = (current_time - self._recovery_start_time) * 1000
                    if recovery_ms >= self.config.recovery_confirmation_ms:
                        self._recovery_start_time = None
                        return FailsafeState.NOMINAL
        
        return self._state

    def reset(self) -> None:
        """Reset failsafe state to nominal."""
        self._state = FailsafeState.NOMINAL
        self._failsafe_entry_time = None
        self._recovery_start_time = None
        self._last_track_valid_time = time.time()
        self._last_telemetry_time = time.time()
        logger.info("FailsafeManager reset")

    @property
    def state(self) -> FailsafeState:
        """Get current failsafe state."""
        return self._state

    @property
    def is_failsafe(self) -> bool:
        """Check if in failsafe mode."""
        return self._state in [FailsafeState.FAILSAFE, FailsafeState.RECOVERY]

    @property
    def action(self) -> FailsafeAction:
        """Get configured failsafe action."""
        return self.config.action

    @property
    def should_command_neutral(self) -> bool:
        """Check if should command neutral setpoints."""
        return self._state in [FailsafeState.FAILSAFE, FailsafeState.RECOVERY]
