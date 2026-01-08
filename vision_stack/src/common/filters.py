"""
Signal filtering utilities for control and GPIO processing.
"""

import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class EMAFilter:
    """
    Exponential Moving Average filter.
    
    output = alpha * input + (1 - alpha) * previous_output
    
    Higher alpha = faster response, less smoothing.
    Lower alpha = slower response, more smoothing.
    """
    alpha: float = 0.3
    _value: Optional[float] = None

    def update(self, value: float) -> float:
        """Update filter with new value and return filtered output."""
        if self._value is None:
            self._value = value
        else:
            self._value = self.alpha * value + (1 - self.alpha) * self._value
        return self._value

    def reset(self, value: Optional[float] = None) -> None:
        """Reset filter state."""
        self._value = value

    @property
    def value(self) -> Optional[float]:
        """Current filtered value."""
        return self._value


@dataclass
class SlewRateLimiter:
    """
    Limits the rate of change of a value.
    
    Prevents sudden jumps in control signals.
    """
    max_rate: float  # units per second
    _last_value: Optional[float] = None
    _last_time: Optional[float] = None

    def update(self, value: float, dt: Optional[float] = None) -> float:
        """
        Update with new value, limiting rate of change.
        
        Args:
            value: Desired value
            dt: Time delta in seconds (auto-calculated if None)
            
        Returns:
            Rate-limited value
        """
        current_time = time.time()
        
        if self._last_value is None or self._last_time is None:
            self._last_value = value
            self._last_time = current_time
            return value

        if dt is None:
            dt = current_time - self._last_time
        
        if dt <= 0:
            return self._last_value

        max_change = self.max_rate * dt
        delta = value - self._last_value
        
        if abs(delta) > max_change:
            delta = max_change if delta > 0 else -max_change
        
        self._last_value = self._last_value + delta
        self._last_time = current_time
        
        return self._last_value

    def reset(self, value: Optional[float] = None) -> None:
        """Reset limiter state."""
        self._last_value = value
        self._last_time = time.time() if value is not None else None

    @property
    def value(self) -> Optional[float]:
        """Current limited value."""
        return self._last_value


@dataclass
class Debouncer:
    """
    Digital signal debouncer for GPIO inputs.
    
    Requires signal to be stable for debounce_ms before changing output.
    """
    debounce_ms: float = 50.0
    _current_state: Optional[bool] = None
    _pending_state: Optional[bool] = None
    _pending_start: Optional[float] = None

    def update(self, value: bool) -> bool:
        """
        Update with new raw value and return debounced output.
        
        Args:
            value: Raw GPIO value
            
        Returns:
            Debounced value
        """
        current_time = time.time() * 1000  # Convert to ms

        if self._current_state is None:
            self._current_state = value
            return value

        if value == self._current_state:
            # Signal matches current state, reset pending
            self._pending_state = None
            self._pending_start = None
            return self._current_state

        # Signal differs from current state
        if self._pending_state != value:
            # New pending state
            self._pending_state = value
            self._pending_start = current_time
            return self._current_state

        # Check if debounce period has elapsed
        if self._pending_start is not None:
            elapsed = current_time - self._pending_start
            if elapsed >= self.debounce_ms:
                self._current_state = value
                self._pending_state = None
                self._pending_start = None

        return self._current_state

    def reset(self, value: Optional[bool] = None) -> None:
        """Reset debouncer state."""
        self._current_state = value
        self._pending_state = None
        self._pending_start = None

    @property
    def state(self) -> Optional[bool]:
        """Current debounced state."""
        return self._current_state


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value to range [min_val, max_val]."""
    return max(min_val, min(max_val, value))


def deadband(value: float, threshold: float) -> float:
    """Apply deadband: values within threshold become zero."""
    if abs(value) < threshold:
        return 0.0
    return value


class LowPassFilter:
    """
    Simple first-order low-pass filter.
    
    Cutoff frequency determines filter response.
    """
    
    def __init__(self, cutoff_freq: float, sample_rate: float):
        """
        Initialize low-pass filter.
        
        Args:
            cutoff_freq: Cutoff frequency in Hz
            sample_rate: Sample rate in Hz
        """
        import math
        rc = 1.0 / (2.0 * math.pi * cutoff_freq)
        dt = 1.0 / sample_rate
        self._alpha = dt / (rc + dt)
        self._value: Optional[float] = None

    def update(self, value: float) -> float:
        """Update filter with new value."""
        if self._value is None:
            self._value = value
        else:
            self._value = self._alpha * value + (1 - self._alpha) * self._value
        return self._value

    def reset(self, value: Optional[float] = None) -> None:
        """Reset filter state."""
        self._value = value

    @property
    def value(self) -> Optional[float]:
        return self._value
